# Smoke readings — the ASR runtime, driven by actually transcribing

`backend/apps/voice/test_voice.py` and `apps/sigils` are structural until a weight is on disk:
for weeks every ASR assertion in them **skipped**, and a suite of skips is not a suite of
passes. This file is the other half. **Every reading below came from running the engine on
real audio**, not from reading a path or a manifest.

**Measured 2026-09-04**, on `af2d907d` plus the working tree that became the commit this file
arrives in. The engine did not exist before `4b91a754` and the weight was not on disk before
this session, so there is nothing here carried forward from an earlier tree — which is the
usual way a figure in this repo goes wrong.

## What was run

```
engines/symoneural-listen/build/bin/symoneural-listen \
  -m backend/models/whisper/symoneural-listen-base-en.bin \
  -f engines/symoneural-listen/samples/jfk.wav -t 8 -nt
```

Transcript returned, in full and correct:

> And so my fellow Americans, ask not what your country can do for you, ask what you can do
> for your country.

That sentence is the reading that matters. A timing proves the process ran; **only the words
prove it heard**, and the empty-string case is exactly the fake-green that
`tests/fixtures/README.md` refuses to paper over with a tone.

## Timings, `base.en` at `-t 8`

| Stage | Measured |
|---|---|
| load | 217.67 ms |
| mel | 16.86 ms |
| encode | 372.93 ms / 1 run |
| batchd | 193.53 ms / 125 runs (1.55 ms per run) |
| sample | 41.56 ms / 129 runs (0.32 ms per run) |
| **total** | **884.67 ms** |

## The CPU-only claim, proved structurally rather than by watching a number

The design requires this engine never to take the GPU lock (see `tools/fork_engines.sh`
`fork_listen`, and the argument in `scripts/fetch-whisper.sh` that it inherits). Two readings,
and the first is the one to trust:

- **`ldd` reports zero CUDA, cuBLAS or NVIDIA libraries linked.** A binary that links no CUDA
  cannot allocate VRAM, which settles it independently of any measurement.
- `GGML_CUDA:BOOL=OFF` in `engines/symoneural-listen/build/CMakeCache.txt`, read directly.

A VRAM delta of **14 MiB** was observed across a transcription while the chat model was
resident at ~9.3 GiB. That is **not** reported as the engine's usage: it is desktop noise on a
shared card, and quoting it as "the ASR uses 14 MiB" would be inventing a measurement the
method cannot support. The linkage above is the claim; this paragraph exists so the next
reader does not repeat the observation and draw the wrong conclusion from it.

The four libraries it does load are all ours, all resolved out of its own directory, which is
what `RUNPATH: [$ORIGIN]` is for: `libsymoneural_listen_core.so.1`, `libsymoneural_tensor.so.0`,
`libsymoneural_tensor_base.so.0`, `libsymoneural_tensor_cpu.so.0`.

## The weight

| | |
|---|---|
| house name | `backend/models/whisper/symoneural-listen-base-en.bin` |
| bytes | 147,964,211 |
| sha256 | `a03779c86df3323075f5e796cb2ce5029f00ec8869eee3fdfb897afe36c6d002` |
| upstream | `ggerganov/whisper.cpp` · `ggml-base.en.bin` · MIT |

The sha256 is **our measurement of what we fetched**, not a digest upstream publishes — the
vendored tree carries no checksum list to check against. What corroborates it is that
`PROVENANCE.json` already recorded `bytes_on_disk` 147964211 from when this file was last on
disk, and the download matched that **exactly**.

## The suite, before and after

`apps/voice` went from **11 skipped** to **33 passed, 0 skipped**, run with the documented
`SYMONEURAL_SPEECH_FIXTURE` pointing at the engine's own public-domain sample.

The skip reason moved twice on the way, and the sequence is the evidence each step landed:

1. *"whisper weights missing …"* **and** the binary absent — before any of this work.
2. *"whisper weights missing at …"* only — after `4b91a754` built the engine and repointed
   both call sites. The binary had stopped being the problem.
3. *"no sample audio at tests/fixtures/speech.wav"* — after the weight arrived. The runtime
   was done; what remained was a test input.

## What this file does NOT claim

- **`tests/fixtures/speech.wav` is still absent.** Those 11 tests pass here only because the
  fixture was pointed at the engine's sample by environment variable. `tests/fixtures/README.md`
  asks for 5–15 s of our own or public-domain speech and puts recording it on Garrett's side,
  and that is unchanged.
- **The `voice` surface is not enabled.** It needs `SYMONEURAL_VOICE_ENABLED=1` (the literal
  `1`) and `SYMONEURAL_VOICE_TOKEN`, both in root-owned config, and `/api/*` is public — so
  enabling it without the token spends this box's CPU for strangers. No `voice` unit appears in
  `GET /api/status` today and this file does not say one does.
