#!/usr/bin/env node
// tests/code_cli.mjs -- the interactive terminal client, driven the way a user drives it.
//
// Deliberately NOT a Playwright suite. Playwright drives browsers; this drives a process:
// `node:child_process` writes stdin and reads stdout, with the pipe making `_tty()` false so
// there is no ANSI to strip out of an assertion. Garrett's *"we should be able to make it just
// like claude using playwright"* lands on the desktop half of task #78, where Playwright's
// Electron API is the measuring instrument; contorting a terminal suite into a browser one
// would test the harness rather than the client.
//
// Two of the assertions here are regression guards rather than new behaviour, and they are the
// reason this file exists at all. Making a bare `symoneural-cli` open a session means removing
// argparse's `required=True`, and a script that runs `symoneural-cli "$CMD"` with CMD unset
// used to get exit 2 and usage. If it instead got a client reading stdin, that script would
// block forever, in cron, silently. So: no terminal on stdin, no session -- and these two
// assertions are what stop that guarantee being refactored away by someone who never knew it
// was load-bearing.
//
// Usage:  node tests/code_cli.mjs [http://127.0.0.1:8877]
//
// With no URL the live-turn assertions are SKIPPED and counted out of the total, because
// "19/19 passed" when three never ran is exactly the carried-figure failure this repo bans.
// With a URL, SYMONEURAL_STUDIO_TOKEN must match that API's or the turns cannot run.

import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const CLI = join(ROOT, 'bin', 'symoneural-cli');
const CODE = join(ROOT, 'bin', 'symoneural-code');
const BASE = process.argv[2] || null;
const TOKEN = process.env.SYMONEURAL_STUDIO_TOKEN || '';

