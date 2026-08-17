"""SyMoNeuRaL Reinforce -- regression tests. Stdlib `unittest`, no dependencies.

    python3 -m unittest discover -s backend/apps -p 'test_reinforce.py' -v

`.claude/CLAUDE.md`'s framing, taken from the Reinforce engine's own suite: a constraint found
by audit is only a constraint once a test guards it. Every check here was verified to FAIL
when the thing it tests is reverted -- the four that matter most:

* remove the resident-bf16 term from the arithmetic and `test_resident_bf16_is_not_forgotten`
  and `test_7b_derivation_matches_the_safetensors_index` both fail;
* change `parse_log` to pass unmatched lines through and `test_log_parser_drops_unknown_lines`
  fails on the sentinel;
* drop the `is_denied` check from `admit()` and `test_corpus_is_refused_*` fail;
* change `build_script` to `acquire`/`release` and `test_launch_uses_the_with_form` fails.

Nothing here starts a real fine-tune, and nothing here reads `training/corpus.jsonl`. The
launch path is exercised separately and deliberately, by hand, with the step-capped Smoke
preset against a synthetic dataset:

    mkdir -p run/reinforce/datasets   # then write a few dummy {"messages": [...]} rows
    SYM_REINFORCE_ENABLED=1 SYM_REINFORCE_TOKEN=x python3 -c "\\
      import sys; sys.path.insert(0, 'backend/apps'); from reinforce import jobs; \\
      print(jobs.start('Qwen/Qwen2.5-7B-Instruct', 'smoke', \\
                       'run/reinforce/datasets/pipeline-smoke.jsonl'))"

A synthetic dataset rather than the real one on purpose: if the launch path had only ever been
exercised against the corpus, the guard that refuses the corpus would never have been tested
against a real launch.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from reinforce import dataset_guard, jobs, presets, registry  # noqa: E402

GIB = registry.GIB
SEVEN_B = "Qwen/Qwen2.5-7B-Instruct"


def _imported_modules(path: pathlib.Path) -> set[str]:
    """Every module name a file imports, from its AST.

    Source-text assertions about imports are unreliable in this package specifically, because
    these modules explain at length *why* they do not import torch. Ask the parser.
    """
    import ast
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
    return found


def _dict_keys_and_kwargs(path: pathlib.Path) -> set[str]:
    """Every literal dict key and keyword-argument name in a file, from its AST.

    Used to assert on what is actually *passed* to the trainer, rather than on what the
    surrounding comments say about it."""
    import ast
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Dict):
            names.update(k.value for k in node.keys
                         if isinstance(k, ast.Constant) and isinstance(k.value, str))
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                and isinstance(node.slice.value, str):
            names.add(node.slice.value)
    return names


class ArithmeticTests(unittest.TestCase):
    """The VRAM model. Arithmetic is only trustworthy where it lands on something real."""

    def test_7b_derivation_matches_the_safetensors_index(self):
        """The parameter count derived from config.json must equal the index's total_size / 2.

        This is the check that makes every other projection believable: if the split between
        quantised and bf16-resident parameters were wrong, the total would not land on the
        file. bf16 is two bytes per parameter, so total_size / 2 is the parameter count, and
        the two numbers must agree exactly -- not approximately.
        """
        entry = registry.find(SEVEN_B)
        if entry is None or not entry.present:
            self.skipTest("the 7B is not in the local weight cache")
        snap = registry.ROOT / entry.path
        index = snap / "model.safetensors.index.json"
        if not index.is_file():
            self.skipTest("no safetensors index in the snapshot")
        total_size = json.loads(index.read_text())["metadata"]["total_size"]
        arch = registry.Arch(**entry.arch)
        self.assertEqual(arch.total_params, total_size // 2)

    def test_resident_bf16_is_not_forgotten(self):
        """Embeddings and lm_head stay at bf16 and are over a gibibyte on a 152k vocabulary.

        This is the term a naive `params x 0.5 bytes` estimate throws away, and throwing it
        away is the most common reason a 'this fits' estimate OOMs at step 0.
        """
        entry = registry.find(SEVEN_B)
        if entry is None:
            self.skipTest("the 7B is not in the local weight cache")
        arch = registry.Arch(**entry.arch)
        self.assertGreater(arch.resident_bf16_params * 2, 2 * GIB)
        self.assertFalse(arch.tied_embeddings, "the 7B config states tie_word_embeddings false")

    def test_lora_params_match_the_adapter_on_disk(self):
        """r=16 over the seven modules must be the 40,370,176 the shipped adapter contains.

        Corroborated independently: `adapter_model.safetensors` is 161,533,192 bytes, which is
        40,370,176 fp32 parameters plus a 52 KB safetensors header. This asserts the shape of
        the adapter, never its contents -- the weights are output, and the corpus that produced
        them is never read by this suite.
        """
        entry = registry.find(SEVEN_B)
        if entry is None:
            self.skipTest("the 7B is not in the local weight cache")
        arch = registry.Arch(**entry.arch)
        self.assertEqual(arch.lora_params(16, presets.ALL_SEVEN), 40_370_176)
        # Attention-only is genuinely cheaper, not nominally so -- which is what makes Smoke's
        # q,v target list a real speed choice rather than a cosmetic one.
        self.assertLess(arch.lora_params(8, presets.ATTENTION_ONLY),
                        arch.lora_params(8, presets.ALL_SEVEN) // 4)

    def test_logits_dominate_the_activation_term(self):
        """On a 152k-vocabulary model the logit tensor is the largest activation.

        This is why `max_length` moves the projected peak more than layer count does, and it
        is the justification for Long-form being the preset nearest the ceiling. If this ever
        stops being true the presets' sequence-length reasoning needs revisiting.
        """
        entry = registry.find(SEVEN_B)
        if entry is None:
            self.skipTest("the 7B is not in the local weight cache")
        arch = registry.Arch(**entry.arch)
        acts = registry.activation_bytes(arch, seq_len=1024, batch=1, checkpointing=True)
        self.assertGreater(acts["logits"], acts["hidden_states"])
        self.assertGreater(acts["logits"], acts["recompute_peak"])
        self.assertEqual(acts["label"], "projected")

    def test_doubling_sequence_doubles_activations(self):
        entry = registry.find(SEVEN_B)
        if entry is None:
            self.skipTest("the 7B is not in the local weight cache")
        arch = registry.Arch(**entry.arch)
        a1 = registry.activation_bytes(arch, 1024, 1)["total"]
        a2 = registry.activation_bytes(arch, 2048, 1)["total"]
        self.assertAlmostEqual(a2 / a1, 2.0, places=6)


class VerdictTests(unittest.TestCase):
    """`headroom > 0` is the wrong test, and this is where that is enforced."""

    def _arch(self, model_id):
        entry = registry.find(model_id)
        if entry is None or entry.arch is None:
            self.skipTest(f"{model_id} not available on this box")
        return registry.Arch(**entry.arch)

    def test_7b_voice_fits_with_margin(self):
        arch = self._arch(SEVEN_B)
        p = presets.PRESETS["voice"]
        plan = registry.plan_fit(arch, rank=p.rank, target_modules=p.target_modules,
                                 seq_len=p.max_length, batch=1)
        self.assertEqual(plan["verdict"], "fits")
        self.assertEqual(plan["label"], "projected")
        self.assertEqual(plan["ladder"], [], "a fitting configuration offers no OOM ladder")

    def test_14b_is_refused_at_every_preset(self):
        """A 14B is NOT trainable on this card, at any preset. This reverses an earlier
        projection and the reversal is the point.

        The upgrade spec projected the 14B as "feasible at rank <=16, batch 1, sequence <=1024".
        That projection charged two bytes for each resident parameter. peft upcasts them to
        fp32, and the 14B has an untied lm_head, so its embeddings and output head alone are
        1.56B parameters -- 5.80 GiB rather than 2.90 GiB. The weights exceed the budget before
        a single activation exists. Measured on the 7B, applied to the 14B by arithmetic.
        """
        arch = self._arch("Qwen/Qwen2.5-14B-Instruct")
        for pid, p in presets.PRESETS.items():
            with self.subTest(preset=pid):
                plan = registry.plan_fit(arch, rank=p.rank, target_modules=p.target_modules,
                                         seq_len=p.max_length, batch=1)
                self.assertEqual(plan["verdict"], "refused")
                self.assertTrue(plan["ladder"])
                self.assertIn("smaller base model", plan["ladder"][-1])

    def test_a_refusal_shows_its_working(self):
        arch = self._arch("Qwen/Qwen2.5-14B-Instruct")
        p = presets.PRESETS["longform"]
        plan = registry.plan_fit(arch, rank=p.rank, target_modules=p.target_modules,
                                 seq_len=p.max_length, batch=1)
        self.assertEqual(plan["verdict"], "refused")
        self.assertFalse(plan["fits"])
        self.assertTrue(plan["ladder"], "a refusal must name a rung of the OOM ladder")
        self.assertIn("shorten max_length", plan["ladder"][0])
        # The sum has to come back with the refusal, or it is indistinguishable from a bug.
        self.assertEqual(len(plan["terms"]), 6)
        for term in plan["terms"].values():
            self.assertIn(term["label"], ("measured", "vendor", "projected"))
            self.assertTrue(term["basis"])

    def test_a_sub_gibibyte_margin_is_refused_not_called_a_fit(self):
        """`headroom > 0` is the wrong test, and this is the check that says so directly.

        The projection has unmodelled terms -- cuBLAS workspace growth, fragmentation, the
        dataloader, and an activation estimate that is arithmetic rather than a reading. Its own
        error bar is wider than a gibibyte; the one run that exists came in 7% over its content
        projection. So a configuration projected to fit by half a gibibyte is not a fit, it is a
        run whose OOM is inside the noise. Free VRAM is passed explicitly here to put the
        headroom in the band under test rather than relying on whatever this box has spare.
        """
        arch = self._arch(SEVEN_B)
        p = presets.PRESETS["voice"]
        base = registry.plan_fit(arch, rank=p.rank, target_modules=p.target_modules,
                                 seq_len=p.max_length, batch=1)
        peak = base["projected_peak_bytes"]
        for margin, expected in ((int(0.5 * GIB), "refused"),
                                 (int(1.5 * GIB), "tight"),
                                 (int(3.0 * GIB), "fits")):
            with self.subTest(margin_gib=margin / GIB):
                plan = registry.plan_fit(arch, rank=p.rank, target_modules=p.target_modules,
                                         seq_len=p.max_length, batch=1,
                                         free_bytes=peak + margin)
                self.assertEqual(plan["verdict"], expected)

    def test_resident_term_is_fp32_not_bf16(self):
        """The constant that cost 2.03 GiB. peft/utils/other.py:197-202 casts every
        non-quantised parameter to fp32 before training, so the resident term is 4 bytes per
        parameter and not 2. Reverting it makes the projection under-report a real run."""
        self.assertEqual(registry.RESIDENT_BYTES_PER_PARAM, 4)
        arch = self._arch(SEVEN_B)
        plan = registry.plan_fit(arch, rank=8, target_modules=presets.ATTENTION_ONLY,
                                 seq_len=512, batch=1)
        self.assertGreater(plan["terms"]["weights_resident_fp32"]["bytes"], 4 * GIB)
        self.assertIn("peft/utils/other.py", plan["terms"]["weights_resident_fp32"]["basis"])

    def test_the_projection_is_conservative_against_the_one_measurement(self):
        """The only run that exists reserved 9.46 GiB. The projected peak for that exact cell
        must sit ABOVE it -- under-projecting is what OOMs at step 0, and over-projecting only
        refuses a run that might have fit."""
        arch = self._arch(SEVEN_B)
        p = presets.PRESETS["smoke"]
        plan = registry.plan_fit(arch, rank=p.rank, target_modules=p.target_modules,
                                 seq_len=p.max_length, batch=1)
        self.assertGreater(plan["projected_peak_bytes"],
                           registry.ACCURACY["measured_reserved_bytes"])

    def test_accuracy_is_published_with_the_projection(self):
        """Publishing a projection without publishing how far off it was the one time it could
        be checked is the same class of dishonesty as an unlabelled figure."""
        arch = self._arch(SEVEN_B)
        plan = registry.plan_fit(arch, rank=16, target_modules=presets.ALL_SEVEN,
                                 seq_len=1024, batch=1)
        acc = plan["accuracy"]
        self.assertEqual(acc["label"], "measured")
        self.assertEqual(acc["runs_measured"], 1)
        self.assertIn("under", acc["content_term_error"])

    def test_budget_is_practical_not_nameplate(self):
        """Budgeting against 15.92 GiB is how a run OOMs at step 0."""
        self.assertLess(registry.PRACTICAL_BUDGET_BYTES, 15 * GIB)
        arch = self._arch(SEVEN_B)
        plan = registry.plan_fit(arch, rank=16, target_modules=presets.ALL_SEVEN,
                                 seq_len=1024, batch=1)
        self.assertEqual(plan["budget_label"], "projected")
        plan_measured = registry.plan_fit(arch, rank=16, target_modules=presets.ALL_SEVEN,
                                          seq_len=1024, batch=1, free_bytes=13 * GIB)
        self.assertEqual(plan_measured["budget_label"], "measured")


class RegistryTests(unittest.TestCase):
    """The model picker. Real files, real sizes, real quantisations."""

    def test_gguf_quantisation_is_read_from_the_file(self):
        """The quantisation label must come from the tensor table, not from the filename.

        A file named `...Q4_K_M.gguf` that was secretly Q8_0 would be caught by this, which is
        the difference between a measured figure and an assumed one.
        """
        ggufs = [e for e in registry.catalogue() if e.kind == "gguf" and e.present]
        if not ggufs:
            self.skipTest("no GGUF weights on this box")
        for e in ggufs:
            self.assertEqual(e.quant_label, "measured")
            self.assertTrue(e.quantisation)
            self.assertTrue(e.tensor_types, "the per-tensor histogram is the evidence")
            self.assertGreater(e.bytes_on_disk, 0)

    def test_gguf_is_offered_but_rejected_with_a_reason(self):
        for e in registry.catalogue():
            if e.kind == "gguf":
                self.assertFalse(e.trainable)
                self.assertIn("training format", e.reason)

    def test_tied_embeddings_detected_from_the_tensor_table(self):
        """The 0.5B is tied (no output.weight); the 14B is not. Worth ~0.9 GiB on the 14B."""
        small = registry.find("Qwen2.5-0.5B-Instruct-Q4_K_M")
        big = registry.find("Qwen2.5-14B-Instruct-Q4_K_M")
        if not small or not big:
            self.skipTest("the 0.5B/14B GGUFs are not on this box")
        self.assertTrue(registry.Arch(**small.arch).tied_embeddings)
        self.assertFalse(registry.Arch(**big.arch).tied_embeddings)

    def test_hf_size_follows_symlinks(self):
        """The HF cache snapshots are symlinks into blobs/; reporting the link size would
        report ~60 bytes as the model size."""
        entry = registry.find(SEVEN_B)
        if entry is None or not entry.present:
            self.skipTest("the 7B is not in the local weight cache")
        self.assertGreater(entry.bytes_on_disk, 10 * GIB)

    def test_fetchable_rows_state_their_cost_and_are_not_trainable(self):
        for e in registry.catalogue():
            if not e.present and e.kind == "hf":
                self.assertFalse(e.trainable)
                self.assertGreater(e.fetch_bytes, 0)
                self.assertIn("not implemented", e.reason)

    def test_catalogue_never_touches_the_training_directory(self):
        """The picker enumerates weights. It must never enumerate the corpus."""
        for e in registry.catalogue():
            self.assertNotIn("corpus", e.path)
            self.assertFalse(e.path.startswith("training/"))

    def test_find_resolves_the_short_form(self):
        if registry.find(SEVEN_B) is None:
            self.skipTest("the 7B is not in the local weight cache")
        self.assertIsNotNone(registry.find("Qwen2.5-7B-Instruct"))
        self.assertIsNone(registry.find("no-such-model-anywhere"))


class PresetTests(unittest.TestCase):
    """The predetermined tuning methods, and the honesty rules they are held to."""

    def test_every_preset_has_a_rationale_for_its_choices(self):
        for pid, p in presets.PRESETS.items():
            with self.subTest(preset=pid):
                self.assertTrue(p.when, "a preset must say when it is the right one")
                self.assertTrue(p.rationale, "a value with no defensible source is not a preset")
                for key, why in p.rationale.items():
                    self.assertIn("provenance:", why,
                                  f"{pid}.{key} states no provenance")

    def test_alpha_is_twice_rank_everywhere(self):
        """Holding the ratio fixed is what makes rank the single knob it appears to be."""
        for pid, p in presets.PRESETS.items():
            with self.subTest(preset=pid):
                self.assertEqual(p.lora_alpha, p.rank * 2)

    def test_no_preset_claims_a_measured_quality_figure(self):
        """Nothing about training quality or throughput has been measured on this box.

        One adapter exists, from an unlogged run with no validation split. A preset carrying a
        'measured' quality claim would be the exact dishonesty CLAUDE.md names, so the only
        `measured` provenance permitted in this module is on `warmup`, where the measurement is
        a fact about the installed library rather than about training.
        """
        measured = [k for k, v in presets.SHARED.items() if v["provenance"] == "measured"]
        self.assertEqual(measured, ["warmup"])
        for p in presets.PRESETS.values():
            for why in p.rationale.values():
                self.assertNotIn("provenance: measured", why)

    def test_warmup_is_never_expressed_as_a_ratio(self):
        """`warmup_ratio` is absent from transformers 5.15.0 and trl 1.10.0 on this box; code
        copied from older guides raises TypeError here."""
        self.assertIn("never warmup_ratio", presets.SHARED["warmup"]["value"])
        # Read the AST, not the text. The comment on the line that sets `warmup_steps`
        # explains why `warmup_ratio` is not used, and a substring search would trip over its
        # own explanation -- which is how a source-text assertion quietly becomes untestable.
        keys = _dict_keys_and_kwargs(pathlib.Path(__file__).parent / "runner.py")
        self.assertIn("warmup_steps", keys)
        self.assertNotIn("warmup_ratio", keys)
        self.assertNotIn("group_by_length", keys, "also absent from transformers 5.15.0")

    def test_batch_is_one_and_checkpointing_is_on(self):
        """Both are forced by one 16 GiB card, and both are what the OOM ladder has already
        spent -- which is why `plan_fit`'s ladder never offers them as rungs."""
        self.assertEqual(presets.SHARED["per_device_train_batch_size"]["value"], 1)
        self.assertIs(presets.SHARED["gradient_checkpointing"]["value"], True)
        arch = registry.Arch(**registry.find(SEVEN_B).arch) if registry.find(SEVEN_B) else None
        if arch is None:
            self.skipTest("the 7B is not in the local weight cache")
        plan = registry.plan_fit(arch, rank=32, target_modules=presets.ALL_SEVEN,
                                 seq_len=8192, batch=1)
        self.assertEqual(plan["verdict"], "refused")
        joined = " ".join(plan["ladder"])
        self.assertNotIn("batch", joined.split("gradient")[0].replace("effective batch", ""))

    def test_every_preset_holds_out_a_validation_split(self):
        """The repo manual: hold out 5-10% BEFORE looking at training loss. The shipped trainer
        does not, which is why no loss figure from it means anything."""
        for pid, p in presets.PRESETS.items():
            with self.subTest(preset=pid):
                self.assertGreaterEqual(p.val_split, 0.05)

    def test_smoke_is_capped_in_steps(self):
        """A capped step count is what makes a smoke test a smoke test rather than a short run."""
        self.assertGreater(presets.PRESETS["smoke"].max_steps, 0)
        self.assertEqual(presets.PRESETS["smoke"].target_modules, presets.ATTENTION_ONLY)

    def test_preference_tuning_is_stated_not_built(self):
        """A control that cannot be used is a decorative control."""
        self.assertIn("preference_tuning", presets.NOT_IN_V1)
        self.assertIn("greyed-out", presets.NOT_IN_V1["preference_tuning"])

    def test_fit_table_costs_every_preset(self):
        if registry.find(SEVEN_B) is None:
            self.skipTest("the 7B is not in the local weight cache")
        rows = presets.fit_table(SEVEN_B)
        self.assertEqual(len(rows), len(presets.PRESETS))
        by_id = {r["preset"]: r["plan"] for r in rows}
        for row in rows:
            self.assertEqual(row["plan"]["label"], "projected")
            # Every preset must at least be offerable on the one model this box can train.
            self.assertNotEqual(row["plan"]["verdict"], "refused", row["preset"])
        # Long-form is the preset nearest the ceiling, and it is honest about being tight
        # rather than presenting a 1.1 GiB margin as comfort.
        self.assertEqual(by_id["longform"]["verdict"], "tight")
        self.assertEqual(by_id["voice"]["verdict"], "fits")
        self.assertLess(by_id["smoke"]["projected_peak_bytes"],
                        by_id["longform"]["projected_peak_bytes"])


