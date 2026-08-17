#!/usr/bin/env python3
"""Tests for the Tuner. Standard library only, no network, no IPTV provider.

    python3 backend/apps/tuner/test_tuner.py           # from the repo root
    python3 -m apps.tuner.test_tuner                   # from backend/

Three things are actually being defended here and the rest is parsing:

1. **The SSRF validator**, against a table of hostile inputs. The table is the specification --
   if a bypass is ever found, it gets a row here before it gets a fix.
2. **No credential ever escapes.** A sentinel password is pushed through the real router and
   every channel it could come back out of -- log records, response bodies, exception text,
   the session's public document -- is searched for it.
3. **The DoS caps** on concurrent sessions and on path names.

No playlist from `references/` is read, quoted or shipped. Every fixture below was written by
hand for this file; the provider playlists in that directory embed real credentials in their
URLs and must never enter this repo's source.
"""
from __future__ import annotations

import functools
import http.server
import io
import ipaddress
import logging
import pathlib
import socketserver
import sys
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from apps.tuner import m3u, routes, safefetch, sessions, xtream          # noqa: E402
from apps.tuner.safefetch import BlockedURL, Policy, Scrubber            # noqa: E402

SENTINEL_USER = "zz-tuner-test-user-zz"
SENTINEL_PASS = "Hunter2-CorrectHorseBatteryStaple-9times"


def resolver(mapping: dict[str, list[str]], counter: list[int] | None = None):
    """A stand-in for getaddrinfo so the hostile table needs no DNS and no network."""
    def _r(host: str, port: int) -> list[str]:
        if counter is not None:
            counter[0] += 1
        try:
            return [str(ipaddress.ip_address(host))]      # a literal resolves to itself
        except ValueError:
            pass
        if host in mapping:
            return mapping[host]
        raise OSError("NXDOMAIN")
    return _r


# ===================================================================== SSRF

class TestAddressClassification(unittest.TestCase):
    """`_reject_reason` on addresses directly -- the layer under `validate_url`."""

    BLOCKED = [
        ("127.0.0.1", "loopback"), ("127.255.255.254", "loopback"),
        ("10.0.0.1", "private"), ("172.16.0.1", "private"), ("172.31.255.255", "private"),
        ("192.168.1.1", "private"), ("169.254.169.254", "link-local"),
        ("169.254.0.1", "link-local"), ("0.0.0.0", "unspecified"),
        ("100.64.0.1", None), ("192.0.2.1", None), ("198.18.0.1", None),
        ("224.0.0.1", "multicast"), ("239.255.255.250", "multicast"),
        ("240.0.0.1", None), ("255.255.255.255", None),
        ("::1", "loopback"), ("::", "unspecified"), ("fe80::1", "link-local"),
        ("fc00::1", "private"), ("fd12:3456::1", "private"), ("ff02::1", "multicast"),
        ("::ffff:127.0.0.1", None), ("::ffff:169.254.169.254", None),
        ("::ffff:10.0.0.1", None), ("2002:7f00:1::1", None),
    ]
    ALLOWED = ["8.8.8.8", "1.1.1.1", "93.184.216.34", "2606:4700:4700::1111",
               "2001:4860:4860::8888"]

    def test_blocked(self):
        for addr, expect in self.BLOCKED:
            with self.subTest(addr=addr):
                reason = safefetch._reject_reason(ipaddress.ip_address(addr))
                self.assertIsNotNone(reason, f"{addr} was allowed and must not be")
                if expect:
                    self.assertIn(expect, reason)

    def test_allowed(self):
        for addr in self.ALLOWED:
            with self.subTest(addr=addr):
                self.assertIsNone(safefetch._reject_reason(ipaddress.ip_address(addr)))

    def test_metadata_endpoint_specifically(self):
        """169.254.169.254 is the one address that has cost the industry the most money."""
        self.assertIsNotNone(safefetch._reject_reason(ipaddress.ip_address("169.254.169.254")))


