#!/usr/bin/env python3
"""Capacity Lab CLI: run / clear / list.

FIND SERVER LIMIT is deliberately absent -- it is safe-gated until the
high-load ramp is separately approved.
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capacity_lab.harness import Harness, clear_run_data
from capacity_lab.core import known_run_ids, REPORT_DIR

def main() -> int:
    ap = argparse.ArgumentParser(prog="capacity-lab")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--users", type=int, default=2)
    r.add_argument("--ai", choices=["on", "off"], default="off")
    r.add_argument("--scenario", default="transaction")
    r.add_argument("--base-url", default="http://127.0.0.1:8800")
    r.add_argument("--timeout", type=float, default=120.0)
    r.add_argument("--sample-interval", type=float, default=0.05,
                   dest="sample_interval",
                   help="GPU/system sampling interval in seconds")
    r.add_argument("--json", action="store_true")
    c = sub.add_parser("clear"); c.add_argument("run_id")
    sub.add_parser("list")
    a = ap.parse_args()

    if a.cmd == "list":
        for rid in known_run_ids():
            print(rid)
        return 0
    if a.cmd == "clear":
        print(json.dumps(clear_run_data(a.run_id), indent=2)); return 0

    if a.users > 2:
        print(f"REFUSED: slice 1 is capped at 2 concurrent users (asked {a.users}).",
              file=sys.stderr)
        print("The 4/6/8/10/16/24/32/48/64 presets and FIND SERVER LIMIT are "
              "safe-gated until the ramp is approved.", file=sys.stderr)
        return 3

    rep = Harness(base_url=a.base_url, scenario=a.scenario, ai_mode=a.ai,
                  users=a.users, timeout=a.timeout,
                  sample_interval=a.sample_interval).run()
    if a.json:
        print(json.dumps(rep, indent=2, default=str))
    else:
        m = rep.get("measurements")
        print(f"run_id         : {rep['run_id']}")
        print(f"ai_mode        : {rep['ai_mode']}   scenario: {rep['scenario']}")
        print(f"classification : {rep['classification']}")
        if rep.get("runnable"):
            s = rep["sessions"]
            print(f"sessions       : requested={s['requested']} started={s['started']} "
                  f"completed={s['completed']} failed={s['failed']}")
            print(f"max concurrency: {rep['actual_max_concurrency']}")
            print(f"session ms     : {m['application']['session_latency_ms']}")
        else:
            print(f"unavailable    : {rep['unavailable_reason']}")
        print(f"report         : {rep.get('report_path')}")
    return 0 if rep.get("classification") in ("PASS", "NOT AVAILABLE") else 1

if __name__ == "__main__":
    sys.exit(main())