const results = [];
const record = (name, ok, detail = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'ok  ' : 'FAIL'}  ${name}${detail ? `  -- ${detail}` : ''}`);
};
const skip = (name, why) => {
  results.push({ name, ok: true, skipped: true });
  console.log(`SKIP  ${name}  -- ${why}`);
};

// `stdin` is written and then closed, which is Ctrl-D: every scripted session below ends by
// end-of-input unless it types /exit, and both paths are asserted.
function run(args, { stdin = '', tty = false, env = {}, bin = CLI } = {}) {
  const spec = tty
    ? ['script', ['-qec', [bin, ...args].join(' '), '/dev/null']]
    : [bin, args];
  const r = spawnSync(spec[0], spec[1], {
    input: stdin, encoding: 'utf8', timeout: 60_000,
    env: { ...process.env, ...env },
  });
  // The pipe suppresses colour, but `script` allocates a pty and colour comes back.
  const strip = s => (s || '').replace(/\x1b\[[0-9;]*m/g, '');
  return { code: r.status, out: strip(r.stdout), err: strip(r.stderr) };
}

// ---- the two guards ------------------------------------------------------------------
{
  const r = run([], { stdin: '' });
  record('a bare invocation with no stdin tty exits 2, as it did before there was a repl',
         r.code === 2, `exit ${r.code}`);
  record('and it says why on stderr, naming both ways forward',
         /not a terminal/.test(r.err) && /--help/.test(r.err) && /repl/.test(r.err),
         r.err.split('\n').filter(Boolean).pop());
}
{
  const r = run(['']);
  record('an empty command string is still an argparse error, not a session',
         r.code === 2 && /invalid choice/.test(r.err), `exit ${r.code}`);
}
{
  const r = run(['status']);
  record('`status` in a script is untouched by any of this', r.code === 0, `exit ${r.code}`);
}
{
  const r = run(['--help']);
  record('`repl` is a real subcommand and appears in usage', /repl/.test(r.out));
}

// ---- the session ---------------------------------------------------------------------
{
  const r = run(['repl'], { stdin: '/exit\n' });
  record('a piped repl session opens, names its session id and its file, and exits 0',
         r.code === 0 && /session\s+code-\d{8}-\d{6}\s+->\s+agent-code-/.test(r.out),
         `exit ${r.code}`);
  record('and it closes by telling you the command that resumes it',
         /resume with `symoneural-cli repl --session code-/.test(r.out));
}
{
  const r = run(['repl'], { stdin: '' });   // stdin closed immediately == Ctrl-D
  record('end of input leaves the session cleanly, like Ctrl-D',
         r.code === 0 && /0 turns in code-/.test(r.out), `exit ${r.code}`);
}
{
  const r = run(['repl'], { stdin: '/help\n/exit\n' });
  const want = ['/help', '/clear', '/status', '/tools', '/model', '/resume', '/session',
                '/permissions', '/exit'];
  const missing = want.filter(v => !r.out.includes(v));
  record('/help lists every slash command the client answers',
         missing.length === 0, missing.length ? `missing ${missing.join(' ')}` : `${want.length} listed`);
  record('/help also documents the two things that are not commands: @path and continuation',
         /@path/.test(r.out) && /continues onto the next line/.test(r.out));
}
{
  const r = run(['repl', '--session', 'nosuchthread-xyz'], { stdin: '/session\n/exit\n' });
  record('/session reports an unwritten thread as unwritten rather than as empty',
         /0 messages/.test(r.out) && /not written yet/.test(r.out));
}
{
  const r = run(['repl'], { stdin: '/nope\n/exit\n' });
  record('an unknown slash command is refused by name and does not end the session',
         /\/nope: no such command/.test(r.out) && /0 turns in/.test(r.out));
}
{
  const r = run(['repl'], { stdin: '/model qwen-x\n/model\n/model -\n/model\n/exit\n' });
  const seen = r.out.match(/model: [^\n]*/g) || [];
  record('/model sets, reports and clears, and says the change is session-scoped',
         seen.length === 4 && /this session only/.test(seen[0])
           && /qwen-x/.test(seen[1]) && /backend default/.test(seen[3]),
         seen.join(' | '));
}
{
  const r = run(['repl'], { stdin: '/clear\n/exit\n' });
  const ids = r.out.match(/code-\d{8}-\d{6}/g) || [];
  record('/clear mints a new session id and says how many messages it dropped',
         /cleared 0 messages; new session code-/.test(r.out) && new Set(ids).size >= 1);
}
{
  const r = run(['repl'], { stdin: '/resume definitely-not-a-thread\n/resume\n/exit\n' });
  record('/resume refuses an id with no thread behind it',
         /no thread at .*agent-definitely-not-a-thread\.json/.test(r.out));
  record('/resume with no argument lists the recorded threads and marks the current one',
         /\/resume <id> to switch/.test(r.out));
}
// ---- the gate ------------------------------------------------------------------------
// The assertion that stood here said `/permissions` must state that nothing is gated yet. That
// was true when it was written and stopped being true when #78 item 3 landed, so it was red and
// the client was right -- a test asserting the absence of a feature has to be deleted by the
// commit that adds the feature, or it becomes a red that reads like a regression.
//
// Everything below is deterministic: no model, no API, no live tool call. A test that waits for
// the model to choose a gated tool is a coin flip in a suite, and the frame it would exercise is
// covered end to end in backend/apps/test_symoneural_cli.py, which drives the whole handshake
// against a scripted stream. What is left for this file is the operator surface: the setting, how
// it resolves, and where the gated list comes from.
{
  const r = run(['agent', '--permissions', 'bogus', 'hi']);
  record("the gate: an unrecognised --permissions is an argparse error, not a quiet default",
         r.code === 2 && /invalid choice/.test(r.err), `exit ${r.code}`);
}
{
  const r = run(['agent', '--help']);
  record("the gate: --dangerously-allow-all is in help and names what it turns off",
         /--dangerously-allow-all/.test(r.out)
           && /permissions allow/.test(r.out) && /delete_path/.test(r.out));
}
{
  const r = run(['repl'], { stdin: '/permissions\n/exit\n' });
  // The one that matters. `auto` with nobody at a terminal must fall to DENY. If it fell to
  // allow, every scripted invocation on this box would run delete_path unasked, and the failure
  // would be silent in exactly the direction that costs something. This is the client half of
  // the same rule the loop enforces with PERMISSION_MODES: no failing open.
  record("the gate: with no terminal to ask, auto resolves to deny and prints which",
         /permissions: auto -> deny/.test(r.out),
         (r.out.match(/permissions: [^\n]*/) || ['(no permissions line)'])[0]);
  // Not a hardcoded list, and it says so out loud when it cannot reach the server. A client
  // that printed its own copy of the gated set would drift from the registry that decides it,
  // and the drift is invisible until something dangerous is missing from the copy.
  record("the gate: the gated set is asked of the server, and says so when there is no server",
         /gated: unknown \(no api\)/.test(r.out),
         (r.out.match(/gated: [^\n]*/) || ['(no gated line)'])[0]);
  record("the gate: nothing is exempt until somebody exempts it",
         /exempt this session: nothing/.test(r.out));
}
{
  const r = run(['repl'], {
    stdin: '/permissions ask\n/permissions\n/permissions allow\n/permissions\n/exit\n' });
  const seen = (r.out.match(/permissions: [^\n]*/g) || []);
  record("the gate: the mode can be set mid-session and reads back as what was set",
         seen.length === 4 && /ask$/.test(seen[0]) && /ask$/.test(seen[1])
           && /allow$/.test(seen[2]) && /allow$/.test(seen[3]),
         seen.join(' | '));
}
{
  const r = run(['repl'], {
    stdin: '/permissions +run_command\n/permissions\n/permissions -run_command\n'
         + '/permissions\n/exit\n' });
  const seen = (r.out.match(/exempt (?:for )?this session: [^\n]*/g) || []);
  // An exemption is added and removed by name and never persisted -- `always` is per-invocation
  // on purpose, because a written-down "always" is a decision made once and applied forever by
  // a file nobody re-reads.
  // Four lines, not three: the `+` and `-` each confirm the change and each `/permissions`
  // reports it back, and the confirmation is worth asserting separately from the report -- a
  // client that echoed the exemption without recording it would print the same first line.
  record("the gate: an exemption is added and taken away by name, leaving nothing behind",
         seen.length === 4 && /run_command$/.test(seen[0]) && /run_command$/.test(seen[1])
           && /nothing$/.test(seen[2]) && /nothing$/.test(seen[3]),
         seen.join(' | '));
}