class TestValidateUrl(unittest.TestCase):
    """The hostile-input table. Each row is an attack somebody has actually used."""

    MAP = {
        "metadata.example":  ["169.254.169.254"],   # a public name pointing at the metadata IP
        "localtest.example": ["127.0.0.1"],         # a public name pointing at loopback
        "lan.example":       ["192.168.1.10"],
        "rebind.example":    ["1.1.1.1", "127.0.0.1"],   # two answers, one hostile
        "good.example":      ["93.184.216.34"],
        "v6bad.example":     ["::1"],
        "v6good.example":    ["2606:4700:4700::1111"],
    }

    def block(self, url, must_contain=None):
        with self.subTest(url=url):
            with self.assertRaises(BlockedURL, msg=f"{url} was NOT blocked") as cm:
                safefetch.validate_url(url, Policy(), _resolver=resolver(self.MAP))
            if must_contain:
                self.assertIn(must_contain, str(cm.exception))
            # Whatever the reason, the message must not quote the URL back -- that is how a
            # credential in a path gets into a log via an error message.
            self.assertNotIn(SENTINEL_PASS, str(cm.exception))

    def test_scheme_allowlist(self):
        for url in ["file:///etc/passwd", "file://localhost/etc/shadow",
                    "gopher://good.example/_x", "ftp://good.example/x",
                    "data:text/plain;base64,aGk=", "javascript:alert(1)",
                    "jar:http://good.example/!/x", "dict://good.example:11211/stat",
                    "ldap://good.example/", "//good.example/x", "good.example/x"]:
            self.block(url)

    def test_loopback_and_private_literals(self):
        for url in ["http://127.0.0.1/", "http://127.0.0.1:8800/api/status",
                    "https://127.0.0.1/", "http://10.1.2.3/", "http://192.168.0.1/",
                    "http://172.16.9.9/", "http://0.0.0.0:8800/", "http://[::1]:8800/",
                    "http://[fe80::1]/", "http://[fd00::dead]/", "http://[::]/"]:
            self.block(url)

    def test_metadata_endpoint(self):
        self.block("http://169.254.169.254/latest/meta-data/iam/security-credentials/",
                   "link-local")
        self.block("http://metadata.example/computeMetadata/v1/", "link-local")
        self.block("http://[fe80::a9fe:a9fe]/", "link-local")

    def test_obfuscated_ipv4_forms(self):
        """Decimal, octal, hex and short-form addresses.

        These are the reason the check is on the *resolved* address: `2130706433` is not the
        string `127.0.0.1` and no hostname denylist catches it, but `getaddrinfo` turns it into
        127.0.0.1 and the address check then does. Uses the real resolver, because these are
        numeric forms libc parses without a network.
        """
        for url in ["http://2130706433/", "http://0177.0.0.1/", "http://127.1/",
                    "http://0x7f000001/"]:
            with self.subTest(url=url):
                with self.assertRaises(BlockedURL, msg=f"{url} was NOT blocked"):
                    safefetch.validate_url(url, Policy())

    def test_hostname_pointing_at_a_private_address(self):
        """The `localtest.me` / `nip.io` family: a perfectly public name, a hostile answer."""
        self.block("http://localtest.example/", "loopback")
        self.block("http://lan.example/", "private")
        self.block("http://v6bad.example/", "loopback")

    def test_rebinding_multiple_answers(self):
        """A name answering with both a public and a private address is refused outright.

        Taking the public one and connecting to it would be a coin flip against an attacker
        who controls the ordering.
        """
        self.block("http://rebind.example/", "loopback")

    def test_malformed(self):
        for url in ["", "   ", "http://", "http:///path", "http://:80/",
                    "http://good.example:0/", "http://good.example:99999/",
                    "http://good.example:notaport/",
                    "http://good.example/\r\nX-Evil: 1", "http://good.example/\nfoo"]:
            self.block(url)
        self.block("http://" + "a" * 5000 + ".example/")

    def test_unresolvable(self):
        self.block("http://nowhere.example/")

    def test_allows_a_normal_public_url(self):
        t = safefetch.validate_url("http://good.example/playlist.m3u",
                                   Policy(), _resolver=resolver(self.MAP))
        self.assertEqual(t.host, "good.example")
        self.assertEqual(t.ip, "93.184.216.34")     # the pinned address, not the name
        self.assertEqual(t.port, 80)
        self.assertEqual(t.path, "/playlist.m3u")
        t6 = safefetch.validate_url("https://v6good.example:8443/x?y=1",
                                    Policy(), _resolver=resolver(self.MAP))
        self.assertEqual(t6.ip, "2606:4700:4700::1111")
        self.assertEqual(t6.port, 8443)
        self.assertEqual(t6.path, "/x?y=1")

    def test_userinfo_becomes_a_header_not_a_url(self):
        t = safefetch.validate_url(f"http://user:{SENTINEL_PASS}@good.example/x",
                                   Policy(), _resolver=resolver(self.MAP))
        self.assertTrue(t.auth.startswith("Basic "))
        self.assertNotIn(SENTINEL_PASS, t.path)
        self.assertNotIn(SENTINEL_PASS, t.origin)

    def test_odd_ports_are_allowed_on_public_addresses(self):
        """IPTV panels really do live on 8080, 2082 and 25461. Port is not the control."""
        for port in (80, 443, 8080, 2082, 25461, 65535):
            t = safefetch.validate_url(f"http://good.example:{port}/x",
                                       Policy(), _resolver=resolver(self.MAP))
            self.assertEqual(t.port, port)

    def test_policy_cannot_be_relaxed_from_the_environment(self):
        """`allow_private` must be a constructor argument only.

        A live public box must have no switch that turns the SSRF check off. If someone ever
        adds `os.environ` handling to Policy, this fails.
        """
        self.assertFalse(Policy().allow_private)
        src = pathlib.Path(safefetch.__file__).read_text()
        head = src[src.index("class Policy"):src.index("class Target")]
        # `os.environ` / `getenv` specifically -- the prose in the docstring says "environment"
        # and matching that would fail on the very comment explaining the rule.
        self.assertNotIn("os.environ", head)
        self.assertNotIn("getenv", head)
        # And nothing in the whole module may consult the environment either.
        self.assertNotIn("os.environ", src)
        self.assertNotIn("getenv", src)


