"""Tests for the multi-coder session surface (R-184).

The interesting assertions are the ones about what the code REFUSES to do: merge answers,
drop a failed coder, call one answer a consensus, or let an unproven adapter be offered.
Those are the requirement; a passing fan-out is only the easy half.
"""
from __future__ import annotations

import asyncio
import unittest

from . import (Answer, PRESETS, agreement, preset_rows, provider_map, providers,
               _normalise, CODER_IDS)


def A(cid, text="", state="completed", error=""):
    return Answer(cid, cid.title(), state, text=text, error=error)


class AgreementTests(unittest.TestCase):
    def test_identical_answers_agree(self):
        r = agreement([A("symon", "1,2,3"), A("claude", "1,2,3"), A("codex", "1,2,3")])
        self.assertTrue(r["agree"])
        self.assertEqual(r["distinct"], 1)

    def test_whitespace_is_not_disagreement(self):
        r = agreement([A("symon", "1, 2, 3"), A("claude", " 1,  2,\n3 ")])
        self.assertTrue(r["agree"])

    def test_separator_spacing_is_not_disagreement(self):
        # REGRESSION, found by the first real run on 2026-09-02: Symon answered
        # "1,2,3,4,5,6,7,8,9,10" and Claude answered "1, 2, 3, 4, 5, 6, 7, 8, 9, 10".
        # Those are the same answer. Reporting a disagreement would have sent the operator
        # to a decision he should never have been asked to make.
        r = agreement([A("symon", "1,2,3,4,5,6,7,8,9,10"),
                       A("claude", "1, 2, 3, 4, 5, 6, 7, 8, 9, 10")])
        self.assertTrue(r["agree"], "separator spacing must not read as disagreement")

    def test_spacing_fix_does_not_hide_a_real_disagreement(self):
        # The normaliser must not become so eager that it merges genuinely different
        # answers -- that would hide exactly what R-184 exists to surface.
        r = agreement([A("symon", "1,2,3"), A("claude", "1,2,4")])
        self.assertFalse(r["agree"])
        self.assertEqual(r["distinct"], 2)

    def test_different_answers_disagree_and_keep_both(self):
        r = agreement([A("symon", "count up"), A("claude", "count down")])
        self.assertFalse(r["agree"])
        self.assertEqual(r["distinct"], 2)
        self.assertEqual(len(r["proposals"]), 2)
        # Every proposal survives. Nothing is merged, nothing is ranked, and no winner is
        # marked -- that decision is the operator's under R-184.
        texts = {p["text"] for p in r["proposals"]}
        self.assertEqual(texts, {"count up", "count down"})
        for p in r["proposals"]:
            self.assertNotIn("winner", p)
            self.assertNotIn("score", p)

    def test_one_answer_is_not_a_consensus(self):
        # `agree` must be None, never True: one opinion is not agreement.
        self.assertIsNone(agreement([A("symon", "1,2,3")])["agree"])

    def test_failed_coder_does_not_count_as_assent(self):
        # A silent coder must not be read as agreeing. Two completed + one failed compares
        # only the two, and the failure never becomes a third vote.
        r = agreement([A("symon", "x"), A("claude", "x"),
                       A("codex", "", state="failed", error="boom")])
        self.assertTrue(r["agree"])
        self.assertEqual(r["distinct"], 1)

    def test_two_failures_leave_nothing_to_compare(self):
        r = agreement([A("symon", "", state="failed"),
                       A("claude", "", state="timed_out")])
        self.assertIsNone(r["agree"])


class PresetTests(unittest.TestCase):
    def test_all_seven_selections_exist(self):
        self.assertEqual(len(PRESETS), 7)
        kinds = [r["kind"] for r in preset_rows()]
        self.assertEqual(kinds.count("single"), 3)
        self.assertEqual(kinds.count("dual"), 3)
        self.assertEqual(kinds.count("tri"), 1)

    def test_every_preset_is_listed_even_when_unavailable(self):
        # Hiding an unavailable combination would lose the owner's requirement. Each row is
        # always present; only `available` changes.
        rows = preset_rows()
        self.assertEqual(len(rows), 7)
        for r in rows:
            self.assertIn("available", r)
            if not r["available"]:
                self.assertTrue(r["detail"], "an unavailable preset must say why")

    def test_owner_named_combinations_are_present(self):
        keys = {r["key"] for r in preset_rows()}
        for k in ("symon", "claude", "codex", "symon+claude", "codex+symon",
                  "codex+claude", "symon+claude+codex"):
            self.assertIn(k, keys)


