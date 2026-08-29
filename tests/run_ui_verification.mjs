#!/usr/bin/env node
// Run the required UI suites in one process-owned sequence.
//
//   node tests/run_ui_verification.mjs [baseURL]
//   node tests/run_ui_verification.mjs --dry-run
//   node tests/run_ui_verification.mjs --suites applications,responsive
//
// This replaces shell pipelines such as `node suite | head`: a pipe can hide a child's
// exit code or close while the suite is still writing.  Each child here gets a complete
// log, one child finishes before the next starts, and an interrupt is forwarded to the
// whole child process group so Chrome is not left behind.
import { spawn, execFileSync } from 'node:child_process';
import { createWriteStream, mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');
const RECORD = join(ROOT, 'docs', 'ops', 'SMOKE-APPLICATIONS.md');
const REQUIRED = ['applications', 'responsive', 'frontend', 'chat'];

const definitions = {
  applications: {
    file: 'applications_smoke.mjs',
    description: 'application workspaces with a self-contained browser fixture',
    args: () => [process.env.UI_APPLICATIONS_PORT || '8993'],
    needsBase: false,
  },
  responsive: {
    file: 'responsive.mjs',
    description: 'all shell pages across the viewport/news matrix',
    args: base => [base],
    needsBase: true,
  },
  frontend: {
    file: 'frontend.mjs',
    description: 'functional frontend and real image path (takes the GPU)',
    args: base => [base],
    needsBase: true,
  },
  chat: {
    file: 'chat_smoke.mjs',
    description: 'real streamed chat at desktop and phone widths (takes the GPU)',
    args: base => [base],
    needsBase: true,
  },
};

const options = {
  base: process.env.UI_BASE_URL || 'http://127.0.0.1:8800',
  suites: [...REQUIRED],
  keepGoing: false,
  dryRun: false,
};

for (let i = 2; i < process.argv.length; i++) {
  const value = process.argv[i];
  if (value === '--keep-going') options.keepGoing = true;
  else if (value === '--dry-run') options.dryRun = true;
  else if (value === '--suites') options.suites = (process.argv[++i] || '').split(',').filter(Boolean);
  else if (value === '--base') options.base = process.argv[++i] || options.base;
  else if (value === '--help' || value === '-h') {
    console.log('usage: node tests/run_ui_verification.mjs [baseURL] [--keep-going]');
    console.log('       node tests/run_ui_verification.mjs --suites applications,responsive');
    console.log('       node tests/run_ui_verification.mjs --dry-run');
    process.exit(0);
  } else if (!value.startsWith('-')) options.base = value;
  else throw new Error(`unknown option: ${value}`);
}

for (const name of options.suites) {
  if (!definitions[name]) throw new Error(`unknown suite ${name}; choose from ${Object.keys(definitions).join(', ')}`);
}

const canonical = options.suites.join(',') === REQUIRED.join(',');
const timeoutMs = Number(process.env.UI_SUITE_TIMEOUT_MS || 20 * 60 * 1000);
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const logDir = resolve(process.env.UI_LOG_DIR || join(ROOT, 'run', 'ui-verification', stamp));

if (options.dryRun) {
  console.log(`base: ${options.base}`);
  for (const name of options.suites) {
    const suite = definitions[name];
    console.log(`${name}: ${process.execPath} ${join(HERE, suite.file)} ${suite.args(options.base).join(' ')}`);
  }
  process.exit(0);
}

if (options.suites.some(name => definitions[name].needsBase)) {
  try {
    const status = new URL('/api/status', options.base);
    const response = await fetch(status, { signal: AbortSignal.timeout(7000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  } catch (error) {
    console.error(`UI preflight failed: ${options.base}/api/status is not ready (${error.message}).`);
    console.error('Start the intended API/harness or pass its base URL; no browser suite was launched.');
    process.exit(2);
  }
}

mkdirSync(logDir, { recursive: true });

let activeChild = null;
let interruptedSignal = '';

const terminate = signal => {
  if (!activeChild || activeChild.exitCode !== null) return;
  try {
    if (process.platform !== 'win32') process.kill(-activeChild.pid, signal);
    else activeChild.kill(signal);
  } catch {
    activeChild.kill(signal);
  }
};

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => {
    if (interruptedSignal) return;
    interruptedSignal = signal;
    console.error(`\n${signal}: stopping the active suite before exiting.`);
    terminate(signal);
    setTimeout(() => terminate('SIGKILL'), 3000).unref();
  });
}

const runSuite = (name, suite) => new Promise(resolveSuite => {
  const started = Date.now();
  const logPath = join(logDir, `${name}.log`);
  const log = createWriteStream(logPath, { flags: 'w' });
  const argv = [join(HERE, suite.file), ...suite.args(options.base)];
  let tail = '';
  let settled = false;
  let timedOut = false;

  console.log(`RUN   ${name.padEnd(13)} ${suite.description}`);
  const child = spawn(process.execPath, argv, {
    cwd: ROOT,
    env: process.env,
    detached: process.platform !== 'win32',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  activeChild = child;

  const keep = chunk => {
    log.write(chunk);
    tail = (tail + chunk.toString()).slice(-16000);
  };
  child.stdout.on('data', keep);
  child.stderr.on('data', keep);

  const timer = timeoutMs > 0 ? setTimeout(() => {
    timedOut = true;
    log.write(`\nrunner: timed out after ${timeoutMs} ms\n`);
    terminate('SIGTERM');
    setTimeout(() => terminate('SIGKILL'), 3000).unref();
  }, timeoutMs) : null;

  const finish = (code, signal, error = null) => {
    if (settled) return;
    settled = true;
    if (timer) clearTimeout(timer);
    activeChild = null;
    if (error) log.write(`\nrunner spawn error: ${error.message}\n`);
    log.end(() => resolveSuite({
      name,
      ok: !timedOut && !error && code === 0,
      code: timedOut ? 124 : (error ? 127 : code),
      signal: signal || '',
      timedOut,
      durationMs: Date.now() - started,
      logPath,
      tail,
    }));
  };
  child.once('error', error => finish(null, '', error));
  child.once('close', (code, signal) => finish(code, signal));
});

const results = [];
for (const name of options.suites) {
  if (interruptedSignal) break;
  // Deliberately awaited inside the loop: there is never more than one browser suite or
  // GPU claimant alive. Do not replace this with Promise.all.
  const result = await runSuite(name, definitions[name]);
  results.push(result);
  console.log(`${result.ok ? 'PASS' : 'FAIL'}  ${name.padEnd(13)} ${(result.durationMs / 1000).toFixed(1)}s  ${relative(ROOT, result.logPath)}`);
  if (!result.ok) {
    console.error(`\nLast output from ${name}:\n${result.tail.trim() || '(no output)'}`);
    if (!options.keepGoing) break;
  }
}

const allPassed = !interruptedSignal && results.length === options.suites.length && results.every(r => r.ok);
const canonicalPassed = canonical && allPassed;

console.log('\nUI verification summary');
for (const result of results) {
  const detail = result.timedOut ? 'timeout' : result.signal ? result.signal : `exit ${result.code}`;
  console.log(`  ${result.ok ? 'PASS' : 'FAIL'}  ${result.name.padEnd(13)} ${(result.durationMs / 1000).toFixed(1)}s  ${detail}`);
}
for (const name of options.suites.slice(results.length)) console.log(`  SKIP  ${name}`);
console.log(`  logs: ${logDir}`);

if (canonical) {
  let revision = 'unknown';
  let dirty = '';
  try {
    revision = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: ROOT, encoding: 'utf8' }).trim();
    dirty = execFileSync('git', ['status', '--porcelain', '--untracked-files=no'],
                         { cwd: ROOT, encoding: 'utf8' }).trim() ? ' (tracked working tree dirty)' : '';
  } catch { /* the runner remains usable outside Git */ }
  const lines = [
    '# Application UI smoke record',
    '',
    'Generated by `tests/run_ui_verification.mjs`; do not hand-edit this reading.',
    '',
    `- base URL: \`${options.base}\``,
    `- revision: \`${revision}\`${dirty}`,
    `- completed: ${new Date().toISOString()}`,
    `- result: **${canonicalPassed ? 'ALL REQUIRED UI SUITES PASSED' : interruptedSignal ? `INTERRUPTED (${interruptedSignal})` : 'FAILED OR INCOMPLETE'}**`,
    `- full logs: \`${relative(ROOT, logDir)}\``,
    '',
    '| suite | result | seconds | exit |',
    '|---|---:|---:|---:|',
  ];
  for (const result of results) {
    lines.push(`| \`${result.name}\` | ${result.ok ? 'PASS' : 'FAIL'} | ${(result.durationMs / 1000).toFixed(1)} | ${result.timedOut ? 'timeout' : result.signal || result.code} |`);
  }
  for (const name of options.suites.slice(results.length)) lines.push(`| \`${name}\` | SKIPPED | — | — |`);
  lines.push('');
  writeFileSync(RECORD, lines.join('\n'), 'utf8');
  console.log(`  record: ${relative(ROOT, RECORD)}`);
}

if (interruptedSignal) process.exit(interruptedSignal === 'SIGINT' ? 130 : 143);
process.exit(allPassed ? 0 : 1);