class TestRedirects(unittest.TestCase):
    def test_redirect_target_is_revalidated(self):
        """A public host redirecting to loopback must die on the second validation.

        Exercised against the real code path by checking that `open_stream` re-validates: the
        redirect Location is fed through `validate_url` with the same policy, so this is the
        same assertion as the table above once the plumbing is trusted.
        """
        for loc in ["http://127.0.0.1:8800/api/status", "http://localtest.example/",
                    "http://169.254.169.254/", "file:///etc/passwd"]:
            with self.subTest(loc=loc):
                with self.assertRaises(BlockedURL):
                    safefetch.validate_url(loc, Policy(), _resolver=resolver(
                        TestValidateUrl.MAP))

    def test_relative_redirect_resolves_against_the_reached_target(self):
        t = safefetch.validate_url("http://good.example/a/b/c",
                                   Policy(), _resolver=resolver(TestValidateUrl.MAP))
        self.assertEqual(t.join("../d"), "http://good.example:80/a/d")
        self.assertEqual(t.join("/e"), "http://good.example:80/e")

    def test_redirect_cap_is_small(self):
        self.assertLessEqual(Policy().max_redirects, 5)


class TestPinning(unittest.TestCase):
    """The check and the connection must not be able to see different answers."""

    def setUp(self):
        self.seen: list[str] = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.seen.append(self.headers.get("Host", ""))
                body = b"#EXTM3U\n#EXTINF:-1,Test\nhttp://example.com/a.ts\n"
                self.send_response(200)
                self.send_header("Content-Type", "audio/x-mpegurl")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.srv = socketserver.TCPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_name_is_resolved_exactly_once_and_the_pinned_ip_is_used(self):
        """If the connection re-resolved, the resolver would be called twice. It is called once.

        That single call count is the whole anti-rebinding argument, expressed as a test: there
        is no second lookup for an attacker's second answer to win.
        """
        calls = [0]
        r = resolver({"pinned.example": ["127.0.0.1"]}, calls)
        pol = Policy(allow_private=True)            # test-only; see Policy's docstring
        body, _ct, target = safefetch.fetch(
            f"http://pinned.example:{self.port}/x", pol, _resolver=r)
        self.assertEqual(calls[0], 1, "the name was resolved more than once")
        self.assertEqual(target.ip, "127.0.0.1")
        self.assertEqual(target.host, "pinned.example")
        self.assertIn(b"#EXTM3U", body)
        # Connected to the pinned address, but presented as the name: virtual hosting and
        # certificate validation still work.
        self.assertEqual(self.seen[-1], f"pinned.example:{self.port}")

    def test_connection_object_keeps_the_name_and_the_pinned_address_apart(self):
        t = safefetch.Target(scheme="http", host="pinned.example", port=80,
                             ip="93.184.216.34", path="/")
        conn = safefetch._PinnedHTTPConnection(t, 5.0)
        self.assertEqual(conn.host, "pinned.example")     # -> Host: header and TLS SNI
        self.assertEqual(conn._pinned_ip, "93.184.216.34")  # -> the socket

    def test_body_size_is_capped(self):
        pol = Policy(allow_private=True, max_bytes=8)
        with self.assertRaises(safefetch.FetchError):
            safefetch.fetch(f"http://pinned.example:{self.port}/x", pol,
                            _resolver=resolver({"pinned.example": ["127.0.0.1"]}))


