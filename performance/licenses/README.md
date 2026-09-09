# licenses/

Hosted-service dependency and licence ledger.

The question this directory answers is narrow and specific: **may this component
be used for the intended hosted service, and what obligations come with it.**
It is not a general compliance archive and it is not here to protect any
internally-written code.

Belongs here, per component (`PERFORMANCE-POLICY.md` §5):

| field | why it is tracked |
|---|---|
| component | what it is |
| version / commit | obligations differ across versions |
| licence | the actual terms |
| modified / unmodified | changes the obligation under several licences |
| hosted-service considerations | the terms that bind *this* use |
| distribution considerations | separate question, separate answer |
| required action / notices | what we must actually do |

**`modified / unmodified` is the field nobody can reconstruct later.** A patched
engine in `sources/` is indistinguishable from a clean checkout once the reason
for the patch is forgotten, and the distinction is exactly what several licences
turn on. Record it when the patch is made.

**Do not assume server-only use eliminates every obligation.** Serving over a
network is not distribution under most licences — but some carry network-use or
attribution terms regardless, and model weights routinely carry use restrictions
with nothing to do with distribution. The question is never "did we ship a
binary". It is what this licence requires of this use.
