# Frontend responsive smoke record

Written by `tests/responsive.mjs` against `http://127.0.0.1:8800`.
Do not hand-edit this file. It is a reading, and a hand-edited reading is worth nothing.

- pages x viewports checked: **192**
- findings: **0**

Every page laid out inside its viewport at every width, every interactive element was inside the viewport and received its own clicks, and no page raised a JavaScript error.

## What was checked

1. `documentElement.scrollWidth` against the viewport width.
2. Every visible element's right edge -- **clipped elements included**, which is the case a
   `scrollWidth` check cannot see and the case that hid the header defect for as long as it did.
3. Every interactive element: inside the viewport horizontally, and returned by
   `elementFromPoint` at its own centre, so a real click there would reach it.
4. Uncaught JavaScript errors on load.

Viewports: 360, 390, 430, 768, 1024, 1440, 1920, 1440x700 (short).
Pages: 24.
