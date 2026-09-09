#!/usr/bin/env python3
"""End-to-end smoke test for the SyMoNeuRaL API. Exits non-zero if anything is broken.

    python3 tools/smoke.py              # the standard run, about 60 s
    python3 tools/smoke.py --quick      # skip the slow GPU checks (image render, lease proof)
    python3 tools/smoke.py --json

You do not need to know anything about this repository to run this. It takes no arguments
that matter, reads nothing from your shell environment, and needs no credentials. Run it from
anywhere; it locates the repo from its own path.

## What "pass" means here

Every check reports **PASS**, **FAIL** or **SKIP**, and a SKIP is printed as loudly as a
failure with the reason attached. That is deliberate. This repository has shipped a surface
whose eighteen checks were green while its chat page was dead on arrival, and a silent skip
that leaves a green result is the exact failure the whole commissioning exercise exists to
prevent. A skipped check is never counted as a pass.

The exit code is 1 if any check FAILED. Skips alone do not fail the run -- but they are
listed again at the end so nobody can miss them.

## Two ports, and why both are checked

  * `127.0.0.1:8800` is the API itself.
  * `https://symoneural.com` (resolved to this box) is the path a visitor takes: the web
    server, the published document root, and the reverse proxy in front of the API.

**Checking only the first is how a broken site passes its own tests.** As of 2026-09-09 the
public `/api/*` returns 502 while `:8800` returns 200, because the Caddyfile routes `/api/*`
through a gateway on :8000 that is disabled by design. That is a real outage of every
documented surface, and this script is red until it is decided -- see PHASE5 §0 and RUNBOOK.md.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for cand in (here, *here.parents):
        if (cand / "backend" / "api.py").is_file():
            return cand
    raise SystemExit(f"repo root not found above {here}: no backend/api.py marker")


ROOT = _repo_root()
API = "http://127.0.0.1:8800"
PUBLIC = "https://symoneural.com"
PUBLIC_IP = "127.0.0.1"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results: list[dict] = []


def record(name: str, state: str, detail: str = "") -> str:
    results.append({"check": name, "state": state, "detail": detail})
    mark = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}[state]
    print(f"  [{mark}] {name}" + (f"\n         {detail}" if detail else ""))
    return state


# --------------------------------------------------------------------- transport
def curl(url: str, timeout: float = 45.0) -> tuple[int, str, int]:
    """Fetch a public URL through curl, pinning DNS to this box.

    Not urllib, and the reason is worth writing down: the web server requires SNI, and a
    Python SSL context with `check_hostname = False` sends no `server_hostname`, so the
    handshake dies with `TLSV1_ALERT_INTERNAL_ERROR`. The first version of this check
    reported that transport failure as "the public site is broken" -- the right conclusion
    for the wrong reason, which is worse than a wrong conclusion because it looks like
    evidence. `curl --resolve` keeps the hostname (so SNI is correct) while pointing the
    connection at 127.0.0.1.

    Returns (http_code, content_type, bytes). code 0 means curl itself could not connect.
    """
    r = subprocess.run(
        # Pipe-delimited, NOT space-delimited. `%{content_type}` is "text/html; charset=utf-8"
        # -- it contains a space, so splitting on whitespace put the charset where the byte
        # count should be and every public check silently reported code 0. An empty
        # content_type on a 502 broke it the other way, by yielding too few fields.
        ["curl", "-sk", "-o", "/dev/null",
         "-w", "%{http_code}|%{content_type}|%{size_download}",
         "--max-time", str(int(timeout)), "--resolve", f"symoneural.com:443:{PUBLIC_IP}", url],
        capture_output=True, text=True, timeout=timeout + 15)
    parts = r.stdout.strip().split("|")
    if len(parts) != 3:
        return 0, "", 0
    try:
        return int(parts[0]), parts[1].split(";")[0].strip(), int(parts[2] or 0)
    except ValueError:
        return 0, "", 0


def curl_body(url: str, timeout: float = 45.0) -> str:
    r = subprocess.run(
        ["curl", "-sk", "--max-time", str(int(timeout)),
         "--resolve", f"symoneural.com:443:{PUBLIC_IP}", url],
        capture_output=True, text=True, timeout=timeout + 15)
    return r.stdout


def http(url: str, method: str = "GET", body: dict | None = None,
         timeout: float = 60.0) -> tuple[int, str, bytes]:
    headers: dict[str, str] = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", "").split(";")[0], r.read(200_000)
    except urllib.error.HTTPError as e:
        return e.code, (e.headers.get("Content-Type", "").split(";")[0] if e.headers else ""), b""
    except Exception as exc:
        return 0, f"{type(exc).__name__}", str(exc).encode()


# --------------------------------------------------------------------- checks
def check_preflight() -> None:
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "preflight.py"), "--json"],
                       capture_output=True, text=True, timeout=180)
    try:
        hard = json.loads(r.stdout)["hard_failures"]
    except Exception:
        record("preflight runs", FAIL, f"preflight produced no JSON: {r.stderr[-200:]}")
        return
    if hard:
        record("preflight: every hard dependency present", FAIL,
               f"{hard} hard failure(s) -- run: python3 tools/preflight.py")
    else:
        record("preflight: every hard dependency present", PASS)


def check_service() -> None:
    r = subprocess.run(["systemctl", "is-active", "symoneural-api"],
                       capture_output=True, text=True, timeout=30)
    state = r.stdout.strip()
    if state == "active":
        record("symoneural-api.service is active", PASS)
    else:
        record("symoneural-api.service is active", FAIL,
               f"is-active reported '{state}'. Start it: sudo systemctl start symoneural-api")


def check_status() -> dict | None:
    code, ctype, body = http(f"{API}/api/status")
    if code != 200:
        record("GET /api/status -> 200", FAIL, f"got {code}. journalctl -u symoneural-api -n 50")
        return None
    try:
        d = json.loads(body)
    except Exception as exc:
        record("GET /api/status -> 200", FAIL, f"200 but unparseable JSON: {exc}")
        return None
    record("GET /api/status -> 200", PASS, f"{len(d.get('units', []))} units reported")

    drv = d.get("gpu", {}).get("driver")
    if drv is None:
        record("status reports GPU driver health", SKIP,
               "no gpu.driver field -- this service predates that change; restart it to pick "
               "it up (sudo systemctl restart symoneural-api)")
    elif drv == "ok":
        record("status reports GPU driver health", PASS, "gpu.driver = ok")
    elif drv == "persistenced_down":
        record("status reports GPU driver health", PASS,
               "gpu.driver = persistenced_down (surfaces work; cold requests are slower)")
    else:
        record("status reports GPU driver health", FAIL,
               f"gpu.driver = {drv}: {d['gpu'].get('driver_detail')}")
    return d


def check_ravencalc() -> None:
    code, _, body = http(f"{API}/api/ravencalc", "POST",
                         {"expression": "diff(x**3 + 2*x, x)"})
    if code != 200:
        record("POST /api/ravencalc (CPU, no GPU needed)", FAIL, f"got {code}")
        return
    txt = body.decode("utf-8", "replace")
    # The answer, not merely a 200: d/dx(x^3+2x) = 3x^2+2.
    if "3*x**2 + 2" in txt:
        record("POST /api/ravencalc (CPU, no GPU needed)", PASS, "d/dx(x^3+2x) = 3*x**2 + 2")
    else:
        record("POST /api/ravencalc (CPU, no GPU needed)", FAIL,
               f"200 but the wrong answer: {txt[:200]}")


def check_rate_limit() -> None:
    """A published ceiling that is not applied is worse than no ceiling."""
    codes = {}
    for _ in range(280):
        c, _, _ = http(f"{API}/api/ravencalc", "POST", {"expression": "1+1"}, timeout=30)
        codes[c] = codes.get(c, 0) + 1
        if codes.get(429):
            break
    if codes.get(429):
        record("rate limits are enforced, not decorative", PASS,
               f"429 after {codes.get(200, 0)} accepted requests")
    else:
        record("rate limits are enforced, not decorative", FAIL,
               f"280 requests drew no 429: {codes}. Published caps are not being applied.")


def check_chat(driver_ok: bool) -> None:
    if not driver_ok:
        record("POST /api/chat (needs the GPU)", SKIP, "GPU driver is not healthy")
        return
    code, _, body = http(f"{API}/api/chat", "POST",
                         {"prompt": "Say the single word: smoke.", "max_tokens": 8},
                         timeout=300)
    txt = body.decode("utf-8", "replace")
    if code == 200 and '"delta"' in txt:
        record("POST /api/chat (needs the GPU)", PASS, "streamed delta frames")
    else:
        record("POST /api/chat (needs the GPU)", FAIL, f"{code}: {txt[:200]}")


def check_image(driver_ok: bool, quick: bool) -> None:
    if quick:
        record("POST /api/image (needs the GPU, ~20 s)", SKIP, "--quick was passed")
        return
    if not driver_ok:
        record("POST /api/image (needs the GPU, ~20 s)", SKIP, "GPU driver is not healthy")
        return
    code, _, body = http(f"{API}/api/image", "POST",
                         {"prompt": "a grey square", "steps": 4, "size": 256}, timeout=600)
    if code != 200:
        record("POST /api/image (needs the GPU, ~20 s)", FAIL,
               f"{code}: {body[:200].decode('utf-8', 'replace')}")
        return
    try:
        url = json.loads(body)["url"]
    except Exception as exc:
        record("POST /api/image (needs the GPU, ~20 s)", FAIL, f"200 but no url: {exc}")
        return
    c2, t2, b2 = http(API + url)
    if c2 == 200 and t2 == "image/png" and len(b2) > 1000:
        record("POST /api/image (needs the GPU, ~20 s)", PASS,
               f"rendered and served {len(b2)} bytes of image/png")
    else:
        record("POST /api/image (needs the GPU, ~20 s)", FAIL,
               f"render returned a url that does not serve: {c2} {t2}")


def check_remix() -> None:
    code, _, body = http(f"{API}/api/remix", "POST", {"prompt": "dark techno", "count": 3},
                         timeout=300)
    if code == 200 and b"tracks" in body:
        record("POST /api/remix", PASS)
    else:
        record("POST /api/remix", FAIL, f"{code}: {body[:160].decode('utf-8','replace')}")


def check_websocket() -> None:
    try:
        import websockets  # noqa: F401
    except ImportError:
        record("WebSocket /api/ws accepts and greets", SKIP,
               "the `websockets` module is not installed (apt install python3-websockets)")
        return
    import asyncio

    import websockets as ws

    async def go() -> str:
        async with ws.connect("ws://127.0.0.1:8800/api/ws", open_timeout=30) as sock:
            hello = await asyncio.wait_for(sock.recv(), timeout=30)
            return hello

    try:
        hello = asyncio.run(go())
    except Exception as exc:
        record("WebSocket /api/ws accepts and greets", FAIL, f"{type(exc).__name__}: {exc}")
        return
    if '"welcome"' in hello:
        record("WebSocket /api/ws accepts and greets", PASS, "received the welcome frame")
    else:
        record("WebSocket /api/ws accepts and greets", FAIL, f"unexpected first frame: {hello[:160]}")


def check_gpu_lease(driver_ok: bool, quick: bool) -> None:
    """Two concurrent GPU requests must not both load weights onto a 16 GB card."""
    if quick:
        record("GPU lease serialises under concurrency", SKIP, "--quick was passed")
        return
    if not driver_ok:
        record("GPU lease serialises under concurrency", SKIP, "GPU driver is not healthy")
        return
    lock = ROOT / "run" / "gpu.lock.d" / "holder"
    seen: set[str] = set()
    multi = 0
    stop = threading.Event()

    def sample() -> None:
        nonlocal multi
        while not stop.is_set():
            try:
                if lock.is_file():
                    names = {ln.split()[0] for ln in lock.read_text().splitlines() if ln.split()}
                    seen.update(names)
                    if len(names) > 1:
                        multi += 1
            except OSError:
                pass
            stop.wait(0.15)

    t = threading.Thread(target=sample, daemon=True)
    t.start()
    codes: list[int] = []
    lk = threading.Lock()

    def fire(i: int) -> None:
        c, _, _ = http(f"{API}/api/chat", "POST",
                       {"prompt": f"Say the single word: lease{i}.", "max_tokens": 8},
                       timeout=300)
        with lk:
            codes.append(c)

    threads = [threading.Thread(target=fire, args=(i,)) for i in range(2)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    stop.set()
    t.join(timeout=5)

    if any(c != 200 for c in codes):
        record("GPU lease serialises under concurrency", FAIL,
               f"concurrent chat requests returned {codes}")
    elif multi:
        record("GPU lease serialises under concurrency", FAIL,
               f"{multi} sample(s) showed more than one holder at once -- holders: {seen}")
    else:
        record("GPU lease serialises under concurrency", PASS,
               f"both served; never more than one holder (saw {sorted(seen) or ['none']})")


def check_models() -> None:
    wanted = [
        "backend/models/llm/symon-1.0-7b-q4_k_m.gguf",
        "backend/models/llm/symon-1.0-draft-0.5b-q4_k_m.gguf",
        "backend/models/image/symoneural-image-unet-q4_k.gguf",
        "backend/models/image/symoneural-image-vae.safetensors",
        "backend/models/image/symoneural-image-clip.safetensors",
    ]
    missing = [w for w in wanted if not (ROOT / w).is_file()]
    if missing:
        record("model weights present", FAIL,
               "absent: " + ", ".join(missing)
               + " -- check the storage ledger before calling it a defect; it may be a "
                 "completed migration")
    else:
        record("model weights present", PASS, f"{len(wanted)}/{len(wanted)} on disk")


def check_public_site() -> None:
    if not shutil.which("curl"):
        record("public site serves HTML", SKIP, "curl is not installed")
        return
    code, ctype, size = curl(f"{PUBLIC}/chat.html")
    if code != 200 or ctype != "text/html":
        record("public site serves HTML", FAIL, f"{code} {ctype}")
        return
    record("public site serves HTML", PASS, f"/chat.html {size} bytes")

    html = curl_body(f"{PUBLIC}/chat.html")
    refs = set(re.findall(r'(?:href|src)="([^"]+)"', html))
    for m in re.findall(r'srcset="([^"]+)"', html):
        for part in m.split(","):
            refs.add(part.strip().split()[0])
    # Strip BOTH the query string and the fragment. Missing the fragment is how an earlier
    # version of this check "passed" while testing nothing: every asset carries ?v=<hash>.
    assets = sorted({r.split("?")[0].split("#")[0] for r in refs
                     if r.startswith("/") and not r.startswith("//")}
                    - {""})
    ext = [a for a in assets if "." in a.rsplit("/", 1)[-1] and not a.endswith(".html")]
    bad = []
    for a in ext:
        c, t, n = curl(PUBLIC + a)
        if c != 200 or not n:
            bad.append(f"{a} -> {c}")
    if bad:
        record("public site assets resolve", FAIL, "; ".join(bad[:6]))
    else:
        record("public site assets resolve", PASS,
               f"{len(ext)} assets, all 200 through the public path")


def check_public_api() -> None:
    """The path a visitor takes. Currently the one thing that is genuinely broken."""
    if not shutil.which("curl"):
        record("public /api/status reaches the API", SKIP, "curl is not installed")
        return
    code, _, _ = curl(f"{PUBLIC}/api/status")
    if code == 200:
        record("public /api/status reaches the API", PASS)
    else:
        record("public /api/status reaches the API", FAIL,
               f"got {code}. The Caddyfile routes /api/* to 127.0.0.1:8000 "
               "(symoneural-gateway), which is disabled -- so every documented surface is "
               "unreachable from outside this box while working fine on :8800. "
               "See RUNBOOK.md 'The public API returns 502'.")


def check_gpu_released() -> None:
    """The LEASE must be released. Resident weights are not a leak.

    The first version of this failed any box where an engine was still resident, and that is
    wrong: after a GPU request `symoneural-llm` deliberately stays loaded (measured: 8330 MiB
    with `run/gpu.lock.d` absent) so the next request does not pay the load again. The
    governor is designed to evict a resident-but-idle tenant when another needs the card.
    What would be a real fault is the lock directory outliving the work that took it, because
    then nothing else can ever acquire the card.
    """
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30)
    except Exception as exc:
        record("no process left holding VRAM", SKIP, f"nvidia-smi unavailable: {exc}")
        return
    procs = [l for l in out.stdout.strip().splitlines() if l.strip()]
    lockdir = ROOT / "run" / "gpu.lock.d"
    if lockdir.is_dir():
        record("GPU lease released after the work finished", FAIL,
               f"{lockdir} still exists -- nothing else can acquire the card. "
               f"Release it: scripts/gpu-governor.sh release chat")
    else:
        detail = "lock directory gone"
        if procs:
            detail += f"; {len(procs)} engine(s) still resident by design ("
            detail += "; ".join(procs) + ") -- the governor evicts these on demand"
        record("GPU lease released after the work finished", PASS, detail)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true",
                    help="skip the slow GPU checks (image render, lease proof)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    print(f"SyMoNeuRaL API smoke test  ({ROOT})")
    print(f"  API    : {API}")
    print(f"  public : {PUBLIC} (resolved to {PUBLIC_IP})")
    print()

    t0 = time.monotonic()
    check_preflight()
    check_service()
    status = check_status()
    driver = (status or {}).get("gpu", {}).get("driver", "ok")
    driver_ok = driver in ("ok", "persistenced_down")

    check_models()
    check_ravencalc()
    check_remix()
    check_chat(driver_ok)
    check_image(driver_ok, args.quick)
    check_gpu_lease(driver_ok, args.quick)
    check_websocket()
    check_rate_limit()
    check_public_site()
    check_public_api()
    check_gpu_released()
    elapsed = time.monotonic() - t0

    failed = [r for r in results if r["state"] == FAIL]
    skipped = [r for r in results if r["state"] == SKIP]
    passed = [r for r in results if r["state"] == PASS]

    if args.json:
        print(json.dumps({"results": results, "passed": len(passed),
                          "failed": len(failed), "skipped": len(skipped),
                          "seconds": round(elapsed, 1)}, indent=2))
        return 1 if failed else 0

    print(f"\n{'=' * 70}")
    print(f"  {len(passed)} passed, {len(failed)} FAILED, {len(skipped)} skipped "
          f"in {elapsed:.0f}s")
    if skipped:
        print("\n  SKIPPED -- these were NOT tested and are not passes:")
        for r in skipped:
            print(f"    - {r['check']}: {r['detail']}")
    if failed:
        print("\n  FAILED:")
        for r in failed:
            print(f"    - {r['check']}")
            print(f"      {r['detail']}")
        print("\n  SMOKE TEST FAILED")
        return 1
    print("\n  SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