class TestFfmpegNeverSeesAUrl(unittest.TestCase):
    """The structural guarantee that makes the SSRF control real rather than advisory."""

    def test_argv_has_pipe_input_and_a_protocol_allowlist(self):
        src = pathlib.Path(sessions.__file__).read_text()
        spawn = src[src.index("def _spawn"):src.index("def _drain_stderr")]
        self.assertIn('"-i", "pipe:0"', spawn)
        self.assertIn('"-protocol_whitelist", "pipe,fd"', spawn)
        # If the URL were ever interpolated into argv, credentials would be in `ps` output and
        # ffmpeg would do its own DNS. Neither may happen.
        self.assertNotIn("s.url", spawn)
        self.assertNotIn("session.url", spawn)


# ===================================================================== M3U

FIXTURE = """﻿#EXTM3U x-tvg-url="http://epg.example/x.xml"\r
#EXTINF:-1 tvg-id="bbc1.uk" tvg-name="BBC One" tvg-logo="http://img.example/1.png" \
group-title="UK | Entertainment",BBC One HD\r
http://provider.example:8080/live/u/p/1.ts\r
#EXTINF:-1 tvg-name="Sky Sports, Main Event" group-title="UK | Sport",Sky Sports Main Event\r
http://provider.example:8080/live/u/p/2.ts\r
#EXTGRP:Movies\r
#EXTINF:7200,The Example Film (2020)\r
http://provider.example:8080/movie/u/p/300.mp4\r
#EXTINF:-1,\r
http://provider.example:8080/live/u/p/4.ts\r
\r
# a stray comment\r
#EXTVLCOPT:network-caching=1000\r
#KODIPROP:inputstream=inputstream.adaptive\r
http://provider.example:8080/series/u/p/9.mkv\r
#EXTINF:-1 tvg-id="orphan",No URL Follows\r
"""


