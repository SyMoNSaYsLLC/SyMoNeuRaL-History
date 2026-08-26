# Frontend responsive smoke record

Written by `tests/responsive.mjs` against `http://127.0.0.1:8800`.
Do not hand-edit this file. It is a reading, and a hand-edited reading is worth nothing.

- pages x viewports checked: **192**
- findings: **78**
  - OVERFLOW: 47
  - UNREACHABLE: 31

This run found defects. They are listed below and #109 stays red until they are gone.

| viewport | page | kind | detail |
|---|---|---|---|
| 360 | `/chat.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/chat.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/image.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/image.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/ravencalc.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/ravencalc.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/remix.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/remix.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/miner.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/miner.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/gateway.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/gateway.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/streamer.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/streamer.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/studio.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/studio.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/exp.html` | OVERFLOW | scrollWidth 360 vs 360; 35 element(s) past the right edge: nav@405, a.cta@405, table.ex-tbl@432, thead@432, tr@432, th@432, tbody#ex-catalogue@432, tr@432, td@432, code.ex-mono@417, tr@432, td@432, code.ex-mono@417, tr@432, td@432, code.ex-mono@417, tr@432, td@432, br@399, code.ex-mono@404, tr@432, td@432, br@374, code.ex-mono@411, tr@432 |
| 360 | `/exp.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/project.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/project.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/reinforce.html` | OVERFLOW | scrollWidth 360 vs 360; 51 element(s) past the right edge: nav@405, a.cta@405, table#rf-models.rf-tab@668, thead@668, tr@668, th@421, th@531, th@668, tbody@668, tr@668, td@668, table#rf-methods.rf-tab@668, thead@668, tr@668, th@449, th@535, th@668, tbody@668, tr@668, td@668, table#rf-presets.rf-tab@788, thead@788, tr@788, th@430, th@527 |
| 360 | `/reinforce.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/sigils.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/sigils.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/coder.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/coder.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/live.html` | OVERFLOW | scrollWidth 360 vs 360; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 360 | `/live.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..360) |
| 360 | `/credits.html` | OVERFLOW | scrollWidth 360 vs 360; 70 element(s) past the right edge: table@563, caption@563, thead@563, tr@563, th@404, th@563, tbody@563, tr@563, td.num@404, span.badge@370, td@563, tr@563, td.num@404, span.badge@370, td@563, tr@563, td.num@404, span.badge@370, td@563, tr@563, td.num@404, span.badge@370, td@563, code@477, tr@563 |
| 360 | `/credits.html` | UNREACHABLE | 1: a (x 410..459 outside 0..360) |
| 360 | `/documentation.html` | OVERFLOW | scrollWidth 360 vs 360; 112 element(s) past the right edge: table@750, caption@750, thead@750, tr@750, th@437, th@552, th@750, tbody@750, tr@750, td.num@437, b@419, td.num@552, b@495, td@750, tr@750, td.num@437, td.num@552, em@494, td.num@750, tr@750, td.num@437, td.num@552, em@502, td.num@750, tr@750 |
| 360 | `/training.html` | OVERFLOW | scrollWidth 360 vs 360; 547 element(s) past the right edge: code@389, code@650, table@409, thead@409, tr@409, th@409, tbody@409, tr@409, td@409, tr@409, td@409, tr@409, td@409, code@397, tr@409, td@409, table@390, thead@390, tr@390, th@390, tbody@390, tr@390, td@390, tr@390, td@390 |
| 390 | `/chat.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/chat.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/image.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/image.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/ravencalc.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/ravencalc.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/remix.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/remix.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/miner.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/miner.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/gateway.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/gateway.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/streamer.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/streamer.html` | UNREACHABLE | 3: a.cta (x 336..405 outside 0..390), button#tnvguide.tn-vtab (covered by button#tnfgpill.tn-fgpill), button#tnvlist.tn-vtab (covered by button#tnfgpill.tn-fgpill) |
| 390 | `/studio.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/studio.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/exp.html` | OVERFLOW | scrollWidth 390 vs 390; 33 element(s) past the right edge: nav@405, a.cta@405, table.ex-tbl@432, thead@432, tr@432, th@432, tbody#ex-catalogue@432, tr@432, td@432, code.ex-mono@417, tr@432, td@432, code.ex-mono@417, tr@432, td@432, code.ex-mono@417, tr@432, td@432, br@399, code.ex-mono@404, tr@432, td@432, code.ex-mono@411, tr@432, td@432 |
| 390 | `/exp.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/project.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/project.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/reinforce.html` | OVERFLOW | scrollWidth 390 vs 390; 50 element(s) past the right edge: nav@405, a.cta@405, table#rf-models.rf-tab@668, thead@668, tr@668, th@421, th@531, th@668, tbody@668, tr@668, td@668, table#rf-methods.rf-tab@668, thead@668, tr@668, th@449, th@535, th@668, tbody@668, tr@668, td@668, table#rf-presets.rf-tab@788, thead@788, tr@788, th@430, th@527 |
| 390 | `/reinforce.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/sigils.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/sigils.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/coder.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/coder.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/live.html` | OVERFLOW | scrollWidth 390 vs 390; 2 element(s) past the right edge: nav@405, a.cta@405 |
| 390 | `/live.html` | UNREACHABLE | 1: a.cta (x 336..405 outside 0..390) |
| 390 | `/credits.html` | OVERFLOW | scrollWidth 390 vs 390; 43 element(s) past the right edge: table@563, caption@563, thead@563, tr@563, th@404, th@563, tbody@563, tr@563, td.num@404, td@563, tr@563, td.num@404, td@563, tr@563, td.num@404, td@563, tr@563, td.num@404, td@563, code@477, tr@563, td.num@404, td@563, tr@563, td.num@404 |
| 390 | `/credits.html` | UNREACHABLE | 1: a (x 410..459 outside 0..390) |
| 390 | `/documentation.html` | OVERFLOW | scrollWidth 390 vs 390; 105 element(s) past the right edge: table@750, caption@750, thead@750, tr@750, th@437, th@552, th@750, tbody@750, tr@750, td.num@437, b@419, td.num@552, b@495, td@750, tr@750, td.num@437, td.num@552, em@494, td.num@750, tr@750, td.num@437, td.num@552, em@502, td.num@750, tr@750 |
| 390 | `/training.html` | OVERFLOW | scrollWidth 390 vs 390; 505 element(s) past the right edge: code@650, table@409, thead@409, tr@409, th@409, tbody@409, tr@409, td@409, tr@409, td@409, tr@409, td@409, code@397, tr@409, td@409, code@634, code.language-bash@496, code@627, code.language-bash@764, table@554, thead@554, tr@554, th@402, th@554, tbody@554 |
| 430 | `/exp.html` | OVERFLOW | scrollWidth 430 vs 430; 21 element(s) past the right edge: table.ex-tbl@432, thead@432, tr@432, th@432, tbody#ex-catalogue@432, tr@432, td@432, tr@432, td@432, tr@432, td@432, tr@432, td@432, tr@432, td@432, tr@432, td@432, tr@432, td@432, tr@432, td@432 |
| 430 | `/reinforce.html` | OVERFLOW | scrollWidth 430 vs 430; 46 element(s) past the right edge: table#rf-models.rf-tab@668, thead@668, tr@668, th@531, th@668, tbody@668, tr@668, td@668, table#rf-methods.rf-tab@668, thead@668, tr@668, th@449, th@535, th@668, tbody@668, tr@668, td@668, table#rf-presets.rf-tab@788, thead@788, tr@788, th@527, th@623, th@715, th@788, tbody@788 |
| 430 | `/credits.html` | OVERFLOW | scrollWidth 430 vs 430; 32 element(s) past the right edge: table@563, caption@563, thead@563, tr@563, th@563, tbody@563, tr@563, td@563, tr@563, td@563, tr@563, td@563, tr@563, td@563, code@477, tr@563, td@563, tr@563, td@563, tr@563, td@563, tr@563, td@563, table@503, caption@503 |
| 430 | `/credits.html` | UNREACHABLE | 1: a (x 410..459 outside 0..430) |
| 430 | `/documentation.html` | OVERFLOW | scrollWidth 430 vs 430; 104 element(s) past the right edge: table@750, caption@750, thead@750, tr@750, th@437, th@552, th@750, tbody@750, tr@750, td.num@437, td.num@552, b@495, td@750, tr@750, td.num@437, td.num@552, em@494, td.num@750, tr@750, td.num@437, td.num@552, em@502, td.num@750, tr@750, td.num@437 |
| 430 | `/training.html` | OVERFLOW | scrollWidth 430 vs 430; 363 element(s) past the right edge: code@650, code@634, code.language-bash@496, code@627, code.language-bash@764, table@554, thead@554, tr@554, th@554, tbody@554, tr@554, td@554, strong@500, code@529, tr@554, td@554, code@517, code@450, code@532, code@457, code@513, code@490, tr@554, td@554, code@529 |
| 768 | `/reinforce.html` | OVERFLOW | scrollWidth 768 vs 768; 7 element(s) past the right edge: table#rf-presets.rf-tab@788, thead@788, tr@788, th@788, tbody@788, tr@788, td@788 |
| 768 | `/documentation.html` | OVERFLOW | scrollWidth 768 vs 768; 32 element(s) past the right edge: table@1072, caption@1072, thead@1072, tr@1072, th@830, th@932, th@1072, tbody@1072, tr@1072, td.num@830, td.num@932, td.num@1072, tr@1072, td.num@830, td.num@932, td.num@1072, tr@1072, td.num@830, td.num@932, td.num@1072, tr@1072, td.num@830, td.num@932, td.num@1072, tr@1072 |
| 768 | `/training.html` | OVERFLOW | scrollWidth 768 vs 768; 16 element(s) past the right edge: code.language-bash@872, code.language-bash@787, code.language-python@787, code.language-bash@780, code.language-jsonl@1369, code.language-python@787, code.language-jsonl@780, code@780, code.language-ini@1002, code@872, code@849, code.language-text@849, code.language-text@849, code.language-text@1109, code.language-text@879, code.language-t |
| 1024 | `/documentation.html` | OVERFLOW | scrollWidth 1024 vs 1024; 18 element(s) past the right edge: table@1072, caption@1072, thead@1072, tr@1072, th@1072, tbody@1072, tr@1072, td.num@1072, tr@1072, td.num@1072, tr@1072, td.num@1072, tr@1072, td.num@1072, tr@1072, td.num@1072, tr@1072, td.num@1072 |
| 1024 | `/training.html` | OVERFLOW | scrollWidth 1024 vs 1024; 37 element(s) past the right edge: code.language-bash@1117, code.language-bash@1224, code.language-bash@1041, code.language-bash@1140, code.language-python@1140, code.language-python@1094, code@1041, code.language-bash@1087, code.language-bash@1133, code.language-jsonl@1722, code.language-python@1140, code.language-python@1110, code.language-bash@1048, code.language-jsonl |
| 1440 | `/training.html` | OVERFLOW | scrollWidth 1440 vs 1440; 3 element(s) past the right edge: code.language-jsonl@1802, code.language-text@1542, code.language-text@6236 |
| 1920 | `/training.html` | OVERFLOW | scrollWidth 1920 vs 1920; 1 element(s) past the right edge: code.language-text@6248 |
| 1440x700 (short) | `/training.html` | OVERFLOW | scrollWidth 1440 vs 1440; 3 element(s) past the right edge: code.language-jsonl@1802, code.language-text@1542, code.language-text@6236 |

## What was checked

1. `documentElement.scrollWidth` against the viewport width.
2. Every visible element's right edge -- **clipped elements included**, which is the case a
   `scrollWidth` check cannot see and the case that hid the header defect for as long as it did.
3. Every interactive element: inside the viewport horizontally, and returned by
   `elementFromPoint` at its own centre, so a real click there would reach it.
4. Uncaught JavaScript errors on load.

Viewports: 360, 390, 430, 768, 1024, 1440, 1920, 1440x700 (short).
Pages: 24.