// ---- @path and continuations ---------------------------------------------------------
// These assert on the client's own report line, which is printed before the turn is attempted,
// so they need no API. That the file was read is the claim; what the model did with it is not.
{
  const r = run(['repl'], { stdin: '@tests/package.json\n' });
  record('@path reads the file and reports the size it is sending',
         /@tests\/package\.json: \d+ chars/.test(r.out),
         (r.out.match(/@tests[^\n]*/) || [''])[0]);
}
{
  const r = run(['repl'], { stdin: '@no/such/file.txt\n' });
  record('a missing @path is reported and sent as written, never silently dropped',
         /@no\/such\/file\.txt: not a file, sent as written/.test(r.out));
}

// ---- the front door -----------------------------------------------------------------
// `symoneural-code` holds no engine: it translates four flags and execs the client. What is
// worth asserting is therefore not that it can hold a session but that it did not grow a
// second copy of the one policy that matters.
{
  const r = run([], { stdin: '', bin: CODE });
  record('`symoneural-code` with no arguments inherits the tty guard rather than re-stating it',
         r.code === 2 && /not a terminal/.test(r.err), `exit ${r.code}`);
}
{
  const r = run(['--session', 'frontdoor-probe'], { stdin: '/exit\n', bin: CODE });
  record('a flag reaches the client, and asking for a session explicitly works from a pipe',
         r.code === 0 && /session\s+frontdoor-probe/.test(r.out), `exit ${r.code}`);
}
{
  const r = run(['repl'], { stdin: '/exit\n', bin: CODE });
  record('`symoneural-code repl` drops the redundant word instead of failing on `repl repl`',
         r.code === 0 && /the word `repl` is redundant/.test(r.err), `exit ${r.code}`);
}
{
  const r = run(['-p'], { stdin: '', bin: CODE });
  record('`symoneural-code -p` with nothing to ask refuses instead of opening a prompt',
         r.code === 2 && /nothing to ask/.test(r.err), `exit ${r.code}`);
}
{
  const r = run(['-r'], { stdin: '', bin: CODE });
  record('`symoneural-code -r` with no id says which flag lists them',
         r.code === 2 && /--sessions/.test(r.err), `exit ${r.code}`);
}

