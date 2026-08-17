"""Tuning sessions: one upstream stream, one ffmpeg, a bounded number of both.

## What this fixes in `references/IPTV/IPTV/iptv_gateway_server.py`

That file is the right idea and three things in it cannot ship on a public box.

**1. The source was hardcoded.** `PRIMARY_SOURCE` and `BACKUP_SOURCE` were constants at the top
of the file. Here the source arrives per request and belongs to the visitor. Its "self-healing
failover" between the two constants is gone with them: failing over to a source the visitor did
not choose is not resilience, it is playing them something else. A session that loses its
upstream reports that it lost its upstream.

**2. It emitted raw MPEG-TS via `-c copy` to `pipe:1`, which a browser cannot play.** No
`<video>` element in any browser decodes an MPEG-TS elementary stream; the reference's endpoint
works in VLC and shows a broken player on a web page. **We emit HLS** -- `-f hls`, an `.m3u8`
plus rolling `.ts` segments -- and the choice over fragmented MP4 was made on three grounds:

  - **`-c copy` survives more sources.** IPTV upstreams are H.264 or HEVC with AAC, AC-3 or
    MP2 audio, and MPEG-TS segments carry all of those unchanged. Several of them cannot go
    into MP4 without re-encoding, and re-encoding on a box whose GPU is reserved for inference
    is not acceptable -- it would either take the card the rack promised to chat and image, or
    burn the CPU. Stream copy is the requirement; TS segments are what keeps it possible.
  - **The player is decoupled from the transcoder.** A single progressive fMP4 response ties
    one ffmpeg to one TCP connection, so a page reload, a seek or a flaky connection restarts
    the upstream pull. With HLS the segments are on disk and a reload is just more GETs.
  - **Disk is bounded by the muxer itself.** `hls_flags delete_segments` with a short
    `hls_list_size` keeps a rolling window and deletes behind it, so a session cannot fill the
    disk however long it runs.

  The cost is honest and belongs in the wiring notes: Safari plays `.m3u8` natively, and Chrome
  and Firefox need `hls.js` (MSE). That is a frontend dependency this module cannot satisfy for
  the page and does not pretend to.

**3. One unbounded ffmpeg per client was a trivial denial of service.** The reference spawns a
process per request, forever, with no cap and no timeout: a few dozen GETs and the box is gone.
Here there is a hard concurrent-session cap, an idle timeout keyed on the player actually
asking for segments, a hard maximum lifetime, and a reaper that runs whether or not the client
was polite enough to disconnect.

## Why Python holds the socket and ffmpeg only sees a pipe

`safefetch` validates a URL and pins the address. Handing that URL to ffmpeg would throw all of
it away -- ffmpeg resolves its own names, follows its own redirects, in another process. So
**the upstream URL never reaches the subprocess**: a pump thread opens the connection through
`safefetch`, and ffmpeg reads `pipe:0` with `-protocol_whitelist pipe,fd` so it could not open
a URL if one arrived. The same arrangement keeps the visitor's credentials out of `argv`.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import safefetch
from .m3u import parse_hls
from .safefetch import BlockedURL, FetchError, Policy, Scrubber

log = logging.getLogger("symoneural.tuner")

__all__ = ["Session", "SessionManager", "MANAGER", "TunerBusy", "TunerError",
           "PLAYLIST_NAME", "SEGMENT_RE"]


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(os.environ[name])))
    except (KeyError, ValueError):
        return default


#: Concurrent ffmpeg processes. Two, because this is one box that is also serving a 7B model and
#: an image pipeline, and because the honest ceiling is low rather than because the number is
#: tidy. Raise it with `SYMONEURAL_TUNER_MAX_SESSIONS` if the box ever grows.
MAX_SESSIONS = _env_int("SYMONEURAL_TUNER_MAX_SESSIONS", 2, 1, 8)
#: No segment or playlist request for this long and the session is dead, whatever the client
#: thinks. This is the cap that survives a browser tab being closed without a goodbye.
IDLE_TIMEOUT = _env_int("SYMONEURAL_TUNER_IDLE_TIMEOUT", 45, 10, 600)
#: Nothing streams forever on a shared demo box, however attentive the client is.
MAX_LIFETIME = _env_int("SYMONEURAL_TUNER_MAX_LIFETIME", 1800, 60, 21600)
#: A pump that has read this much has had its turn. Bounds egress independently of time.
MAX_SESSION_BYTES = _env_int("SYMONEURAL_TUNER_MAX_BYTES", 4096, 64, 65536) * 1024 * 1024
#: Rolling window: 6 segments x ~2 s. Per session that is ~12 s of video on disk; at a heavy
#: 8 Mb/s that is about 12 MB, and the cap above bounds the total.
HLS_SEGMENT_SECONDS = 2
HLS_WINDOW = 6

PLAYLIST_NAME = "live.m3u8"
#: Anything served out of a session directory must match this. The directory holds only files
#: ffmpeg created with names we chose, so an allow-list of that exact shape is achievable, and
#: it means no request path is ever joined to a directory without first being proved to be a
#: plain filename.
SEGMENT_RE = re.compile(r"^s[0-9]{1,6}\.(ts|m4s)$")

FFMPEG = shutil.which("ffmpeg")


class TunerError(Exception):
    """A session could not start or has failed. Messages are scrubbed before they get here."""


class TunerBusy(TunerError):
    """Every slot is taken. Distinct from TunerError so the router can answer 503, not 400."""


@dataclass
class Session:
    id: str
    label: str                       # channel name, shown to the visitor. Never a URL.
    dir: Path
    created: float
    scrub: Scrubber
    policy: Policy
    url: str = ""                    # upstream. In memory only, never logged, never returned.
    proc: subprocess.Popen | None = None
    thread: threading.Thread | None = None
    stop: threading.Event = field(default_factory=threading.Event)
    last_seen: float = 0.0
    state: str = "starting"          # starting | live | ended | failed
    #: Our own failure text, and only ours. Every string assigned here comes from this package's
    #: own exception classes, whose messages are built from a fixed string plus `scheme://host:
    #: port` -- never from a path, never from an upstream library's message.
    error: str | None = None
    #: ffmpeg's stderr. **Internal.** Never returned to a client and never logged unscrubbed.
    #: Kept apart from `error` because it is the one string in this object whose contents are
    #: written by a program we do not control, and `public()` must have no such field: an M3U
    #: from an Xtream panel has the password in a *path segment*, and a session started from a
    #: pasted playlist has no credentials registered with its scrubber to catch it.
    transcoder_error: str | None = None
    bytes_in: int = 0
    mode: str = "direct"             # direct | hls  -- what the upstream turned out to be

    def public(self) -> dict:
        """What a visitor may see. Deliberately has no field that could hold a credential.

        `error` is either one of our own origin-only messages or a fixed sentence. It is never
        ffmpeg's stderr and never an upstream library's exception text.
        """
        error = self.error
        if error is None and self.state == "failed":
            error = "the transcoder could not stream-copy this source"
        return {
            "id": self.id,
            "label": self.label,
            "state": self.state,
            "error": error,
            "mode": self.mode,
            "playlist": f"stream/{self.id}/{PLAYLIST_NAME}",
            "age_s": round(time.monotonic() - self.created, 1),
            "bytes_in": self.bytes_in,
            "idle_timeout_s": IDLE_TIMEOUT,
            "max_lifetime_s": MAX_LIFETIME,
        }

    @property
    def ready(self) -> bool:
        """True once ffmpeg has actually written a playlist -- the only honest readiness test.

        Not "the process started": ffmpeg exits nonzero several seconds later on a source it
        cannot copy, and reporting `live` in that window would be a status light that reflects
        nothing.
        """
        return (self.dir / PLAYLIST_NAME).is_file()


class SessionManager:
    def __init__(self, root: Path | None = None):
        self._root = Path(root) if root else None
        self._sessions: dict[str, Session] = {}
        # Reentrant: `start` reads the `root` property (which takes the lock to create the
        # directory lazily) from inside its own locked section. With a plain Lock that is a
        # deadlock on the first session, and only on the first session -- the worst kind.
        self._lock = threading.RLock()
        self._reaper: threading.Thread | None = None

    @property
    def root(self) -> Path:
        """Where segments live. Created on first session, never at import.

        Not `run/` -- that directory's contract is locks and pidfiles, and something clearing
        it while a surface holds the card is already a documented hazard here. Not
        `backend/output/` either, which is the render namespace served by `/api/gen/<name>`:
        HLS segments are not renders and this module has no business writing into a namespace
        somebody else owns. A private temporary directory, removed session by session.

        On most systems `/tmp` is tmpfs, so segments cost RAM rather than disk. That is bounded
        deliberately: `hls_list_size` x `hls_time` per session, times `MAX_SESSIONS`. Point
        `SYMONEURAL_TUNER_DIR` at real disk if that trade is wrong for the box.
        """
        if self._root is None:
            with self._lock:
                if self._root is None:
                    self._root = Path(os.environ.get("SYMONEURAL_TUNER_DIR")
                                      or tempfile.mkdtemp(prefix="symoneural-tuner-"))
        self._root.mkdir(parents=True, exist_ok=True)
        return self._root

    # ------------------------------------------------------------------ lifecycle

    def start(self, url: str, label: str, policy: Policy | None = None,
              scrub: Scrubber | None = None) -> Session:
        """Validate the source, take a slot, spawn ffmpeg, start pumping.

        The URL is validated *before* a slot is taken, so a hostile URL cannot occupy capacity
        while it fails.
        """
        if not FFMPEG:
            raise TunerError("ffmpeg is not installed on this machine")
        policy = policy or Policy()
        # Whatever the caller registered, plus everything the URL itself hides. The caller
        # only has credentials to register on the Xtream path; a pasted M3U carries them in
        # the URL and tells us nothing.
        scrub = Scrubber.from_url(url, *(scrub._secrets if scrub else ()))
        # Fail fast and loudly on the SSRF check, before any resource is committed.
        try:
            safefetch.validate_url(url, policy)
        except BlockedURL as exc:
            raise TunerError(scrub(str(exc))) from None

        self.reap()
        with self._lock:
            if len(self._sessions) >= MAX_SESSIONS:
                raise TunerBusy(
                    f"all {MAX_SESSIONS} tuner slots are in use; try again shortly")
            sid = secrets.token_urlsafe(12)
            sdir = self.root / sid
            sdir.mkdir(parents=True, exist_ok=False)
            now = time.monotonic()
            s = Session(id=sid, label=label or "(unnamed)", dir=sdir, created=now,
                        scrub=scrub, policy=policy, url=url, last_seen=now)
            self._sessions[sid] = s

        try:
            s.proc = self._spawn(s)
        except Exception as exc:
            self._drop(sid)
            raise TunerError(f"could not start the transcoder: {type(exc).__name__}") from None

        s.thread = threading.Thread(target=self._pump, args=(s,),
                                    name=f"tuner-pump-{sid}", daemon=True)
        s.thread.start()
        self._ensure_reaper()
        # The label is safe (it came from a playlist display name, not a URL) but it is visitor
        # data, so it is scrubbed and truncated before it is allowed into a log line.
        log.info("tuner: session %s started (%s)", sid, safefetch.redact(s.label)[:60])
        return s

    def _spawn(self, s: Session) -> subprocess.Popen:
        cmd = [
            FFMPEG, "-hide_banner", "-nostdin", "-loglevel", "error",
            # Input-side protocol allow-list. Binds to the input that follows, and means a
            # malformed or hostile stream cannot talk ffmpeg into opening a file or a URL.
            # There is no `file` and no `http` here on purpose.
            "-protocol_whitelist", "pipe,fd",
            "-fflags", "+genpts+discardcorrupt",
            "-analyzeduration", "5M", "-probesize", "5M",
            "-i", "pipe:0",
            # Stream copy, and only stream copy. If the source codecs cannot go into an MPEG-TS
            # segment unchanged, ffmpeg fails and the session reports why -- it never quietly
            # re-encodes, because the GPU belongs to inference and the CPU has a site to serve.
            "-c", "copy",
            "-f", "hls",
            "-hls_time", str(HLS_SEGMENT_SECONDS),
            "-hls_list_size", str(HLS_WINDOW),
            # delete_segments is the disk bound; omit_endlist keeps the player at the live edge;
            # independent_segments lets a player start on any segment; temp_file stops a player
            # fetching a segment ffmpeg is still writing.
            "-hls_flags", "delete_segments+omit_endlist+independent_segments+temp_file",
            "-hls_allow_cache", "0",
            "-hls_segment_type", "mpegts",
            "-hls_segment_filename", str(s.dir / "s%05d.ts"),
            str(s.dir / PLAYLIST_NAME),
        ]
        # No URL and no credential appears anywhere in this argv -- see the module docstring.
        # stderr is a pipe rather than DEVNULL so a failure can be explained, and is drained by
        # a thread that scrubs every line before it is stored.
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, start_new_session=True)
        threading.Thread(target=self._drain_stderr, args=(s, proc), daemon=True,
                         name=f"tuner-err-{s.id}").start()
        return proc

    def _drain_stderr(self, s: Session, proc: subprocess.Popen) -> None:
        """Keep ffmpeg's last complaint, scrubbed, and never write it to a log unscrubbed.

        ffmpeg quotes its input in some messages. Our input is `pipe:0`, so there should be no
        URL in there at all -- this runs the scrubber anyway, because "should be" is not a
        security control.
        """
        try:
            for raw in iter(proc.stderr.readline, b""):
                line = s.scrub(raw.decode("utf-8", "replace").strip())
                if line:
                    s.transcoder_error = line[:200]
        except Exception:
            pass
        finally:
            try:
                proc.stderr.close()
            except Exception:
                pass

    # ------------------------------------------------------------------ the pump

    def _pump(self, s: Session) -> None:
        """Read the upstream through the pinned client, write it into ffmpeg's stdin."""
        try:
            self._pump_inner(s)
            if s.state != "failed":
                s.state = "ended"
        except BlockedURL as exc:
            s.state, s.error = "failed", s.scrub(str(exc))
        except FetchError as exc:
            s.state, s.error = "failed", s.scrub(str(exc))
        except TunerError as exc:
            s.state, s.error = "failed", s.scrub(str(exc))
        except BrokenPipeError:
            # ffmpeg went away. Its stderr says why and stays internal; the client gets a
            # sentence we wrote.
            s.state = "failed"
            s.error = "the transcoder exited before the stream ended"
        except Exception as exc:
            # Never surface the message: an arbitrary exception from a network stack can quote
            # the URL, and the URL is the credential.
            s.state, s.error = "failed", f"upstream error ({type(exc).__name__})"
        finally:
            try:
                if s.proc and s.proc.stdin:
                    s.proc.stdin.close()
            except Exception:
                pass

    def _write(self, s: Session, chunk: bytes) -> None:
        s.proc.stdin.write(chunk)
        s.bytes_in += len(chunk)
        if s.bytes_in > MAX_SESSION_BYTES:
            raise TunerError("session reached its data cap")

    def _pump_inner(self, s: Session) -> None:
        resp, conn, target = safefetch.open_stream(s.url, s.policy)
        try:
            ctype = (resp.getheader("Content-Type") or "").split(";")[0].strip().lower()
            head = resp.read(4096)
            # An IPTV "stream URL" is about as likely to be an HLS playlist as a continuous
            # transport stream, and the extension lies often enough to be useless. Sniff:
            # MPEG-TS begins with the 0x47 sync byte, an HLS playlist begins with #EXTM3U.
            looks_hls = head.lstrip(b"\xef\xbb\xbf \r\n\t").upper().startswith(b"#EXTM3U") or \
                ctype in ("application/vnd.apple.mpegurl", "application/x-mpegurl",
                          "audio/mpegurl", "audio/x-mpegurl")
            if looks_hls:
                body = head + resp.read(s.policy.max_bytes)
                conn.close()
                s.mode = "hls"
                return self._pump_hls(s, target, body)

            s.mode = "direct"
            s.state = "live"
            self._write(s, head)
            while not s.stop.is_set():
                chunk = resp.read(65536)
                if not chunk:
                    return          # upstream EOF. No failover -- see the module docstring.
                self._write(s, chunk)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _pump_hls(self, s: Session, target: safefetch.Target, body: bytes) -> None:
        """Follow an upstream HLS playlist, concatenating its segments into ffmpeg's stdin.

        Every playlist and every segment URL goes back through `safefetch.open_stream`, so the
        SSRF rules are re-applied to each one. A playlist is a list of URLs supplied by a
        third party and is exactly as untrusted as the URL the visitor typed.
        """
        pl = parse_hls(body.decode("utf-8", "replace"))
        if pl.is_master:
            # Prefer the highest bitrate that is not absurd for a shared box; if every variant
            # is above the ceiling take the smallest, rather than refusing to play anything.
            ceiling = 8_000_000
            under = [v for v in pl.variants if 0 < v.bandwidth <= ceiling]
            pick = (max(under, key=lambda v: v.bandwidth) if under
                    else min(pl.variants, key=lambda v: v.bandwidth or 1 << 62))
            body, _ct, target = safefetch.fetch(target.join(pick.uri), s.policy)
            pl = parse_hls(body.decode("utf-8", "replace"))
        if pl.encrypted:
            raise TunerError("this stream is AES-encrypted; the tuner cannot decrypt it")
        if not pl.segments:
            raise TunerError("upstream playlist contained no segments")

        # The absolute URL of the media playlist, kept as a string. Segment URIs and every
        # refresh resolve against *this*, not against whatever the last redirect left in
        # `target` -- refreshing a playlist by re-joining an empty reference is the kind of
        # thing that works until a provider serves the playlist from a redirect.
        playlist_url = target.join("")

        # Where to start reading. A live playlist should start near its live edge -- handing
        # ffmpeg the whole window only starts playback further behind. A playlist carrying
        # #EXT-X-ENDLIST is not live, it is a complete recording, and starting at its "live
        # edge" would silently skip everything but the last few seconds. That distinction cost
        # a smoke-test run to find: a 12 s VOD playlist played 4 s of itself.
        if pl.ended:
            next_seq = pl.segments[0].sequence
        else:
            next_seq = max(pl.segments[0].sequence, pl.segments[-1].sequence - 2)
        s.state = "live"
        deadline = time.monotonic() + MAX_LIFETIME

        while not s.stop.is_set() and time.monotonic() < deadline:
            for seg in [g for g in pl.segments if g.sequence >= next_seq]:
                if s.stop.is_set():
                    return
                # Re-validated per segment: a playlist is a list of URLs written by a third
                # party and is exactly as untrusted as the one the visitor typed.
                resp, conn, _t = safefetch.open_stream(
                    safefetch.validate_url(playlist_url, s.policy).join(seg.uri), s.policy)
                try:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        self._write(s, chunk)
                finally:
                    conn.close()
                next_seq = seg.sequence + 1
            if pl.ended:
                return
            # A live playlist gains a segment every target duration; polling faster than half
            # of that is load on someone else's server for no new data.
            if s.stop.wait(max(1.0, pl.target_duration / 2)):
                return
            body, _ct, _t = safefetch.fetch(playlist_url, s.policy)
            pl = parse_hls(body.decode("utf-8", "replace"))

    # ------------------------------------------------------------------ reaping

    def touch(self, sid: str) -> Session | None:
        s = self._sessions.get(sid)
        if s:
            s.last_seen = time.monotonic()
        return s

    def get(self, sid: str) -> Session | None:
        return self._sessions.get(sid)

    def list(self) -> list[Session]:
        return list(self._sessions.values())

    def stop_session(self, sid: str) -> bool:
        if sid not in self._sessions:
            return False
        self._drop(sid)
        return True

    def _drop(self, sid: str) -> None:
        with self._lock:
            s = self._sessions.pop(sid, None)
        if not s:
            return
        s.stop.set()
        proc = s.proc
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                    # Reap it. Without this wait the child stays a zombie until the next
                    # garbage collection of the Popen object -- which on a long-lived API
                    # process is "eventually", and eventually is how a process table fills.
                    proc.wait(timeout=3)
                except Exception:
                    pass
        try:
            if proc and proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        shutil.rmtree(s.dir, ignore_errors=True)
        log.info("tuner: session %s reaped (%s, %.1f MB in)",
                 sid, s.state, s.bytes_in / 1048576)

    def reap(self) -> int:
        """Close sessions that are idle, expired, or whose transcoder has exited.

        Idleness is measured from the last *player* request, not from the last upstream byte:
        a source can keep sending long after the visitor closed the tab, and it is the tab
        closing that should free the slot.
        """
        now = time.monotonic()
        doomed = []
        for sid, s in list(self._sessions.items()):
            if now - s.last_seen > IDLE_TIMEOUT:
                doomed.append(sid)
            elif now - s.created > MAX_LIFETIME:
                doomed.append(sid)
            elif s.proc is not None and s.proc.poll() is not None:
                doomed.append(sid)
            elif s.state in ("ended", "failed") and now - s.created > 10:
                doomed.append(sid)
        for sid in doomed:
            self._drop(sid)
        return len(doomed)

    def _ensure_reaper(self) -> None:
        """Start the reaper on first use.

        Lazily, and never at import: the wiring engineer imports this module at module scope in
        `api.py`, and importing something should not spawn a background thread in a process that
        may never tune a channel.
        """
        if self._reaper and self._reaper.is_alive():
            return
        with self._lock:
            if self._reaper and self._reaper.is_alive():
                return
            self._reaper = threading.Thread(target=self._reap_loop, name="tuner-reaper",
                                            daemon=True)
            self._reaper.start()

    def _reap_loop(self) -> None:
        while True:
            time.sleep(5)
            try:
                if not self._sessions:
                    return          # nothing to watch; `_ensure_reaper` restarts us on demand
                self.reap()
            except Exception:       # pragma: no cover - a reaper that dies leaks processes
                log.exception("tuner: reaper iteration failed")

    def shutdown(self) -> None:
        for sid in list(self._sessions):
            self._drop(sid)


#: The process-wide manager. One per API process; sessions are in-memory, so a restart ends
#: every session, which is correct -- the segments went with the temporary directory.
MANAGER = SessionManager()