class TradeSecretTests(unittest.TestCase):
    """The guard that matters most. `training/corpus.jsonl` is protected only by not being
    public, and this surface is the likeliest accident."""

    def test_corpus_is_refused_from_any_working_directory(self):
        """A guard whose answer depends on where the process was started is not a guard.

        This caught a live bug: `is_denied` resolved a relative path against the process's cwd
        while `admit()` resolved the same string against the repo root, so the refusal held
        from the repo root and failed from anywhere else. It now judges both interpretations.
        """
        import os as _os
        cwd = _os.getcwd()
        try:
            for where in (registry.ROOT, registry.ROOT / "backend", pathlib.Path("/tmp")):
                _os.chdir(where)
                with self.subTest(cwd=str(where)):
                    self.assertTrue(dataset_guard.is_denied(
                        pathlib.Path("training/corpus.jsonl")))
                    with self.assertRaises(dataset_guard.Refused) as ctx:
                        dataset_guard.admit("training/corpus.jsonl")
                    self.assertEqual(ctx.exception.code, "protected")
        finally:
            _os.chdir(cwd)

    def test_corpus_is_refused_by_every_spelling(self):
        corpus = registry.ROOT / "training" / "corpus.jsonl"
        spellings = [
            str(corpus),
            "training/corpus.jsonl",
            "./training/corpus.jsonl",
            "training/../training/corpus.jsonl",
            "training/adapter/../corpus.jsonl",
            str(registry.ROOT / "training" / "." / "corpus.jsonl"),
        ]
        for s in spellings:
            with self.subTest(spelling=s):
                self.assertTrue(dataset_guard.is_denied(pathlib.Path(s)))
                with self.assertRaises(dataset_guard.Refused) as ctx:
                    dataset_guard.admit(s)
                self.assertEqual(ctx.exception.code, "protected")

    def test_a_symlink_to_the_corpus_is_refused(self):
        corpus = registry.ROOT / "training" / "corpus.jsonl"
        if not corpus.is_file():
            self.skipTest("no corpus on this box")
        with tempfile.TemporaryDirectory() as td:
            link = pathlib.Path(td) / "innocent.jsonl"
            link.symlink_to(corpus)
            self.assertTrue(dataset_guard.is_denied(link))
            with self.assertRaises(dataset_guard.Refused) as ctx:
                dataset_guard.admit(str(link))
            self.assertEqual(ctx.exception.code, "protected")

    def test_build_dataset_and_the_adapter_tree_are_refused(self):
        self.assertTrue(dataset_guard.is_denied(registry.ROOT / "training" / "build_dataset.py"))
        self.assertTrue(dataset_guard.is_denied(
            registry.ROOT / "training" / "adapter" / "adapter_model.safetensors"))

    def test_the_refusal_message_describes_nothing(self):
        """The refusal is the feature. A helpful explanation of what is inside defeats it."""
        with self.assertRaises(dataset_guard.Refused) as ctx:
            dataset_guard.admit("training/corpus.jsonl")
        msg = ctx.exception.message.lower()
        for leak in ("persona", "refusal", "pricing", "example", "voice", "327"):
            self.assertNotIn(leak, msg)

    def test_deny_is_checked_before_existence(self):
        """Checking existence first would let a caller probe for the corpus by the difference
        between 'denied' and 'not found'."""
        with self.assertRaises(dataset_guard.Refused) as ctx:
            dataset_guard.admit("training/corpus.jsonl")
        self.assertEqual(ctx.exception.code, "protected")
        with self.assertRaises(dataset_guard.Refused) as ctx2:
            dataset_guard.admit("training/no-such-file-at-all.jsonl")
        self.assertEqual(ctx2.exception.code, "not_found")

    def test_runner_carries_its_own_copy_of_the_denylist(self):
        """The runner runs in a different interpreter under a different cwd. A guard that
        depends on an import path is a guard a refactor can lose, so it duplicates the list --
        and the two copies must agree."""
        source = (pathlib.Path(__file__).parent / "runner.py").read_text()
        self.assertIn('"corpus.jsonl"', source)
        self.assertIn('"build_dataset.py"', source)
        self.assertIn("ProtectedArtefact", source)

    def test_no_module_globs_the_training_directory(self):
        """A dataset picker that scans the sibling directory publishes the recipe. This asserts
        that no module in the serving path does, by reading the source."""
        here = pathlib.Path(__file__).parent
        for name in ("registry.py", "presets.py", "jobs.py", "routes.py", "dataset_guard.py"):
            src = (here / name).read_text()
            for forbidden in ('glob("training', "glob('training", '"training/*.jsonl"',
                              "iterdir()  # training"):
                self.assertNotIn(forbidden, src, f"{name} enumerates training/")

    def test_staging_directory_is_outside_the_published_webroot(self):
        """`deploy.sh` publishes `site/` wholesale. A dataset there would be public."""
        self.assertNotIn("site", dataset_guard.STAGE.parts)
        self.assertIn("run", dataset_guard.STAGE.parts)

    def test_malformed_rows_report_a_line_number_and_never_the_line(self):
        sentinel = "SYMONEURAL-SECRET-TRAINING-EXAMPLE"
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "bad.jsonl"
            p.write_text(
                json.dumps({"messages": [{"role": "user", "content": "hi"},
                                         {"role": "assistant", "content": "hello"}]}) + "\n"
                + '{"messages": "' + sentinel + '"}\n')
            with self.assertRaises(dataset_guard.Refused) as ctx:
                dataset_guard.admit(str(p))
            self.assertEqual(ctx.exception.code, "malformed")
            self.assertIn("line 2", ctx.exception.message)
            self.assertNotIn(sentinel, ctx.exception.message)

    def test_a_good_dataset_reports_shape_only(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "ok.jsonl"
            rows = [{"messages": [{"role": "user", "content": f"q{i}"},
                                  {"role": "assistant", "content": f"a{i}"}]} for i in range(5)]
            p.write_text("\n".join(json.dumps(r) for r in rows))
            info = dataset_guard.admit(str(p))
            self.assertEqual(info.rows, 5)
            payload = json.dumps(info.to_dict())
            self.assertNotIn("q0", payload)
            self.assertNotIn("a0", payload)

    def test_there_is_no_default_dataset(self):
        with self.assertRaises(dataset_guard.Refused) as ctx:
            dataset_guard.admit("")
        self.assertEqual(ctx.exception.code, "no_dataset")
        self.assertIn("does not fall back", ctx.exception.message)


class LogAllowlistTests(unittest.TestCase):
    """The other half of the trade-secret guard: a training process's stdout is not trusted."""

    def test_log_parser_drops_unknown_lines(self):
        """A traceback carrying a training example must not survive into an API response.

        This is an allowlist, not a denylist: the sentinel is dropped because the line does not
        match a known shape, not because anything recognised it as secret.
        """
        sentinel = "SYMONEURAL-SECRET-TRAINING-EXAMPLE"
        log = "\n".join([
            "Loading checkpoint shards: 100%|##########| 4/4",
            f'  File "train.py", line 9, in encode: row = {{"messages": "{sentinel}"}}',
            f"ValueError: could not tokenise {sentinel}",
            "REINFORCE event=step step=3 total_steps=8 loss=1.234 elapsed_s=12.5",
            f"REINFORCE event=step note={sentinel}",
        ])
        events = jobs.parse_log(log)
        self.assertEqual(len(events), 2)
        self.assertNotIn(sentinel, json.dumps(events))
        self.assertEqual(events[0]["step"], 3)
        self.assertEqual(events[0]["loss"], 1.234)
        # The last line is well-formed but carries a key outside the allowlist; the key is
        # dropped while the event survives.
        self.assertNotIn("note", events[1])

    def test_out_of_vocabulary_enum_values_are_dropped(self):
        self.assertEqual(jobs.parse_log("REINFORCE event=exfiltrate step=1"), [])
        self.assertEqual(jobs.parse_log("REINFORCE event=error kind=X stage=elsewhere"), [])
        ok = jobs.parse_log("REINFORCE event=error kind=OutOfMemoryError stage=train")
        self.assertEqual(ok[0]["kind"], "OutOfMemoryError")

    def test_overlong_and_spaced_values_are_dropped(self):
        self.assertEqual(jobs.parse_log("REINFORCE event=step kind=" + "x" * 65), [])
        self.assertEqual(jobs.parse_log('REINFORCE event=step kind=a b c'), [])
        self.assertEqual(jobs.parse_log("prefix REINFORCE event=step step=1"), [])

    def test_non_numeric_values_in_numeric_fields_are_rejected(self):
        self.assertEqual(jobs.parse_log("REINFORCE event=step step=NaNsy-text"), [])

    def test_runner_emit_and_parser_agree(self):
        """Both ends of the protocol are constrained, so they cannot drift silently."""
        src = (pathlib.Path(__file__).parent / "runner.py").read_text()
        self.assertIn('print("REINFORCE "', src)
        # The runner must not print an exception *message* anywhere on stdout.
        self.assertNotIn("print(exc", src)
        self.assertIn("traceback.print_exc(file=sys.stderr)", src)


class LaunchPathTests(unittest.TestCase):
    """The GPU rules, asserted on the command that would actually be run."""

    def test_launch_uses_the_with_form(self):
        script = jobs.build_script(["/x/python", "runner.py", "--preset", "smoke"],
                                   pathlib.Path("/tmp/j.exit"))
        self.assertIn("gpu-governor.sh with train --", script)

    def test_launch_never_calls_a_bare_release(self):
        """An unscoped release once destroyed a running fine-tune's lock from the API's
        shutdown hook. The release belongs to the governor's `with` form, and this package
        must not write one at all."""
        script = jobs.build_script(["/x/python"], pathlib.Path("/tmp/j.exit"))
        self.assertNotIn("release", script)
        self.assertNotIn("acquire", script)
        here = pathlib.Path(__file__).parent
        for name in ("jobs.py", "routes.py", "runner.py", "registry.py"):
            src = (here / name).read_text()
            for call in ("governor.sh release", "governor.sh acquire",
                         '"release"', "'release'", '"acquire"', "'acquire'"):
                self.assertNotIn(call, src, f"{name} talks to the governor directly")

    def test_dataset_paths_are_shell_quoted(self):
        script = jobs.build_script(["/x/python", "--dataset", "/tmp/a b; rm -rf /"],
                                   pathlib.Path("/tmp/j.exit"))
        self.assertNotIn("; rm -rf /'", script.replace("'/tmp/a b; rm -rf /'", ""))
        self.assertIn("'/tmp/a b; rm -rf /'", script)

    def test_exit_code_is_written_after_the_governor_returns(self):
        script = jobs.build_script(["/x/python"], pathlib.Path("/tmp/j.exit"))
        self.assertTrue(script.index("gpu-governor.sh") < script.index("printf"))
        self.assertIn("$?", script)

    def test_no_module_here_shadows_a_training_stack_package(self):
        """A sibling module named after a third-party package breaks the runner after acquire.

        This bit: `datasets.py` in this directory shadowed Hugging Face's `datasets` for the
        subprocess, because Python puts a script's own directory at sys.path[0]. The run failed
        at import -- 74 seconds after it had taken the GPU. Two fixes, and this asserts both:
        the module was renamed, and `runner.py` now removes its own directory from sys.path.
        """
        here = pathlib.Path(__file__).parent
        reserved = {"datasets", "torch", "transformers", "peft", "accelerate", "trl",
                    "bitsandbytes", "numpy", "tokenizers", "safetensors", "json", "os", "re"}
        for py in here.glob("*.py"):
            self.assertNotIn(py.stem, reserved,
                             f"{py.name} shadows a package the runner imports")
        self.assertIn("sys.path[:] = [p for p in sys.path", (here / "runner.py").read_text())

    def test_the_runner_is_invoked_with_the_training_interpreter(self):
        """The serving API runs on the system interpreter and has no torch. The training venv
        is cu128 because Blackwell sm_120 needs it."""
        self.assertEqual(jobs.TRAIN_PYTHON,
                         registry.ROOT / "training" / ".venv" / "bin" / "python")
        self.assertNotEqual(str(jobs.TRAIN_PYTHON), sys.executable)

    def test_serving_modules_import_no_training_stack(self):
        """Everything importable by api.py must be stdlib-only.

        Walks the AST rather than grepping the text: these modules discuss torch, transformers
        and peft at length in their docstrings, and a substring search would fail on its own
        documentation. The AST answers the question actually being asked -- what does this
        module import.
        """
        here = pathlib.Path(__file__).parent
        heavy = {"torch", "transformers", "peft", "numpy", "bitsandbytes", "trl", "datasets_hf",
                 "accelerate", "cupy", "cuda"}
        for name in ("registry.py", "presets.py", "dataset_guard.py", "jobs.py", "__init__.py"):
            for mod in _imported_modules(here / name):
                self.assertNotIn(mod.split(".")[0], heavy,
                                 f"{name} imports the training stack ({mod})")

    def test_routes_import_only_fastapi_and_pydantic(self):
        """Both are already OS packages on the system interpreter; the serving path has no
        virtualenv and nothing may be pip-installed into it."""
        mods = {m.split(".")[0] for m in
                _imported_modules(pathlib.Path(__file__).parent / "routes.py")}
        self.assertTrue(mods <= {"os", "hmac", "fastapi", "pydantic", "__future__", ""},
                        f"unexpected imports in routes.py: {mods}")


class RackUnitTests(unittest.TestCase):
    """`Unit.state` is a four-value Literal. An out-of-vocab string raises pydantic at
    /api/status and takes every other unit's rack row down with it."""

    VALID = {"ready", "busy", "queued", "offline"}

    def test_status_keys_match_the_unit_model(self):
        st = jobs.status()
        self.assertEqual(set(st), {"id", "label", "slot", "state", "bus", "href", "spec", "detail"})
        self.assertIn(st["state"], self.VALID)
        self.assertIn(st["bus"], {"gpu", "cpu", "asic", "net"})
        self.assertEqual(st["id"], "train")
        self.assertEqual(st["label"], "SyMoNeuRaL Reinforce")

    def test_status_is_offline_when_the_surface_is_off(self):
        old = dict(os.environ)
        try:
            os.environ.pop("SYM_REINFORCE_ENABLED", None)
            self.assertEqual(jobs.status()["state"], "offline")
            self.assertIn("SYM_REINFORCE_ENABLED", jobs.status()["detail"])
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_status_reports_a_real_model_count_when_enabled(self):
        old = dict(os.environ)
        try:
            os.environ["SYM_REINFORCE_ENABLED"] = "1"
            os.environ["SYM_REINFORCE_TOKEN"] = "test-token"
            st = jobs.status()
            self.assertIn(st["state"], self.VALID)
            if st["state"] == "ready":
                n = sum(1 for e in registry.catalogue() if e.trainable)
                self.assertIn(f"{n} base model(s) loadable", st["detail"])
                self.assertIn(f"{len(presets.PRESETS)} tuning presets", st["detail"])
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_no_decorative_indicator_when_there_is_no_run(self):
        snap = jobs.snapshot()
        if snap["state"] == "none":
            self.assertEqual(snap["detail"], "no run has been started from this surface")
            self.assertEqual(snap["events"], [])
            self.assertIsNone(snap["job"])

    def test_branding_carries_no_vendor_product_names(self):
        """The surface is SyMoNeuRaL Reinforce. Technique descriptions may say '4-bit low-rank
        adaptation', which describes the method without using anybody's product name."""
        st = jobs.status()
        blob = json.dumps(st).lower()
        for banned in ("qlora", "qwen", "mit ai training"):
            self.assertNotIn(banned, blob)
        self.assertIn("4-bit low-rank adaptation", st["spec"])

    def test_eta_is_labelled_projected(self):
        snap = jobs.snapshot()
        if snap.get("eta_s") is not None:
            self.assertEqual(snap["eta_label"], "projected")


class PreflightTests(unittest.TestCase):

    def test_unknown_preset_and_model_are_refused_by_name(self):
        r = jobs.preflight(SEVEN_B, "no-such-preset")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_preset")
        r2 = jobs.preflight("no-such-model", "voice")
        self.assertFalse(r2["ok"])
        self.assertEqual(r2["reason"], "unknown_model")

    def test_a_gguf_is_refused_with_the_reason_not_a_shrug(self):
        gguf = next((e for e in registry.catalogue() if e.kind == "gguf"), None)
        if gguf is None:
            self.skipTest("no GGUF weights on this box")
        r = jobs.preflight(gguf.id, "voice")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "model_not_trainable")
        self.assertIn("training format", r["message"])

    def test_preflight_refuses_the_corpus_as_a_dataset(self):
        r = jobs.preflight(SEVEN_B, "smoke", "training/corpus.jsonl")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "dataset_protected")


if __name__ == "__main__":
    unittest.main(verbosity=2)