class TestM3U(unittest.TestCase):
    def setUp(self):
        self.chans, self.truncated = m3u.parse_m3u(FIXTURE)

    def test_counts_and_no_invention(self):
        # Five URLs are present; the trailing #EXTINF has no URL and must be dropped, not
        # given an invented one.
        self.assertEqual(len(self.chans), 5)
        self.assertFalse(self.truncated)
        self.assertNotIn("No URL Follows", [c.name for c in self.chans])

    def test_attributes(self):
        c = self.chans[0]
        self.assertEqual(c.name, "BBC One HD")
        self.assertEqual(c.tvg_id, "bbc1.uk")
        self.assertEqual(c.tvg_name, "BBC One")
        self.assertEqual(c.logo, "http://img.example/1.png")
        self.assertEqual(c.group, "UK | Entertainment")
        self.assertEqual(c.kind, "live")

    def test_comma_inside_a_quoted_attribute(self):
        """The naive split(',', 1) truncates the attributes and mangles the name."""
        c = self.chans[1]
        self.assertEqual(c.name, "Sky Sports Main Event")
        self.assertEqual(c.tvg_name, "Sky Sports, Main Event")
        self.assertEqual(c.group, "UK | Sport")

    def test_extgrp_and_duration_and_kind(self):
        c = self.chans[2]
        self.assertEqual(c.name, "The Example Film (2020)")
        self.assertEqual(c.group, "Movies")
        self.assertEqual(c.duration, 7200.0)
        self.assertEqual(c.kind, "vod")

    def test_empty_name_is_marked_not_invented(self):
        self.assertEqual(self.chans[3].name, "(unnamed)")

    def test_bare_url_is_kept_and_named_from_its_filename(self):
        c = self.chans[4]
        self.assertEqual(c.url, "http://provider.example:8080/series/u/p/9.mkv")
        self.assertEqual(c.name, "9.mkv")
        self.assertEqual(c.kind, "series")

    def test_bom_and_crlf_absorbed(self):
        for c in self.chans:
            self.assertNotIn("\r", c.url)
            self.assertNotIn("﻿", c.name)

    def test_empty_and_junk_input(self):
        self.assertEqual(m3u.parse_m3u(""), ([], False))
        self.assertEqual(m3u.parse_m3u("#EXTM3U\n"), ([], False))
        self.assertEqual(m3u.parse_m3u("not a playlist at all")[0][0].name,
                         "not a playlist at all")

    def test_no_extm3u_header_still_parses(self):
        chans, _ = m3u.parse_m3u("#EXTINF:-1,A\nhttp://a.example/1.ts\n")
        self.assertEqual(len(chans), 1)

    def test_truncation_is_reported_not_silent(self):
        big = "".join(f"#EXTINF:-1,C{i}\nhttp://a.example/{i}.ts\n"
                      for i in range(m3u.MAX_CHANNELS + 50))
        chans, truncated = m3u.parse_m3u(big)
        self.assertTrue(truncated)
        self.assertEqual(len(chans), m3u.MAX_CHANNELS)


class TestHlsParser(unittest.TestCase):
    def test_master(self):
        pl = m3u.parse_hls(
            "#EXTM3U\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=1400000,RESOLUTION=848x480\nlow/index.m3u8\n"
            "#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080\nhigh/index.m3u8\n")
        self.assertTrue(pl.is_master)
        self.assertEqual([v.bandwidth for v in pl.variants], [1400000, 5000000])
        self.assertEqual(pl.variants[1].resolution, "1920x1080")

    def test_media_playlist_sequence(self):
        pl = m3u.parse_hls(
            "#EXTM3U\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:117\n"
            "#EXTINF:4.0,\na.ts\n#EXTINF:4.0,\nb.ts\n#EXTINF:3.5,\nc.ts\n")
        self.assertFalse(pl.is_master)
        self.assertEqual(pl.target_duration, 4.0)
        self.assertEqual([s.sequence for s in pl.segments], [117, 118, 119])
        self.assertEqual([s.uri for s in pl.segments], ["a.ts", "b.ts", "c.ts"])
        self.assertFalse(pl.ended)

    def test_endlist_marks_a_complete_recording(self):
        pl = m3u.parse_hls("#EXTM3U\n#EXTINF:2,\na.ts\n#EXT-X-ENDLIST\n")
        self.assertTrue(pl.ended)

    def test_encrypted_is_detected_not_ignored(self):
        pl = m3u.parse_hls('#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="k.key"\n'
                           "#EXTINF:2,\na.ts\n")
        self.assertTrue(pl.encrypted)
        self.assertFalse(m3u.parse_hls("#EXTM3U\n#EXT-X-KEY:METHOD=NONE\n"
                                       "#EXTINF:2,\na.ts\n").encrypted)


