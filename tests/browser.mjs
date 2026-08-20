// The one place any suite gets a browser from.
//
//   import { chromium } from './browser.mjs';        // from tests/
//   import { chromium } from '<rel>/tests/browser.mjs';
//
// **There used to be nine copies of this resolution and every one of them was broken.** They
// all pointed at `contrib/llama.cpp/tools/ui/node_modules/playwright` -- Playwright as it
// happened to be installed as a side effect of building somebody else's web UI. That path
// moved under `references/` in the restructure, so all eight browser suites stopped starting;
// and the fixed path would have been worse than the broken one, because task #74's acceptance
// test is that nothing under `references/` is imported, built or linked. Nine hand-edited
// relative paths is also how you get nine chances to be wrong again, so there is now one.
//
// Playwright is a **devDependency and never ships**: no serving path imports it, no page
// links it, `deploy.sh` copies nothing from here. That is the whole reason it is used as-is
// rather than recreated -- the recreate-by-default rule is about what we hand a user, and a
// browser-automation harness is not that. Pinned at 1.56.1 in `tests/package.json` because
// that is the version every published browser figure was measured against; see
// `backend/DEPENDENCIES.md` for the argument written out.
//
// Install with `npm install` in `tests/`. Browsers are NOT downloaded and must not be: every
// suite launches `channel: 'chrome'`, the system Chrome, which is what makes the readings
// about the browser real visitors use.
import { createRequire } from 'node:module';

let playwright;
try {
  playwright = createRequire(import.meta.url)('playwright');
} catch (e) {
  // Say the fix, not the stack. A bare MODULE_NOT_FOUND here reads as a suite bug and has
  // sent somebody hunting one.
  console.error('Playwright is not installed. Run:\n\n    cd tests && npm install\n');
  console.error(`(resolution failed: ${e.message})`);
  process.exit(2);
}

export const { chromium, firefox, webkit, devices } = playwright;
export default playwright;