class ProviderTests(unittest.TestCase):
    def test_three_coders(self):
        self.assertEqual(len(providers()), 3)
        self.assertEqual({p.coder_id for p in providers()}, set(CODER_IDS))

    def test_unavailable_provider_states_a_reason(self):
        for p in providers():
            if not p.available:
                self.assertTrue(p.detail.strip(), f"{p.coder_id} unavailable with no reason")

    def test_codex_is_not_offered_without_a_proven_boundary(self):
        # The incoming plan: an adapter that cannot enforce the answer-only boundary is
        # reported unavailable. This asserts we did not ship it as working because one
        # clean probe came back.
        c = provider_map()["codex"]
        if not c.answer_only_proven:
            self.assertFalse(c.available,
                             "codex offered as available without a proven answer-only boundary")


class UnavailableRowTests(unittest.IsolatedAsyncioTestCase):
    async def test_unavailable_coder_still_gets_a_row(self):
        from . import _ask_one
        pm = provider_map()
        target = next((c for c in CODER_IDS if not pm[c].available), None)
        if target is None:
            self.skipTest("all providers available on this box")
        a = await _ask_one(target, "hi", 5.0, "/tmp")
        self.assertEqual(a.state, "unavailable")
        self.assertTrue(a.error)
        # The row survives so a 3-coder run cannot silently become a 2-coder run.
        self.assertEqual(a.coder_id, target)


if __name__ == "__main__":
    unittest.main()


class DebateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from . import Session, Answer, _remember
        import time
        self.s = Session("debate-fixture", "Choose an implementation", ["symon", "claude"],
                         time.time(), answers=[Answer("symon", "Symon", "completed", "Option A"),
                                               Answer("claude", "Claude", "completed", "Option B")],
                         state="done", fixture=True)
        _remember(self.s)

    async def test_round_preserves_positions_and_requires_a_new_user_decision(self):
        from . import run_debate, record_decision, Answer
        from unittest.mock import patch, AsyncMock
        self.s.decision = "symon"
        calls = []
        async def answer(coder, prompt, deadline, scratch):
            calls.append((coder, prompt))
            return Answer(coder, coder.title(), "completed", "Revised " + coder)
        with patch(f"{__package__}._ask_one", side_effect=answer):
            await run_debate(self.s, "Explain tradeoffs", 0)
        self.assertEqual(calls[0][1], calls[1][1])
        for value in ("Option A", "Option B", "symon", "claude", "Explain tradeoffs"):
            self.assertIn(value, calls[0][1])
        self.assertEqual([a.text for a in self.s.answers], ["Option A", "Option B"])
        self.assertEqual(self.s.rounds[0].prompt, calls[0][1])
        self.assertEqual(self.s.decision, "")
        with self.assertRaises(ValueError):
            record_decision(self.s, "claude", 0)
        record_decision(self.s, "claude", 1)
        self.assertEqual(self.s.decisions[-1]["round_number"], 1)
        self.assertEqual(self.s.decision, "claude")

    async def test_duplicate_round_and_bounded_limit_do_not_dispatch(self):
        from . import run_debate, Answer, MAX_DEBATE_ROUNDS
        from unittest.mock import patch
        async def answer(coder, *args):
            return Answer(coder, coder.title(), "completed", "same")
        with patch(f"{__package__}._ask_one", side_effect=answer) as ask:
            for n in range(MAX_DEBATE_ROUNDS):
                await run_debate(self.s, "Discuss", n)
            count = ask.call_count
            for version in (0, MAX_DEBATE_ROUNDS):
                with self.assertRaises(ValueError):
                    await run_debate(self.s, "Discuss", version)
            self.assertEqual(ask.call_count, count)
            self.assertEqual(self.s.decision, "")

    async def test_inflight_round_refuses_second_round_and_decision(self):
        import asyncio
        from . import run_debate, record_decision, Answer
        from unittest.mock import patch
        entered, release = asyncio.Event(), asyncio.Event()
        async def answer(coder, *args):
            entered.set()
            await release.wait()
            return Answer(coder, coder.title(), "completed", coder)
        with patch(f"{__package__}._ask_one", side_effect=answer):
            task = asyncio.create_task(run_debate(self.s, "Discuss", 0))
            await entered.wait()
            with self.assertRaises(ValueError):
                await run_debate(self.s, "duplicate", 1)
            with self.assertRaises(ValueError):
                record_decision(self.s, "symon", 1)
            release.set()
            await task
        self.assertEqual(len(self.s.rounds), 1)

    async def test_failure_stays_attributed_and_cannot_be_selected(self):
        from . import run_debate, record_decision, Answer
        from unittest.mock import patch
        async def answer(coder, *args):
            if coder == "claude":
                return Answer(coder, "Claude", "timed_out", error="fixture deadline")
            return Answer(coder, "Symon", "completed", "Option A")
        with patch(f"{__package__}._ask_one", side_effect=answer):
            await run_debate(self.s, "Discuss", 0)
        self.assertEqual([a.coder_id for a in self.s.rounds[0].answers], self.s.coder_ids)
        self.assertEqual(self.s.rounds[0].answers[1].state, "timed_out")
        with self.assertRaises(ValueError):
            record_decision(self.s, "claude", 1)
        self.assertIsNone(self.s.to_dict()["rounds"][0]["agree"])

    async def test_cancellation_retains_round_and_every_participant(self):
        import asyncio
        from . import run_debate
        from unittest.mock import patch
        entered = asyncio.Event()
        async def answer(*args):
            entered.set()
            await asyncio.Event().wait()
        with patch(f"{__package__}._ask_one", side_effect=answer):
            task = asyncio.create_task(run_debate(self.s, "Discuss", 0))
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(self.s.rounds[0].state, "canceled")
        self.assertEqual(len(self.s.rounds[0].answers), 2)
        self.assertTrue(all(a.state == "canceled" for a in self.s.rounds[0].answers))

    async def test_blank_or_oversized_context_is_rejected_without_dispatch(self):
        from . import run_debate, MAX_DEBATE_CONTEXT_CHARS
        from unittest.mock import patch
        with patch(f"{__package__}._ask_one") as ask:
            with self.assertRaises(ValueError):
                await run_debate(self.s, "  ", 0)
            self.s.answers[0].text = "x" * MAX_DEBATE_CONTEXT_CHARS
            with self.assertRaises(ValueError):
                await run_debate(self.s, "Discuss", 0)
            ask.assert_not_called()
        self.assertEqual(self.s.rounds, [])


class AdapterAndBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_codex_jsonl_contract_uses_completed_item_and_turn(self):
        import json
        from unittest.mock import patch, AsyncMock
        from . import _ask_codex
        output = "\n".join(json.dumps(x) for x in [
            {"type":"item.completed","item":{"type":"agent_message","text":"Answer"}},
            {"type":"turn.completed","usage":{"output_tokens":2}}])
        with patch(f"{__package__}._run", new=AsyncMock(return_value=(0,output,""))) as run:
            answer = await _ask_codex("test", 1, "/tmp")
        self.assertEqual(answer.text, "Answer")
        self.assertEqual(answer.usage["output_tokens"], 2)
        self.assertEqual(run.call_args.args[0][1:4], ["-a", "never", "exec"])
        with patch(f"{__package__}._run", new=AsyncMock(return_value=(0,'{"type":"turn.completed"}',""))):
            answer = await _ask_codex("test", 1, "/tmp")
        self.assertEqual(answer.state, "failed")

    async def test_cancel_reaps_provider_process(self):
        import asyncio, sys, os, tempfile
        from pathlib import Path
        from . import _run
        with tempfile.TemporaryDirectory() as d:
            pidfile = Path(d)/"pid"
            script = "import os,time;open('pid','w').write(str(os.getpid()));time.sleep(30)"
            task = asyncio.create_task(_run([sys.executable,"-B","-c",script],"",d,60))
            for _ in range(100):
                if pidfile.exists(): break
                await asyncio.sleep(.01)
            self.assertTrue(pidfile.exists())
            pid = int(pidfile.read_text())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
            with self.assertRaises(ProcessLookupError): os.kill(pid,0)


class DebateRouteBoundaryTests(unittest.TestCase):
    def test_debate_inherits_local_router_guard(self):
        from fastapi import FastAPI, Depends
        from fastapi.testclient import TestClient
        from api import _require_local
        from .routes import router
        app = FastAPI()
        app.include_router(router,prefix="/local/coders",dependencies=[Depends(_require_local)])
        body = {"clarification":"test", "expected_round":0}
        local = TestClient(app, client=("127.0.0.1",1234))
        for header in ("X-Forwarded-For","X-Forwarded-Host","X-Real-IP"):
            response = local.post("/local/coders/session/test/debate",json=body,headers={header:"198.51.100.1"})
            self.assertEqual(response.status_code,404)
        remote = TestClient(app,client=("198.51.100.1",1234))
        self.assertEqual(remote.get("/local/coders/providers").status_code,404)
        self.assertEqual(local.get("/local/coders/providers").status_code,200)
