#!/usr/bin/env python3
"""SyMoNeuRaL Code -- the desktop window.

A GTK3 window with a VTE terminal in it, running `bin/symoneural-code`. That is the whole
program. It owns a window, a font, a palette and the keybindings a terminal widget does not
come with; it does not own a session, a turn, a transcript or a permission prompt, and the
reason it must never grow one is the only interesting thing about this file.

**Why a terminal and not a web view.** `desktop/README.md` measured four runtimes and chose
GTK3 + WebKit2GTK on footprint. The footprint reading stands; the runtime changed, and the
argument is recorded in that file under *The decision, revised*. Short form: a web client is
a second implementation of the permission gate. `approve()` in `bin/symoneural-cli` opens
`/dev/tty` deliberately -- not stdin, because in `agent "..."` stdin may be a pipe carrying
the query and in the repl it is the transcript, and neither absence of a tty means there is
nobody at the keyboard. A browser has no `/dev/tty`, so a JS client needs its own fresh
answer to *who is the human here*, and every fresh answer to that question is a new way to
fail open. VTE allocates a real pty, so the prompt, the four keys, the re-ask on an
unrecognised key and the refusal when the terminal goes away are the code already under test
in `backend/apps/test_symoneural_cli.py::ApprovePromptTests` rather than a parallel copy.

One gate, one engine, one session store. What this file adds is a window.

**What it deliberately does not do**, each because doing it would be a second
implementation of something that already exists exactly once:

  * no session list, no resume picker      -- `/resume` and `--sessions` in the client
  * no permission dialog                   -- `approve()`, on the pty this window provides
  * no transcript handling                 -- `run/agent-<session>.json`, written by the client
  * no API calls of its own                -- it has no idea what the API is; it spawns a child

**No decorative indicators.** The repo rule is that every light on a surface reflects a real
reading, and it applies to a window as much as to a page. The one piece of status here is the
child's exit code, which arrives on VTE's `child-exited` signal and is a fact. There is no
connection light, because this window holds no connection.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gdk, GLib, Gtk, Pango, Vte  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# The same assert the CLI makes, for the same reason: the repo root has been computed wrongly
# four times in this repo and it fails silently, because the wrong parent is usually a
# directory that exists. A window that opens onto a shell in the wrong tree is worse than one
# that refuses to open.
assert (ROOT / "bin" / "symoneural-code").is_file(), f"repo root not found at {ROOT}"

LAUNCHER = ROOT / "bin" / "symoneural-code"

# `site/symoneural.css`, so the window and the site are the same product rather than two
# things that happen to share a name. Each is that file's token, copied by value and named
# here -- GTK cannot read CSS custom properties out of a stylesheet, so this is a copy, and
# the comment is what makes it a traceable one.
BG = "#0e100f"          # --bg
FG = "#f2f6f3"          # --fg
DIM = "#a8b3ac"         # --dim
ACCENT = "#2ee08a"      # --accent
AMBER = "#ffab3d"       # --amber
PANEL = "#161a18"       # --panel
LINE = "#28302b"        # --line

# The 16-colour palette VTE hands the child, built from the same tokens. The client only ever
# emits bold, dim, green and amber -- see `BOLD, DIM, GREEN, AMBER` in `bin/symoneural-cli` --
# so those four are the ones that had to be right; the rest are filled in consistently so that
# anything else run in this window (a pager, `git`, a compiler) is legible rather than lurid.
PALETTE = [
    "#161a18", "#ff6b6b", ACCENT, AMBER, "#5aa9e6", "#c792ea", "#4fd6d6", DIM,
    "#3a443e", "#ff8f8f", "#6ff0a8", "#ffc169", "#82c4f0", "#dcb3f5", "#8ae8e8", FG,
]

FONT = "monospace 11"
SCROLLBACK = 100_000    # lines. A turn with three tool calls is long, and losing the top of
                        # it to a default of 512 would mean the answer scrolled off the
                        # record while the reader was still reading the tool output.
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.5, 3.0, 0.1


def rgba(spec: str) -> Gdk.RGBA:
    colour = Gdk.RGBA()
    if not colour.parse(spec):
        raise ValueError(f"not a colour: {spec!r}")
    return colour


class Window(Gtk.Window):
    """The window. One terminal, one child, one exit code."""

    def __init__(self, argv: list[str], *, cwd: Path):
        super().__init__(title="SyMoNeuRaL Code")
        self.set_default_size(1100, 740)
        self.set_icon_name("utilities-terminal")
        self.argv = argv
        self.cwd = cwd
        self.zoom = 1.0

        self.term = Vte.Terminal()
        self.term.set_scrollback_lines(SCROLLBACK)
        self.term.set_font(Pango.FontDescription(FONT))
        self.term.set_colors(rgba(FG), rgba(BG), [rgba(x) for x in PALETTE])
        self.term.set_color_cursor(rgba(ACCENT))
        self.term.set_cursor_blink_mode(Vte.CursorBlinkMode.OFF)
        self.term.set_mouse_autohide(True)
        # Wrap rather than clip, which is the terminal spelling of a rule this repo states for
        # CSS: a layout change may not drop data, and `text-overflow: ellipsis` on a detail
        # line is data loss with extra steps. A tool result or a licence attribution that runs
        # past the right edge must arrive on the next line, not be cut.
        self.term.set_word_char_exceptions("-A-Za-z0-9,./?%&#:_=+@~")
        self.term.connect("child-exited", self.on_child_exited)
        # The client prints urls (`api  http://127.0.0.1:8800`, and both halves of every link
        # in a rendered answer). Making them clickable is the one affordance a terminal in a
        # window has over a terminal in a tab, and it costs nothing.
        try:
            self.term.connect("hyperlink-hover-uri-changed", lambda *_: None)
            self.term.set_allow_hyperlink(True)
        except (AttributeError, TypeError):
            pass                            # older VTE: links stay text, nothing else changes

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.term)

        self.status = Gtk.Label(xalign=0.0)
        self.status.set_selectable(True)
        self.status.set_markup(self.status_markup(f"{LAUNCHER.name} in {cwd}"))
        bar = Gtk.EventBox()
        bar.add(self.status)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(scroller, True, True, 0)
        box.pack_start(bar, False, False, 0)
        self.add(box)

        self.style()
        self.connect("key-press-event", self.on_key)
        self.connect("delete-event", self.on_delete)
        self.connect("destroy", lambda *_: Gtk.main_quit())

    # -- appearance -----------------------------------------------------------------------

    def style(self) -> None:
        css = f"""
        window {{ background-color: {BG}; }}
        label {{ color: {DIM}; font-family: monospace; font-size: 10.5pt;
                 padding: 4px 10px; }}
        eventbox {{ background-color: {PANEL}; border-top: 1px solid {LINE}; }}
        """.encode()
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def status_markup(self, text: str, colour: str = DIM) -> str:
        return f'<span foreground="{colour}">{GLib.markup_escape_text(text)}</span>'

    def apply_zoom(self) -> None:
        font = Pango.FontDescription(FONT)
        font.set_size(int(font.get_size() * self.zoom))
        self.term.set_font(font)

    # -- the child ------------------------------------------------------------------------

    def start(self) -> None:
        """Spawn the launcher on this window's pty.

        `Vte.PtyFlags.DEFAULT` is what makes the child's terminal a real controlling terminal,
        which is the entire point of this window: `approve()` opens `/dev/tty` and finds it.
        """
        env = [f"{k}={v}" for k, v in os.environ.items() if "\n" not in v]
        # Two things the child is told about the window it is in. TERM so that curses-ish
        # programs and readline behave, and a marker so a client can tell -- honestly, from
        # its environment rather than by guessing -- that it was launched from the desktop
        # entry. Nothing reads the marker yet; it is here so that when something does, it does
        # not have to infer it from the shape of stdin.
        env = [e for e in env if not e.startswith(("TERM=", "SYMONEURAL_DESKTOP="))]
        env += ["TERM=xterm-256color", "SYMONEURAL_DESKTOP=1"]
        self.term.spawn_async(
            Vte.PtyFlags.DEFAULT,
            str(self.cwd),
            [str(LAUNCHER), *self.argv],
            env,
            # DEFAULT, not DO_NOT_REAP_CHILD. VTE reaps the child itself -- that is what
            # raises `child-exited` with a status -- and passing the flag makes
            # `vte_pty_spawn_with_fds_async` fail its own runtime check and spawn
            # nothing, leaving a black window and one warning on stderr that a desktop
            # launcher throws away. Measured that way round before it was written.
            GLib.SpawnFlags.DEFAULT,
            None, None,
            -1,
            None,
            self.on_spawned,
        )

    def on_spawned(self, _term, pid, error, *_) -> None:
        if error is not None:
            # Reported into the window rather than only to stderr. A desktop launcher has no
            # terminal behind it, so a message on stderr goes to the journal and the user sees
            # an empty black rectangle -- which reads as a hang, and is the one failure mode a
            # GUI must not have.
            self.status.set_markup(self.status_markup(
                f"could not start {LAUNCHER}: {error.message}", AMBER))
            self.term.feed(f"\r\n  could not start {LAUNCHER}\r\n  {error.message}\r\n"
                           .encode())
            return
        self.pid = pid
        self.status.set_markup(self.status_markup(f"{LAUNCHER.name}  pid {pid}  {self.cwd}"))

    def on_child_exited(self, _term, status: int) -> None:
        """The only status this window reports, because it is the only one it knows.

        The window stays open on a non-zero exit. Closing it would take the scrollback with
        it, and the scrollback is where the reason is -- a client that failed and a window
        that vanished is a bug report nobody can write.
        """
        if status == 0:
            self.status.set_markup(self.status_markup("session ended -- close this window"))
            self.destroy()
            return
        self.status.set_markup(self.status_markup(
            f"the client exited {status}; the scrollback above is kept", AMBER))

    def on_delete(self, *_) -> bool:
        """`False` -- let it close, and let the child get its SIGHUP from the pty closing.

        No confirmation dialog. A turn in flight is abandoned, which is exactly what Ctrl-C in
        the session does and what the client already documents: `cmd_agent` writes the thread
        only after a complete answer, so an interrupted turn leaves nothing half-recorded.
        There is nothing to lose that a dialog would be protecting.
        """
        return False

    # -- keys -----------------------------------------------------------------------------

    def on_key(self, _widget, event) -> bool:
        """The bindings VTE does not come with. Ctrl-Shift for the window's own, so that plain
        Ctrl-C reaches the child -- which is the binding the session actually needs, since
        Ctrl-C is how a turn is abandoned without leaving the session."""
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(event.state & Gdk.ModifierType.SHIFT_MASK)
        key = Gdk.keyval_name(event.keyval) or ""
        if not ctrl:
            return False
        if shift and key in ("C", "c"):
            self.term.copy_clipboard_format(Vte.Format.TEXT)
            return True
        if shift and key in ("V", "v"):
            self.term.paste_clipboard()
            return True
        if key in ("plus", "equal", "KP_Add"):
            self.zoom = min(ZOOM_MAX, self.zoom + ZOOM_STEP)
            self.apply_zoom()
            return True
        if key in ("minus", "KP_Subtract"):
            self.zoom = max(ZOOM_MIN, self.zoom - ZOOM_STEP)
            self.apply_zoom()
            return True
        if key == "0":
            self.zoom = 1.0
            self.apply_zoom()
            return True
        return False


def parse(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    ap = argparse.ArgumentParser(
        prog="symoneural-code-desktop",
        description="SyMoNeuRaL Code in a window. Everything after `--` goes to the client "
                    "verbatim, so `--url`, `-r ID` and `--sessions` work exactly as they do "
                    "in a terminal.",
        epilog="The window owns no session and no permission prompt: it hosts "
               "bin/symoneural-code on a real pty. See desktop/README.md.")
    ap.add_argument("--cwd", default=None,
                    help="working directory for the session (default: where this was "
                         "launched from, or the repo root when that is not a real place -- "
                         "a desktop entry starts in $HOME or in /)")
    return ap.parse_known_args(argv)


def main(argv: list[str] | None = None) -> int:
    args, rest = parse(sys.argv[1:] if argv is None else argv)
    if rest and rest[0] == "--":
        rest = rest[1:]
    cwd = Path(args.cwd).expanduser() if args.cwd else Path.cwd()
    if not cwd.is_dir():
        cwd = ROOT
    win = Window(rest, cwd=cwd)
    win.show_all()
    win.start()
    # The terminal takes focus, not the status label. Without this the first keystroke of the
    # first question goes to a Gtk.Label, silently.
    win.term.grab_focus()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
