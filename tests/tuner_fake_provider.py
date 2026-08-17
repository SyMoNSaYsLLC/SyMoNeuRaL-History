"""A scripted tuner API, so the page's failure paths can be driven without a provider.

The point of this harness is that we have no credentials and no known-good stream, so
every claim about "the page now explains why a stream did not play" would otherwise be
unfalsifiable. This serves site/ unchanged and answers /api/tuner/* with whatever the
case under test needs, including the exact shape that produced the blank screen:
HTTP 200 with state:"starting" and a playlist path that does not exist.
"""
import json
import pathlib
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

SITE = str(pathlib.Path(__file__).resolve().parent.parent / "site")

# Set by the test through GET /_case?name=...
CASE = {"name": "refused"}
POLLS = {"n": 0}

M3U = """#EXTM3U
#EXTINF:-1 group-title="Sports",Test Channel One
http://example.invalid/live/a/b/1.ts
#EXTINF:-1 group-title="Movies",Test Film Two
http://example.invalid/movie/a/b/2.mp4
"""


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/_case"):
            CASE["name"] = self.path.split("=", 1)[1]
            POLLS["n"] = 0
            return self._json(200, {"case": CASE["name"]})
        if self.path.startswith("/api/tuner/session/"):
            POLLS["n"] += 1
            return self._json(200, self._session())
        if self.path.startswith("/api/tuner/state"):
            return self._json(200, {"ffmpeg": True, "max_sessions": 2, "active": 0,
                                    "sessions": [], "channels_stored": 0})
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        if self.path.startswith("/api/tuner/playlist"):
            # `truncated` is the parser saying it stopped at MAX_CHANNELS. The page read it
            # nowhere, so an over-cap playlist silently lost its tail -- see the "cut off"
            # case in tuner_failpaths.mjs.
            return self._json(200, {
                "source": "pasted", "count": 2,
                "truncated": CASE["name"] == "truncated", "limit": 20000,
                "groups": ["Sports", "Movies"],
                "channels": [
                    {"name": "Test Channel One", "group": "Sports", "kind": "live",
                     "url": "http://example.invalid/live/a/b/1.ts", "logo": ""},
                    {"name": "Test Film Two", "group": "Movies", "kind": "vod",
                     "url": "http://example.invalid/movie/a/b/2.mp4", "logo": ""},
                ]})
        if self.path.startswith("/api/tuner/xtream/channels"):
            # A panel whose movie catalogue was over this box's byte ceiling: live and series
            # arrive, movies do not, and the only thing standing between the visitor and
            # "movies are broken" is that note.
            return self._json(200, {
                "count": 2, "groups": ["Sports", "SERIES | Drama"],
                "notes": ["vod: this panel's catalogue is larger than this box will load in "
                          "one request, so it was skipped (panel.invalid:80: response exceeds "
                          "67108864 bytes)"],
                "channels": [
                    {"name": "Test Channel One", "group": "Sports", "kind": "live",
                     "url": "http://example.invalid/live/a/b/1.ts", "logo": ""},
                    {"name": "A Show", "group": "SERIES | Drama", "kind": "series",
                     "url": "", "logo": ""},
                ]})
        if self.path.startswith("/api/tuner/tune"):
            c = CASE["name"]
            if c == "refused":
                # What a provider actually does when a channel is off air: an HTTP
                # error carrying its own words. The old code showed none of this.
                return self._json(400, {"detail": "example.invalid:80: upstream returned "
                                                  "HTTP 404 - Stream is currently offline. "
                                                  "Please contact your provider."})
            if c == "hevc":
                # `segments` and `segment_s` are what `sessions.public()` reports, and the
                # page will not hand a manifest to hls.js until segments > 0 -- a "live"
                # session whose playlist is still empty is the blank-screen bug all over
                # again. This fixture omitted them, so it was testing a backend that no
                # longer exists and case 4 timed out waiting for a panel.
                return self._json(200, {"id": "S1", "label": "x", "state": "live",
                                        "error": None, "mode": "direct", "vcodec": "hevc",
                                        "playlist": "stream/S1/live.m3u8", "age_s": 1.0,
                                        "bytes_in": 99, "idle_timeout_s": 45,
                                        "segments": 3, "segment_s": 2.0,
                                        "max_lifetime_s": 1800})
            if c == "ac3":
                # THE ONE THAT LOOKS PERFECT AND SHOWS NOTHING. h264 video -- which every
                # browser decodes -- with a Dolby Digital soundtrack, which Chrome's MSE
                # refuses. It refuses the whole segment, not just the audio, so the picture
                # is black while `vcodec` reads a reassuring `h264` and every byte counter on
                # the box climbs. Measured on one of the owner's own channels: live, h264,
                # 87 MB pulled over five minutes, zero frames decoded, and the page had
                # nothing to say because it could only see the video codec.
                return self._json(200, {"id": "S1", "label": "x", "state": "live",
                                        "error": None, "mode": "direct", "vcodec": "h264",
                                        "acodec": "ac3",
                                        "playlist": "stream/S1/live.m3u8", "age_s": 1.0,
                                        "bytes_in": 91_226_112, "idle_timeout_s": 45,
                                        "segments": 4, "segment_s": 6.54,
                                        "max_lifetime_s": 1800})
            if c == "aac":
                # The control for `ac3`, and the assertion that matters most: an ordinary
                # h264 + AAC stream must produce NO panel at all. A codec warning that fires
                # on a stream which plays is worse than none -- it teaches the visitor to
                # ignore the one panel that tells the truth.
                return self._json(200, {"id": "S1", "label": "x", "state": "live",
                                        "error": None, "mode": "direct", "vcodec": "h264",
                                        "acodec": "aac",
                                        "playlist": "stream/S1/live.m3u8", "age_s": 1.0,
                                        "bytes_in": 1_150_000, "idle_timeout_s": 45,
                                        "segments": 6, "segment_s": 2.002,
                                        "max_lifetime_s": 1800})
            if c == "emptylive":
                # The one the gate exists for: state "live", playlist named, nothing in it.
                return self._json(200, {"id": "S1", "label": "x", "state": "live",
                                        "error": None, "mode": "direct",
                                        "playlist": "stream/S1/live.m3u8", "age_s": 1.0,
                                        "bytes_in": 4096, "idle_timeout_s": 45,
                                        "segments": 0, "segment_s": 0.0,
                                        "max_lifetime_s": 1800})
            # "starting" + a note: HTTP 200 that is not a success. This is the exact
            # response that used to be handed straight to hls.js.
            return self._json(200, {"id": "S1", "label": "x", "state": "starting",
                                    "error": None, "mode": "direct",
                                    "playlist": "stream/S1/live.m3u8", "age_s": 10.0,
                                    "bytes_in": 0, "idle_timeout_s": 45,
                                    "max_lifetime_s": 1800,
                                    "note": "no playable output yet; poll the session"})
        return self._json(404, {"detail": "no"})

    def _session(self):
        c = CASE["name"]
        base = {"id": "S1", "label": "x", "mode": "direct",
                "playlist": "stream/S1/live.m3u8", "age_s": 3.0, "bytes_in": 0,
                "idle_timeout_s": 45, "max_lifetime_s": 1800}
        if c == "html":
            # The provider answered 200 with a web page instead of a stream.
            return {**base, "state": "failed",
                    "error": "example.invalid:80 answered with a web page, not a stream: "
                             "\"This stream is temporarily unavailable while we perform "
                             "maintenance. Sorry for the inconvenience.\""}
        if c == "stuck":
            return {**base, "state": "starting"}
        if c == "hevc":
            return {**base, "state": "live", "error": None, "vcodec": "hevc",
                    "segments": 3, "segment_s": 2.0}
        if c == "ac3":
            return {**base, "state": "live", "error": None, "vcodec": "h264",
                    "acodec": "ac3", "segments": 4, "segment_s": 6.54,
                    "bytes_in": 91_226_112}
        if c == "aac":
            return {**base, "state": "live", "error": None, "vcodec": "h264",
                    "acodec": "aac", "segments": 6, "segment_s": 2.002,
                    "bytes_in": 1_150_000}
        if c == "emptylive":
            return {**base, "state": "live", "error": None,
                    "segments": 0, "segment_s": 0.0}
        return {**base, "state": "starting"}


if __name__ == "__main__":
    port = int(sys.argv[1])
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"serving {SITE} on {port}", flush=True)
    threading.Event().wait()