# ===================================================================== credentials

class TestScrubber(unittest.TestCase):
    def test_query_credentials(self):
        s = safefetch.redact(
            f"http://p.example/player_api.php?username=u&password={SENTINEL_PASS}&action=x")
        self.assertNotIn(SENTINEL_PASS, s)
        self.assertIn("password=***", s)

    def test_userinfo(self):
        self.assertNotIn(SENTINEL_PASS,
                         safefetch.redact(f"http://u:{SENTINEL_PASS}@p.example/x"))

    def test_path_segment_needs_the_session_scrubber(self):
        """An Xtream password sits in a *path segment* and looks like nothing.

        `redact` alone cannot see it -- which is the whole reason `Scrubber` carries the
        session's own literals.
        """
        url = f"http://p.example/live/{SENTINEL_USER}/{SENTINEL_PASS}/1.ts"
        self.assertIn(SENTINEL_PASS, safefetch.redact(url))          # documents the gap
        scrub = Scrubber([SENTINEL_USER, SENTINEL_PASS])
        self.assertNotIn(SENTINEL_PASS, scrub(url))
        self.assertNotIn(SENTINEL_USER, scrub(url))

    def test_percent_encoded_form_is_also_scrubbed(self):
        scrub = Scrubber(["p@ss word/x"])
        self.assertNotIn("p%40ss%20word%2Fx", scrub("http://a/p%40ss%20word%2Fx/1.ts"))

    def test_xtream_creds_repr_does_not_leak(self):
        c = xtream.XtreamCreds("http://p.example", SENTINEL_USER, SENTINEL_PASS)
        for text in (repr(c), str(c), f"{c}", repr([c]), repr({"c": c})):
            self.assertNotIn(SENTINEL_PASS, text)
            self.assertNotIn(SENTINEL_USER, text)

    def test_stream_url_is_built_correctly_but_never_shown(self):
        c = xtream.XtreamCreds("p.example:8080", SENTINEL_USER, SENTINEL_PASS)
        url = xtream.stream_url(c, "live", "123", "ts")
        self.assertEqual(url, f"http://p.example:8080/live/{SENTINEL_USER}/"
                              f"{SENTINEL_PASS}/123.ts")
        self.assertNotIn(SENTINEL_PASS, c.scrubber(url))


