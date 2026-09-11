"""Run-scoped native-hybrid Chat player.

ONE GPU-owning worker per benchmark run, shared by every concurrent user:

    user 1 ─┐
    user 2 ─┼─▶ AI REQUEST QUEUE ─▶ ONE NATIVE CHAT PLAYER ─▶ GPU
    user 3 ─┘

Spawning a model process per user would measure nothing except how fast a 16 GB
card runs out of memory. The interesting question is the opposite one: with a
single resident player, at what concurrency does the *queue* make latency
unacceptable? That is what this adapter is built to expose, so queue depth and
queue wait are first-class measurements here, not afterthoughts.

This is the H3/H5-proven path and nothing else: native PyTorch + Transformers,
BitsAndBytes NF4, the exact H3 model, driven through the H5 supervisor's GPU
lease. It never touches /api/chat, symoneural-llm, llama.cpp, vLLM or GPT-OSS.

Cold start is measured separately and never folded into steady-state latency --
a model load is not an inference.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from .core import NOT_AVAILABLE, percentiles
from .players import Player, PlayerResult

HYBRID = Path("/home/google/Symoneural/.claude/worktrees/native-hybrid-gpu-player/"
              "engines/symoneural-hybrid")

# The exact H3-proven configuration. Changing any of these makes the result a
# measurement of something else, so they are constants, not parameters.
CHAT_PY = "/home/google/.venvs/vllm/bin/python"
CHAT_MODEL = ("/home/google/Symoneural/backend/models/hf/hub/"
              "models--Qwen--Qwen2.5-7B-Instruct/snapshots/"
              "a09a35458c702b33eeacc393d103063234e8bc28")
CHAT_QUANT = "bitsandbytes-nf4"


@dataclass
class QueueSample:
    at: float
    depth: int
    active: int


class NativeChatPlayer(Player):
    """AI ENABLED, native hybrid. Thread-safe: many session threads call
    `invoke()`, one worker answers, and the wait is measured."""

    name = "SyMon AI"                 # customer-facing; no upstream branding
    kind = "chat-native-hybrid"
    uses_gpu = True

    def __init__(self, *, baseline_mib: int, tolerance_mib: int = 256):
        sys.path.insert(0, str(HYBRID))
        import gpu_guard                       # noqa: PLC0415 -- deliberately late
        import supervisor as sup               # noqa: PLC0415
        self._guard = gpu_guard
        self._sup_mod = sup
        self.sup = sup.Supervisor(python=CHAT_PY, baseline_mib=baseline_mib,
                                  tolerance_mib=tolerance_mib)
        # ONE condition guards both the queue discipline and the counters, so a
        # request can never be observed as waiting and in service at the same
        # time. A plain Lock could not do this: between `acquire()` returning and
        # the bookkeeping that follows it, the caller held the worker while still
        # counted as waiting, which over-reported queue depth by one.
        #
        # Service order is FIFO by ticket rather than whatever order the OS
        # happens to wake threads in. "Waiting behind the request in service" is
        # only a meaningful phrase if there is an actual order to be behind in,
        # and arbitrary wake order would also change the queue-wait distribution
        # against which the Slice 2 reference was measured.
        self._cv = threading.Condition()
        self._next_ticket = 0
        self._now_serving = 0
        self._abandoned: set[int] = set()
        self._waiting = 0
        self._active = 0
        self._max_depth = 0
        self._max_active = 0
        self._max_in_system = 0
        self._queue_waits: list[float] = []
        self._samples: list[QueueSample] = []
        self.cold_start_s: float | None = None
        self.worker_pid: int | None = None
        self.worker_vram_mib: int | None = None
        self.ready_report: dict | None = None
        self._stop_sampler = threading.Event()
        self._sampler: threading.Thread | None = None

    # ------------------------------------------------------------------ lifecycle
    def start(self, ready_timeout: float = 900.0) -> dict:
        """Load the single worker. The duration is COLD START and is reported
        separately from every steady-state number."""
        t0 = time.monotonic()
        ev = self.sup.start("chat", CHAT_MODEL,
                            extra_env={"SYMON_CHAT_QUANT": CHAT_QUANT},
                            ready_timeout=ready_timeout)
        self.cold_start_s = round(time.monotonic() - t0, 3)
        self.worker_pid = ev["pid"]
        self.worker_vram_mib = ev["proc_vram_mib"]
        self.ready_report = ev["worker_reported"]
        self._sampler = threading.Thread(target=self._sample_queue, daemon=True)
        self._sampler.start()
        return ev

    def reset_level_counters(self) -> None:
        """Zero the per-level peaks between concurrency levels.

        These counters are high-water marks. Across a monotonically rising ramp
        that is harmless -- the max at level N is the level's own max -- but an
        adaptive ramp brackets downward (48 then 40), and a carried-forward peak
        would report level 40 as having queued 47 deep. The queue-wait and
        service percentiles are derived per level from the session results and
        are not affected.
        """
        with self._cv:
            self._max_depth = self._waiting
            self._max_active = self._active
            self._max_in_system = self._waiting + self._active
            self._queue_waits.clear()
            self._samples.clear()
            # Ticket numbers only reset when the queue is genuinely empty.
            # Rewinding them with work in flight would hand two requests the
            # same turn.
            if self._waiting == 0 and self._active == 0:
                self._next_ticket = self._now_serving = 0
                self._abandoned.clear()

    def _release_locked(self) -> None:
        """Hand the worker to the next live ticket.

        Steps over tickets whose owner timed out while queued -- without this a
        single abandoned ticket would wedge everyone behind it forever, which
        would read in the report as a worker hang rather than as a timeout.
        """
        self._now_serving += 1
        while self._now_serving in self._abandoned:
            self._abandoned.discard(self._now_serving)
            self._now_serving += 1
        self._cv.notify_all()

    def stop(self) -> dict:
        self._stop_sampler.set()
        if self._sampler:
            self._sampler.join(timeout=5)
        return self.sup.stop(drain_timeout=60, vram_timeout=60)

    def _sample_queue(self) -> None:
        while not self._stop_sampler.is_set():
            with self._cv:
                self._samples.append(QueueSample(time.time(), self._waiting, self._active))
            self._stop_sampler.wait(0.05)

    # --------------------------------------------------------------------- invoke
    def invoke(self, prompt: str, timeout: float) -> PlayerResult:
        """Queue, wait for the single worker, then time only the inference.

        `latency_s` is queue wait + service time, because that is what the user
        experiences. `queue_wait_s` is broken out so the two can be separated in
        the report -- at concurrency 1 they differ by nothing, and at concurrency
        N the difference is the whole story.
        """
        deadline = time.monotonic() + timeout
        with self._cv:
            ticket = self._next_ticket
            self._next_ticket += 1
            self._waiting += 1
            # Observed here, under the same lock that performs the
            # waiting -> active transition, so depth is exactly the number of
            # requests enqueued and NOT yet in service.
            self._max_depth = max(self._max_depth, self._waiting)
            self._max_in_system = max(self._max_in_system,
                                      self._waiting + self._active)
            t_enqueue = time.monotonic()

            acquired = True
            while ticket != self._now_serving or self._active > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    acquired = False
                    break
                self._cv.wait(remaining)

            if acquired:
                # Atomic hand-over: no observer can ever see this request in
                # both states, and none can see it in neither.
                self._waiting -= 1
                self._active += 1
                self._max_active = max(self._max_active, self._active)
            else:
                self._waiting -= 1
                self._abandoned.add(ticket)
                if self._active == 0 and ticket == self._now_serving:
                    self._abandoned.discard(ticket)
                    self._release_locked()
            t_service = time.monotonic()
            wait_s = t_service - t_enqueue
            self._queue_waits.append(wait_s)

        if not acquired:
            # Never reached the worker at all: the request spent its whole budget
            # queueing. That is a TIMEOUT POLICY outcome, not a capacity failure,
            # and the two must not be aggregated together.
            res = PlayerResult(ok=False, latency_s=wait_s,
                               error=f"queue wait exceeded {timeout}s")
            res.fault_class = "TIMEOUT POLICY / QUEUE ADMISSION"  # type: ignore[attr-defined]
            res.queue_wait_s = wait_s                             # type: ignore[attr-defined]
            return res
        try:
            r = self.sup.request({"type": "generate", "prompt": prompt,
                                  "max_new_tokens": 24},
                                 timeout=max(1.0, timeout - wait_s))
            if r.get("type") != "result":
                res = PlayerResult(ok=False, latency_s=time.monotonic() - t_enqueue,
                                   error=f"worker returned {r.get('type')}: {r.get('error')}")
                res.fault_class = "AI WORKER FAULT"                # type: ignore[attr-defined]
                res.queue_wait_s = wait_s                          # type: ignore[attr-defined]
                return res
            service_s = time.monotonic() - t_service
            res = PlayerResult(
                ok=True,
                latency_s=time.monotonic() - t_enqueue,
                tokens=r.get("completion_tokens"),
                tok_per_s=r.get("tok_per_s"),
                model=self.name,
            )
            res.queue_wait_s = wait_s          # type: ignore[attr-defined]
            res.service_s = service_s          # type: ignore[attr-defined]
            # The worker generates without streaming, so there is no first-token
            # event to time. Reporting a fabricated TTFT would be worse than
            # reporting none.
            res.ttft_s = None
            return res
        except Exception as e:                 # noqa: BLE001
            res = PlayerResult(ok=False, latency_s=time.monotonic() - t_enqueue,
                               error=f"{type(e).__name__}: {e}")
            # Reached the worker but the *inference* exceeded what the queue left
            # of the budget. Distinct again from the two cases above: aggregated
            # they look like one number and mean three different things.
            res.fault_class = ("TIMEOUT POLICY / INFERENCE BUDGET"
                               if isinstance(e, TimeoutError)
                               or "timeout" in str(e).lower()
                               else "AI QUEUE / SERIAL SERVICE")  # type: ignore[attr-defined]
            res.queue_wait_s = wait_s                             # type: ignore[attr-defined]
            return res
        finally:
            with self._cv:
                self._active -= 1
                self._release_locked()

    # ------------------------------------------------------------------ reporting
    def identity(self) -> dict:
        d = {"player": self.name, "kind": self.kind, "uses_gpu": self.uses_gpu,
             "implementation": "native PyTorch + Transformers, BitsAndBytes NF4",
             "interpreter": CHAT_PY, "model_path": CHAT_MODEL, "quantization": CHAT_QUANT,
             "single_worker_per_run": True,
             "legacy_paths_used": {"api_chat": False, "symoneural_llm": False,
                                   "llama_cpp": False, "vllm": False, "gpt_oss": False}}
        if self.ready_report:
            d["worker_reported"] = self.ready_report
        return d

    def metrics(self) -> dict:
        waits_ms = [w * 1000 for w in self._queue_waits]
        return {
            "cold_start_seconds": self.cold_start_s if self.cold_start_s is not None else NOT_AVAILABLE,
            "worker_pid": self.worker_pid if self.worker_pid is not None else NOT_AVAILABLE,
            "worker_process_vram_mib": self.worker_vram_mib if self.worker_vram_mib is not None else NOT_AVAILABLE,
            "worker_load_seconds_internal": (self.ready_report or {}).get("load_s", NOT_AVAILABLE),
            "max_queue_depth": self._max_depth,
            "max_active_ai_requests": self._max_active,
            # Observed directly rather than as max(active) + max(depth): those
            # two maxima can occur at different instants, so their sum is not a
            # figure any request ever experienced.
            "max_total_ai_in_system_observed": self._max_in_system,
            "queue_discipline": "FIFO by ticket; one request in service at a time",
            "queue_wait_ms": percentiles(waits_ms) if waits_ms else NOT_AVAILABLE,
            "queue_samples": len(self._samples),
            "queue_sample_interval_s": 0.05,
            "time_to_first_token_ms": NOT_AVAILABLE,
            "ttft_note": ("the native worker returns a completed generation rather than a "
                          "token stream, so there is no first-token event to time"),
        }