// ---- a real terminal -----------------------------------------------------------------
// The whole point of the guards above is that the behaviour forks on `stdin.isatty()`, so one
// side of that fork has to be exercised through an actual pty or only half of it is tested.
if (spawnSync('script', ['--version'], { encoding: 'utf8' }).status === 0) {
  const r = run([], { stdin: '/exit\n', tty: true });
  record('a bare invocation WITH a terminal on stdin opens the session',
         /SyMoNeuRaL Code/.test(r.out) && /interactive session/.test(r.out), `exit ${r.code}`);
} else {
  skip('a bare invocation WITH a terminal on stdin opens the session',
       'util-linux `script` is not installed, so no pty can be allocated here');
}

// ---- live turns ----------------------------------------------------------------------
if (!BASE) {
  skip('two turns in one session, with the thread continuing and no -c typed',
       'no API url given: node tests/code_cli.mjs http://127.0.0.1:8877');
  skip('the status line reports the session, the thread depth and the permission mode',
       'no API url given');
} else if (!TOKEN) {
  skip('two turns in one session, with the thread continuing and no -c typed',
       'SYMONEURAL_STUDIO_TOKEN is not set, and the agent endpoint requires it');
  skip('the status line reports the session, the thread depth and the permission mode',
       'SYMONEURAL_STUDIO_TOKEN is not set');
} else {
  const session = 'codecli-suite';
  const thread = join(ROOT, 'run', `agent-${session}.json`);
  if (existsSync(thread)) spawnSync(CLI, ['agent', '--session', session, '--forget']);
  const r = run(['repl', '--url', BASE, '--session', session], {
    stdin: 'what is 17 squared?\nand 18 squared?\n/exit\n',
  });
  // Assert the client's contract, not the model's wording. An assertion demanding a literal
  // reply goes red when a temperature, an adapter or a system prompt changes, with nothing on
  // screen to say the session machinery was fine -- the same defect as the ASR test that
  // required the word `country` from a fixture. What this client guarantees is that turn two
  // was sent WITH turn one attached and that both turns produced an answer frame; that the
  // model can square a number is llama-server's claim to make.
  const answers = (r.out.match(/^\s*\d+\.\d\ds answer/gm) || []).length;
  // `history: N messages` goes to stderr, because `cmd_agent` keeps its own commentary off
  // stdout so that `--output-format json` stays machine-readable. A terminal interleaves the
  // two, so this assertion has to read both or it is asserting about a stream split the user
  // never sees. Matching only stdout is what made this go red the first time it was run.
  const seen = r.out + r.err;
  record('two turns in one session, with the thread continuing and no -c typed',
         answers === 2
           && /history: 2 messages from agent-codecli-suite\.json/.test(seen),
         `exit ${r.code}, ${answers} answer frames`);
  // The permission mode joined this line when it was extracted into `status_line`, and this
  // assertion moved with it. It is the one session setting that decides whether a tool runs
  // without anybody being asked, so a line that can be rendered without it is a line that can
  // hide `allow` -- and the assertion asserting the OLD shape would have gone red reading like
  // a regression, which is the trap the gate section one file over documents.
  const shape = (n, msgs) =>
    new RegExp(`\\[${session}\\s+turn ${n}\\s+${msgs} messages\\s+perm (ask|deny|allow)\\]`);
  record('the status line reports the session, the thread depth and the permission mode',
         shape(1, 2).test(r.out) && shape(2, 4).test(r.out),
         (r.out.match(/\[codecli-suite[^\]]*\]/g) || []).join(' '));
}

// ---- tally ---------------------------------------------------------------------------
const bad = results.filter(r => !r.ok).length;
const skipped = results.filter(r => r.skipped).length;
const ran = results.length - skipped;
console.log(`\n${ran - bad}/${ran} passed` + (skipped ? `, ${skipped} skipped` : ''));
process.exit(bad ? 1 : 0);