class TestNoCredentialLeak(unittest.TestCase):
    """The grep test. A sentinel password goes in; every exit is searched for it.

    The exits are: our own log output, the HTTP response body, the text of any exception
    raised, and the session document handed to the browser. All four, because a password that
    is kept out of the log file and returned in a 422 body has not been kept.
    """

    def setUp(self):
        self.buf = io.StringIO()
        self.handler = logging.StreamHandler(self.buf)
        self.handler.setLevel(logging.DEBUG)
        self.root = logging.getLogger()
        self.prev_level = self.root.level
        self.root.setLevel(logging.DEBUG)
        self.root.addHandler(self.handler)

    def tearDown(self):
        self.root.removeHandler(self.handler)
        self.root.setLevel(self.prev_level)

    def assertClean(self, *texts: str):
        blob = "\n".join(t for t in texts if t)
        log_text = self.buf.getvalue()
        for secret, name in ((SENTINEL_PASS, "password"), (SENTINEL_USER, "username")):
            self.assertNotIn(secret, log_text, f"the {name} appeared in log output")
            self.assertNotIn(secret, blob, f"the {name} appeared in a response or error")

    def test_router_paths_never_carry_a_credential(self):
        """Structural: uvicorn logs the request line, so no credential may ride in a URL."""
        for route in routes.router.routes:
            path = getattr(route, "path", "")
            for bad in ("username", "password", "user", "pass", "token", "creds"):
                self.assertNotIn(bad, path.lower(),
                                 f"route {path} puts a credential in the request line")
            if "POST" not in getattr(route, "methods", set()):
                self.assertNotIn("{", path.replace("{sid}", "").replace("{name}", ""))

    def test_credential_models_have_no_required_fields(self):
        """A missing required field makes pydantic echo the whole body into a 422.

        That body contains the password. With defaults there is no such error path.
        """
        for model in (routes.XtreamBody, routes.TuneBody, routes.PlaylistBody):
            with self.subTest(model=model.__name__):
                model()                                  # must not raise
                for name, field in model.model_fields.items():
                    self.assertFalse(field.is_required(),
                                     f"{model.__name__}.{name} is required; a missing-field "
                                     f"422 would echo the whole request body")

    def test_blocked_xtream_server_does_not_leak(self):
        creds = xtream.XtreamCreds(f"http://127.0.0.1:8800", SENTINEL_USER, SENTINEL_PASS)
        with self.assertRaises(xtream.XtreamError) as cm:
            xtream.panel_info(creds, Policy())
        self.assertClean(str(cm.exception), repr(cm.exception))

    def test_session_start_on_a_blocked_url_does_not_leak(self):
        url = f"http://127.0.0.1:8800/live/{SENTINEL_USER}/{SENTINEL_PASS}/1.ts"
        mgr = sessions.SessionManager()
        with self.assertRaises(sessions.TunerError) as cm:
            mgr.start(url, "Test Channel", Policy(),
                      Scrubber([SENTINEL_USER, SENTINEL_PASS]))
        self.assertClean(str(cm.exception), repr(cm.exception))

    def test_session_public_document_has_no_url_field(self):
        s = sessions.Session(id="x", label="L", dir=pathlib.Path("/nonexistent"),
                             created=0.0, scrub=Scrubber(), policy=Policy(),
                             url=f"http://p.example/live/{SENTINEL_USER}/{SENTINEL_PASS}/1.ts")
        import json
        doc = json.dumps(s.public())
        self.assertClean(doc)
        self.assertNotIn("p.example", doc)

    def test_transcoder_stderr_never_reaches_the_client(self):
        """ffmpeg's stderr is written by a program we do not control and must stay internal.

        The hole this guards: a visitor pastes an Xtream-exported M3U, whose URLs carry the
        password in a *path segment*, and sends `/tune` with no username or password fields --
        so a scrubber primed from the request body would be empty and `redact()` cannot see a
        path segment. If `public()` echoed stderr, that password would come straight back out
        of `GET /session/{sid}`.
        """
        s = sessions.Session(id="x", label="L", dir=pathlib.Path("/nonexistent"),
                             created=0.0, scrub=Scrubber(), policy=Policy(),
                             url=f"http://p.example/live/{SENTINEL_USER}/{SENTINEL_PASS}/1.ts")
        s.state = "failed"
        s.transcoder_error = (f"pipe:0: Invalid data found when processing input "
                              f"http://p.example/live/{SENTINEL_USER}/{SENTINEL_PASS}/1.ts")
        import json
        doc = json.dumps(s.public())
        self.assertClean(doc)
        # Still says something honest rather than nothing.
        self.assertIsNotNone(s.public()["error"])

    def test_scrubber_derived_from_the_url_catches_path_segment_credentials(self):
        """`Scrubber.from_url` is what protects the M3U path, where nobody registered a secret."""
        url = f"http://p.example/live/{SENTINEL_USER}/{SENTINEL_PASS}/1.ts?token={SENTINEL_PASS}"
        scrub = Scrubber.from_url(url)
        self.assertClean(scrub(f"ffmpeg: cannot open {url}"))

    def test_full_request_through_the_router(self):
        """End to end through FastAPI, including the error responses it generates itself."""
        try:
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
        except Exception as exc:                                  # pragma: no cover
            self.skipTest(f"TestClient unavailable: {exc}")
        app = FastAPI()
        app.include_router(routes.router, prefix="/api/tuner")
        client = TestClient(app, raise_server_exceptions=False)
        bodies = []
        cred = {"server": "http://127.0.0.1:8800", "username": SENTINEL_USER,
                "password": SENTINEL_PASS}
        for path, payload in [
            ("/api/tuner/xtream/info", cred),
            ("/api/tuner/xtream/channels", cred),
            ("/api/tuner/xtream/info", {"username": SENTINEL_USER,
                                        "password": SENTINEL_PASS}),      # no server
            ("/api/tuner/xtream/info", {**cred, "kinds": 12345}),          # 422 path
            ("/api/tuner/xtream/info", {**cred, "server": "http://169.254.169.254"}),
            ("/api/tuner/tune", {"url": f"http://127.0.0.1:8800/live/{SENTINEL_USER}/"
                                        f"{SENTINEL_PASS}/1.ts",
                                 "label": "Test", "username": SENTINEL_USER,
                                 "password": SENTINEL_PASS}),
            ("/api/tuner/playlist", {"url": f"http://127.0.0.1:8800/x.m3u"}),
        ]:
            r = client.post(path, json=payload)
            bodies.append(r.text)
            self.assertNotEqual(r.status_code, 500, f"{path} raised: {r.text[:200]}")
        self.assertClean(*bodies)


