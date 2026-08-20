# tests/fixtures — inputs the browser and HTTP suites feed to a real surface

## `speech.wav` — not here, and that is recorded rather than papered over

Three suites want a few seconds of **real speech** to push through the transcriber:

| caller | what it asserts |
|---|---|
| `tests/stickers.mjs` | an uploaded clip is heard, and a sticker renders from what it said |
| `tests/sigils_http.py` | the `/api/sigils` listen route accepts a clip |
| `backend/apps/voice/test_voice.py` | ASR returns words, cut from the clip rather than committed |

All three used to read `contrib/whisper.cpp/samples/jfk.wav` — a sample that came in as a
side effect of building somebody else's project, and that now sits under `references/`,
which task #74 says nothing may read from. So the path is stale *and* the fixed path would
breach the rule.

**A tone is not a substitute.** The surface transcribes the clip and builds a prompt from
the words; silence transcribes to nothing and the assertion would pass while testing the
empty-prompt path instead of the one it names. That is the fake-green failure `.claude/CLAUDE.md`
forbids, so the callers **skip loudly** when this file is absent and say why. A skip you can
read is honest; a pass you cannot is not.

Set `SYMONEURAL_SPEECH_FIXTURE=/path/to/clip.wav` to point them anywhere else, and
`SYMONEURAL_SPEECH_WORD=<word>` to one word the clip definitely contains — `stickers.mjs`
asserts the transcript against it. That assertion was hardcoded to `country`, because the
old fixture was a JFK speech: swapping the clip would have turned it red with nothing on
screen to say why. With no word set it only asserts that *something* was transcribed, and
the assertion renames itself to say so.

**What is needed:** 5–15 s of clear speech, 16 kHz mono WAV, recorded by us or public
domain — recording it needs a microphone, so it is on Garrett's side of the line. Once it
is here every caller picks it up with no code change.
