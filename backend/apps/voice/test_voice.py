#!/usr/bin/env python3
"""Tests for SyMoNeuRaL Voice. Stdlib `unittest`, and they run with the network unplugged.

    python3 backend/apps/voice/test_voice.py
    cd backend && python3 -m pytest apps/voice -q

Three properties this suite is built for, beyond checking the code works.

**It must SKIP, not fail, on a fresh checkout.** `contrib/` and `backend/models/` are both
gitignored, so `whisper-cli` and `symoneural-listen-base-en.bin` are absent from a clone. A suite that went
red there would be a false alarm the next agent has to disprove before they can trust
`pytest apps/`, and this repo has already paid for that lesson five times. Everything that
needs the engine lives in `EngineTests` and skips as a unit; everything above it is pure.

**It is a tripwire on the trap that makes this surface look like it works.** `whisper-cli`
exits **0** on a file it could not read, and the browser's own recording format -- WebM/Opus --
is one of those files. So `test_undecodable_audio_is_an_error_not_an_empty_transcript` and
`test_browser_webm_opus_transcribes_through_the_transcode` are the two assertions that matter
most here: the first says a failure is reported, the second says the fix is doing the work.

**It is a tripwire on a fail-open.** `test_no_configuration_can_reach_the_engine` asserts that
with the surface off, every route refuses -- including on a box where the engine is installed
and working, which is the only configuration where a fail-open would go unnoticed.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import voice  # noqa: E402
from voice import asr, tts  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

TOKEN = "test-token-not-a-real-secret"
ON = {"SYM_VOICE_ENABLED": "1", "SYM_VOICE_TOKEN": TOKEN}
AUTH = {"X-Sym-Token": TOKEN}

# Every SYM_VOICE_* name this package reads. Cleared before each case so a value set in the
# shell -- or by a peer suite -- cannot make a gate test pass for the wrong reason.
_OWN_ENV = ("SYM_VOICE_ENABLED", "SYM_VOICE_TOKEN", "SYM_VOICE_THREADS",
            "SYM_VOICE_CONCURRENCY", "SYM_VOICE_TIMEOUT_S", "SYM_VOICE_TRANSCODE_TIMEOUT_S",
            "SYM_WHISPER_CLI", "SYM_WHISPER_MODEL", "SYM_FFMPEG")


def clean_env(**overrides: str) -> mock._patch:
    env = {k: v for k, v in os.environ.items() if k not in _OWN_ENV}
    env.update(overrides)
    return mock.patch.dict(os.environ, env, clear=True)


def client() -> TestClient:
    """A throwaway app carrying only this router. Deliberately not `backend/api.py`: that file
    is contended, and the scope of these tests is the router and the engine, not the mount
    order of the real service."""
    app = FastAPI()
    app.include_router(voice.router, prefix="/api/voice")
    return TestClient(app)


class GateTests(unittest.TestCase):
    """The two switches, and the header. No audio is touched by any of these."""

    def test_both_variables_are_required(self):
        for env in ({}, {"SYM_VOICE_ENABLED": "1"}, {"SYM_VOICE_TOKEN": TOKEN}):
            with clean_env(**env):
                self.assertFalse(voice.enabled(), env)
        with clean_env(**ON):
            self.assertTrue(voice.enabled())

    def test_enabled_is_the_literal_string_one(self):
        """`true`/`yes`/`on` leave the surface off and say nothing. This is the single most
        reported confusion about `SYM_ASIC_ENABLED`, and it is consistent here on purpose --
        so the test states the behaviour rather than letting somebody 'fix' it."""
        for value in ("true", "True", "yes", "on", "0", " 1", ""):
            with clean_env(SYM_VOICE_ENABLED=value, SYM_VOICE_TOKEN=TOKEN):
                self.assertFalse(voice.enabled(), value)

    def test_token_compare_refuses_empty_and_wrong(self):
        with clean_env(**ON):
            self.assertTrue(voice.token_ok(TOKEN))
            for bad in (None, "", "wrong", TOKEN[:-1], TOKEN + "x"):
                self.assertFalse(voice.token_ok(bad), repr(bad))

    def test_no_token_configured_refuses_every_presented_token(self):
        with clean_env(SYM_VOICE_ENABLED="1"):
            for presented in (None, "", "anything"):
                self.assertFalse(voice.token_ok(presented))

    def test_no_configuration_can_reach_the_engine(self):
        """With the surface off, all three routes refuse -- and this runs whether or not the
        engine is installed, because a fail-open on a working box is the case that would
        never be noticed."""
        with clean_env():
            c = client()
            self.assertEqual(c.get("/api/voice/state").status_code, 503)
            self.assertEqual(c.post("/api/voice/speak", headers=AUTH).status_code, 503)
            r = c.post("/api/voice/transcribe", headers=AUTH,
                       files={"audio": ("a.wav", b"not audio", "audio/wav")})
            self.assertEqual(r.status_code, 503)
            self.assertIn("SYM_VOICE_ENABLED", r.json()["detail"])
            self.assertIn("SYM_VOICE_TOKEN", r.json()["detail"])

    def test_enabled_but_unauthenticated_is_401(self):
        with clean_env(**ON):
            c = client()
            for headers in ({}, {"X-Sym-Token": "wrong"}):
                r = c.post("/api/voice/transcribe", headers=headers,
                           files={"audio": ("a.wav", b"not audio", "audio/wav")})
                self.assertEqual(r.status_code, 401, headers)
            # /state is open once enabled: it publishes presence and absence, and there is no
            # key material in this package. apps/gateway is the precedent.
            self.assertEqual(c.get("/api/voice/state").status_code, 200)

    def test_an_empty_upload_is_rejected_before_any_subprocess(self):
        with clean_env(**ON):
            r = client().post("/api/voice/transcribe", headers=AUTH,
                              files={"audio": ("a.wav", b"", "audio/wav")})
            self.assertEqual(r.status_code, 400)
            self.assertIn("empty", r.json()["detail"])


class SpeakTests(unittest.TestCase):
    """The half that is not built must say so, and must never return audio."""

    def test_speak_is_503_and_names_the_command(self):
        with clean_env(**ON):
            r = client().post("/api/voice/speak", headers=AUTH)
            self.assertEqual(r.status_code, 503)
            detail = r.json()["detail"]
            self.assertIn("piper-tts", detail)
            self.assertNotIn("audio/wav", r.headers.get("content-type", ""))

    def test_nothing_that_speaks_is_installed_and_that_is_probed_not_assumed(self):
        """If somebody installs an engine, `state()` changes without a code change. The point
        of the assertion is that `available` is False for the right reason."""
        half = tts.state()
        self.assertFalse(half["available"])
        self.assertIn("unmeasured", half["latency"])
        if tts.engine() is None:
            self.assertIn("no speech synthesiser", half["problem"])
        else:
            self.assertIn("no synthesis path", half["problem"])

    def test_the_venv_path_follows_the_asicminer_convention(self):
        self.assertEqual(tts.VENV_PIPER, HERE / ".venv" / "bin" / "piper")


class UnitTests(unittest.TestCase):
    """The rack row. `api.py`'s `Unit` model is not imported -- importing `api` builds the
    whole FastAPI app -- so the contract is asserted against its literal shape instead."""

    KEYS = {"id", "label", "slot", "state", "bus", "href", "spec", "detail"}

    def test_status_matches_the_unit_model(self):
        u = voice.status()
        self.assertEqual(set(u), self.KEYS)
        self.assertEqual(u["bus"], "cpu")
        self.assertIn(u["state"], {"ready", "busy", "queued", "offline"})
        self.assertTrue(all(isinstance(v, str) for v in u.values()))

    def test_the_row_is_never_queued(self):
        """`queued` means waiting for the card. This surface never does, which is the whole
        argument for it, so publishing `queued` would contradict its own spec line."""
        self.assertNotEqual(voice.status()["state"], "queued")

    def test_the_label_is_not_a_prefix_of_another_rack_name(self):
        """`tests/frontend.mjs` asserts that no rack name is a prefix of another -- the bug
        that made `SyMoNeuRaL Miner` read as the general case of `SyMoNeuRaL Miner GPU`. This
        catches it here rather than in a browser suite owned by another session."""
        others = ["SyMoNeuRaL Chat", "SyMoNeuRaL Image", "SyMoNeuRaL Remix",
                  "SyMoNeuRaL RavenCalc", "SyMoNeuRaL Reinforce", "SyMoNeuRaL Miner",
                  "SyMoNeuRaL Tuner + Guide", "SyMoNeuRaL Coder", "SyMoNeuRaL Gateway",
                  "SyMoNeuRaL Project"]
        mine = voice.status()["label"]
        for other in others:
            self.assertFalse(mine.startswith(other), other)
            self.assertFalse(other.startswith(mine), other)

    def test_a_missing_engine_is_offline_and_names_the_path(self):
        missing = HERE / "no-such-whisper-cli"
        with mock.patch.object(asr, "WHISPER_CLI", missing):
            u = voice.status()
            self.assertEqual(u["state"], "offline")
            self.assertIn(str(missing), u["detail"])

    def test_missing_weights_are_reported_separately_from_a_missing_binary(self):
        """Two artefacts, two different fixes. `offline · something is missing` would send the
        reader to rebuild whisper.cpp when what they need is a 141 MB download."""
        if not asr.WHISPER_CLI.is_file():
            self.skipTest("whisper-cli absent; the binary clause is already what fires")
        with mock.patch.object(asr, "MODEL", HERE / "no-such-model.bin"):
            _ok, why = asr.installed()
            self.assertIn("weights missing", why)


class WindowTests(unittest.TestCase):
    """The 30-second window is the shape of the whole route, so the arithmetic is asserted."""

    def test_cost_is_flat_inside_a_window_and_steps_between(self):
        self.assertEqual(asr.windows_for(0.4), 1)
        self.assertEqual(asr.windows_for(29.9), 1)
        self.assertEqual(asr.windows_for(30.0), 1)
        self.assertEqual(asr.windows_for(30.1), 2)
        self.assertEqual(asr.windows_for(60.0), 2)
        self.assertEqual(asr.windows_for(60.1), 3)

    def test_zero_length_audio_still_costs_one_window(self):
        """A page counting windows must never render 0 of 0."""
        self.assertEqual(asr.windows_for(0.0), 1)


class SemaphoreTests(unittest.TestCase):
    """The concurrency cap, and the reason it is not a module-level singleton."""

    def test_the_cap_is_two_by_default(self):
        async def go():
            return asr._sem()._value
        self.assertEqual(asyncio.run(go()), asr.CONCURRENCY)
        self.assertEqual(asr.CONCURRENCY, 2)

    def test_a_second_event_loop_gets_its_own_semaphore(self):
        """`asyncio.Semaphore` binds to the loop that first waits on it and raises if another
        touches it. A module-level singleton therefore works in the service (one loop, for
        ever) and breaks under any suite that calls `asyncio.run` twice -- which this one does
        in the very next test. This is that bug, asserted."""
        async def acquire_and_release():
            sem = asr._sem()
            async with sem:
                pass
            return sem
        # Both objects are kept alive for the comparison. Comparing `id()` of two released
        # objects is not the same assertion: CPython reuses the address of a freed object, so
        # that version passed only by luck and failed when it did not get any.
        first = asyncio.run(acquire_and_release())
        second = asyncio.run(acquire_and_release())
        self.assertIsNot(first, second)

    def test_queue_depth_outside_a_loop_is_zero_rather_than_an_error(self):
        """`status()` is called from `/api/status`, which the rack renders. A surface that
        raised here would take the whole status endpoint down with it."""
        self.assertEqual(asr.queue_depth(), 0)


def _have_engine() -> tuple[bool, str]:
    ok, why = asr.installed()
    return ok, why


@unittest.skipUnless(_have_engine()[0], f"engine not installed: {_have_engine()[1]}")
class EngineTests(unittest.TestCase):
    """The real thing, against the real binary. Skipped as a unit on a fresh checkout.

    Fixtures are cut here rather than committed: `contrib/whisper.cpp/samples/jfk.wav` is
    gitignored along with the rest of `contrib/`, so a committed derivative would be a binary
    blob in git whose provenance the next reader could not check.
    """

    @classmethod
    def setUpClass(cls):
        sample = asr.ROOT / "contrib" / "whisper.cpp" / "samples" / "jfk.wav"
        if not sample.is_file():
            raise unittest.SkipTest(f"no sample audio at {sample}")
        if shutil.which("ffmpeg") is None:
            raise unittest.SkipTest("ffmpeg not on PATH")
        cls._tmp = tempfile.TemporaryDirectory(prefix="symvoice-tests-")
        d = cls.dir = pathlib.Path(cls._tmp.name)
        cls.speech_wav = sample
        cls.speech_webm = d / "speech.webm"
        cls.silence_wav = d / "silence.wav"
        cls.garbage_webm = d / "garbage.webm"
        # WebM/Opus, which is what Chrome's MediaRecorder produces and what this build of
        # whisper.cpp cannot read at all.
        cls._ffmpeg("-i", str(sample), "-c:a", "libopus", "-f", "webm", str(cls.speech_webm))
        cls._ffmpeg("-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t", "3",
                    str(cls.silence_wav))
        cls.garbage_webm.write_bytes(bytes(range(256)) * 8)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    @staticmethod
    def _ffmpeg(*args: str) -> None:
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args],
                       check=True, capture_output=True)

    def transcribe(self, path: pathlib.Path, name: str | None = None):
        with clean_env(**ON):
            return client().post(
                "/api/voice/transcribe", headers=AUTH,
                files={"audio": (name or path.name, path.read_bytes(),
                                 "application/octet-stream")})

    def test_browser_webm_opus_transcribes_through_the_transcode(self):
        """THE FIX. Handed this file directly, `whisper-cli` yields nothing and exits 0; the
        unconditional `ffmpeg -ar 16000 -ac 1` is what makes the browser's own format work."""
        r = self.transcribe(self.speech_webm)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("fellow americans", body["text"].lower())
        self.assertGreater(body["transcode_ms"], 0)
        self.assertEqual(body["windows"], 1)
        self.assertAlmostEqual(body["audio_s"], 11.0, delta=0.2)

    def test_the_raw_format_really_does_fail_which_is_why_the_transcode_is_unconditional(self):
        """The premise of the test above, asserted against the tool rather than trusted. If a
        future whisper.cpp gains an Opus decoder this goes red -- and that is the moment to
        re-read the branch, not to delete it."""
        proc = subprocess.run(
            [str(asr.WHISPER_CLI), "-m", str(asr.MODEL), "-t", "2", "-nt",
             "-f", str(self.speech_webm)], capture_output=True)
        self.assertEqual(proc.returncode, 0, "the trap is that it exits 0")
        self.assertEqual(proc.stdout.strip(), b"", "it produced a transcript from Opus")

    def test_undecodable_audio_is_an_error_not_an_empty_transcript(self):
        r = self.transcribe(self.garbage_webm)
        self.assertEqual(r.status_code, 400, r.text)
        self.assertIn("could not be decoded", r.json()["detail"])
        # The tool's own words are surfaced. A bare "bad request" here is what sends somebody
        # to debug their microphone.
        self.assertIn("matroska", r.json()["detail"].lower())

    def test_silence_returns_a_word_and_a_peak_of_zero(self):
        """Whisper invents a word on silence. That is why `peak` is published: it is a real
        measurement of the audio, and it is what lets a caller tell 'nobody spoke' from 'the
        model heard something' without this route applying a filter to the transcript."""
        r = self.transcribe(self.silence_wav)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["peak"], 0.0)
        self.assertNotEqual(body["text"], "", "silence is not the empty-output case")

    def test_speech_has_a_peak_well_above_silence(self):
        r = self.transcribe(self.speech_wav)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertGreater(r.json()["peak"], 0.1)

    def test_a_lying_filename_does_not_change_the_outcome(self):
        """The suffix comes from the caller, so it is sanitised and then ignored -- ffmpeg
        sniffs the container. Opus announced as `.wav` must still transcribe."""
        r = self.transcribe(self.speech_webm, name="../../etc/passwd.wav")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("fellow americans", r.json()["text"].lower())

    def test_every_stage_reports_its_own_milliseconds(self):
        body = self.transcribe(self.speech_wav).json()
        for key in ("transcode_ms", "asr_ms", "queued_ms", "ms"):
            self.assertIsInstance(body[key], int, key)
        self.assertGreaterEqual(
            body["ms"], body["transcode_ms"] + body["asr_ms"] + body["queued_ms"])
        self.assertEqual(body["engine"].startswith("whisper.cpp"), True)
        self.assertIn("GGML_CUDA=OFF", body["engine"])

    def test_it_takes_no_gpu_lease(self):
        """The claim the rack row makes, asserted against behaviour rather than against the
        source. A first version grepped these files for `gpu-governor` and went red on its own
        documentation -- every module here explains at length why it takes no lease, so the
        string is all over the prose. What matters is that a transcription leaves the mutex
        exactly as it found it, including while another surface is holding it."""
        lock = asr.ROOT / "run" / "gpu.lock.d"
        holder = lock / "holder"
        before = (lock.is_dir(), holder.read_bytes() if holder.is_file() else None)
        self.assertEqual(self.transcribe(self.silence_wav).status_code, 200)
        after = (lock.is_dir(), holder.read_bytes() if holder.is_file() else None)
        self.assertEqual(before, after,
                         "a transcription changed the state of the GPU mutex")

    def test_concurrency_never_exceeds_the_cap(self):
        """Three at once on a 2-slot semaphore. The assertion is on the maximum observed
        in-flight count, which is the property; the timing is not asserted, because a loaded
        box would make that flaky and this suite has to pass under the fleet."""
        async def go():
            observed = []

            async def sample():
                for _ in range(200):
                    observed.append(asr.in_flight())
                    await asyncio.sleep(0.01)

            async def one():
                with tempfile.TemporaryDirectory() as tmp:
                    await asr.transcribe(self.silence_wav, pathlib.Path(tmp))

            watcher = asyncio.create_task(sample())
            await asyncio.gather(*(one() for _ in range(3)))
            watcher.cancel()
            return max(observed or [0])

        peak = asyncio.run(go())
        self.assertGreater(peak, 0, "the sampler never saw a transcription running")
        self.assertLessEqual(peak, asr.CONCURRENCY)
        self.assertEqual(asr.in_flight(), 0, "the in-flight counter leaked")

    def test_probe_wav_reads_the_file_rather_than_trusting_the_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "x.wav"
            asyncio.run(asr.transcode(self.speech_webm, out))
            with wave.open(str(out)) as w:
                self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()),
                                 (16000, 1, 2))
            seconds, peak = asr.probe_wav(out)
            self.assertAlmostEqual(seconds, 11.0, delta=0.2)
            self.assertGreater(peak, 0.1)

    def test_state_publishes_what_is_installed_and_what_is_not(self):
        with clean_env(**ON):
            body = client().get("/api/voice/state").json()
        self.assertTrue(body["asr"]["available"])
        self.assertEqual(body["asr"]["model"], asr.MODEL.name)
        self.assertFalse(body["tts"]["available"])
        self.assertIn("never", body["gpu"])
        self.assertEqual(body["unit"]["bus"], "cpu")


if __name__ == "__main__":
    unittest.main(verbosity=2)