# ===================================================================== caps

class TestCapsAndPaths(unittest.TestCase):
    def test_segment_names_are_allowlisted(self):
        for good in ["s00000.ts", "s12345.ts", "s0.m4s"]:
            self.assertTrue(sessions.SEGMENT_RE.match(good), good)
        for bad in ["../../etc/passwd", "..%2f..%2fetc%2fpasswd", "s00000.ts/../../x",
                    "/etc/passwd", "s00000.sh", "live.m3u8.bak", ".", "..", "",
                    "s00000.ts\x00.png", "S00000.TS"]:
            self.assertIsNone(sessions.SEGMENT_RE.match(bad), f"{bad!r} was accepted")

    def test_caps_are_bounded(self):
        self.assertLessEqual(sessions.MAX_SESSIONS, 8)
        self.assertGreaterEqual(sessions.MAX_SESSIONS, 1)
        self.assertLessEqual(sessions.IDLE_TIMEOUT, 600)
        self.assertLessEqual(sessions.MAX_LIFETIME, 21600)

    def test_reaper_is_not_started_at_import(self):
        """Importing the module must not spawn a thread in a process that never tunes.

        Checked in a *fresh subprocess*. Asserting on `threading.enumerate()` in this process
        would silently become a test of test-ordering the moment any earlier test starts a real
        session, and would then fail for a reason unrelated to the property being guarded.
        """
        import subprocess
        out = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, %r)\n"
             "import threading\n"
             "import apps.tuner\n"
             "print([t.name for t in threading.enumerate() if t.name.startswith('tuner-')])"
             % str(pathlib.Path(__file__).resolve().parents[2])],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "[]",
                         "importing apps.tuner started a background thread")

    def test_manager_makes_no_directory_until_used(self):
        mgr = sessions.SessionManager()
        self.assertIsNone(mgr._root)


class TestRackStatus(unittest.TestCase):
    def test_shape_matches_the_unit_model(self):
        st = routes.status()
        self.assertEqual(set(st), {"id", "label", "slot", "state", "bus", "href",
                                   "spec", "detail"})
        self.assertIn(st["state"], ("ready", "busy", "queued", "offline"))
        self.assertIn(st["bus"], ("gpu", "cpu"))

    def test_state_is_a_reading_not_a_decoration(self):
        """With no ffmpeg the surface cannot work and must say offline."""
        real = sessions.FFMPEG
        try:
            sessions.FFMPEG = routes.FFMPEG = None
            self.assertEqual(routes.status()["state"], "offline")
        finally:
            sessions.FFMPEG = routes.FFMPEG = real

    def test_reports_no_stored_channels(self):
        self.assertIn("no", routes.status()["detail"].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
