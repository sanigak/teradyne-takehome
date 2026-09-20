# Evaluation and quality monitoring

## Three different checks

1. **Deterministic tests** exercise extraction, source attribution, source versioning, retrieval boundaries, citation rejection, provider failures, and API persistence with test-only providers. They do not require credentials and do not establish live model quality.
2. **Browser workflow tests** verify asking, opening evidence, submitting corrections, resolving reviews, editing routing drafts, and persisting simulated outbox entries. Network fixtures are isolated to the tests, never used as an application mode.
3. **Live evaluation** runs committed questions against the ingested corpus and configured OpenRouter models. It records actual case outcomes and fails when expectations are not met.

Run `python -m app smoke` to validate live structured output and embeddings before ingestion. Run `python -m app evaluate` for the configured suite; the default is the 45-case frozen model-selection set in `data/model_evaluation_gold.json`. Both versioned objects containing `cases` and the older list datasets are accepted. `--limit N` is available for an explicitly shortened canary. The command needs a configured key and an ingested corpus and consumes provider credits.

The original 12 cases became a regression suite after the first live run informed implementation changes. An independent six-case audit is committed at `data/evaluation_audit.json`; its questions and labels were frozen before testing the revised implementation. Set `EVALUATION_PATH` to that file to reproduce it. The first audit outcome is recorded separately from subsequent development runs rather than described as an untouched benchmark after tuning.

## What the suite measures

Each case names expected source files, answer status, required factual terms where appropriate, and forbidden unsupported claims. The evaluator reports source recall, expected-fact coverage, citation validity, abstention status accuracy, and per-case failures. Exact factual assertions are deliberately narrow; wording-sensitive failures need inspection rather than an automatic claim that the model is wrong.

Adversarial cases additionally assert empty evidence/routing for unrelated questions, required source-backed recipients, and answer-shape invariants. Recipient attribution is checked against every routing evidence reference. A correct status alone cannot make invented expertise pass. Alerts keep the latest result for each dataset/suite visible: a passing small canary cannot hide a failing full suite.

The suite includes explicit supersession, cross-format questions, an unresolved conflict between approved records, a missing vendor commitment, and a completely unrelated question. Model-selection work adds numerical comparisons, conditional logging rules, unsupported negative inferences, and 12 source-checked holdout questions. See [the frozen selection protocol](MODEL_SELECTION.md) for the distinction between regression and previously untouched cases.

All defined assertions must pass for a successful evaluation command. A lower pass rate than the previous run of the same suite raises a regression alert. Individual failed assertions raise alerts even without a prior baseline. Evaluation traffic is stored for audit but excluded from the user review queue and first-month feedback metric.

While the application runs with a key and ingested corpus, the scheduler executes the entire configured suite daily. A persisted atomic claim tracks the dataset hash, models, inference options, embeddings, and answer prompts. It prevents duplicate runs across local server processes; an interrupted run waits 24 hours before another scheduled attempt, preventing repeated paid retries every minute. A canary or another dataset does not postpone this full run, and a changed model profile makes a new check due. `/api/quality` and the UI expose results and unresolved failed-case counts per dataset/suite. This uses live credits; set `DAILY_EVALUATION=false` to disable scheduling or explicitly choose another `EVALUATION_PATH`. The scheduler cannot monitor a stopped server. The separate manual GitHub Actions workflow provides a reproducible live evaluation path when its secret is configured.

## Interpreting the results

Citation validity proves that the referenced ID and quotation exist; it does not by itself prove that a claim follows from the quotation. Answer-blind coverage assessment, a separate model support check, and factual assertions provide additional evidence. Daily evaluation checks the existing lexical and structural assertions; it does not independently grade all semantic `required_facts` and `scope_guards` in the frozen gold file. Complete answers receive separate independent semantic inspection for model selection and release. The application's reviewer can share the generator's errors and is not ground truth. The small synthetic set is a regression tool, not a production accuracy estimate. A deployment would need representative user questions, independently reviewed labels, and larger failure slices.

For the first 30 days after launch, the README defines the consumer rejection/correction rate. Its numerator is deduplicated by answered query ID, and voluntary-feedback selection bias is explicit.

Actual executed checks and any remaining live prerequisites are recorded in `docs/VALIDATION.md`; do not substitute intended checks for completed ones.

## Reproduce the adversarial live audit

`scripts/adversarial_live.py` creates a SQLite backup in a **new** subdirectory of `.runtime`, preserves corpus/version/cache data, and clears user history only in that copy. It never overwrites the normal workspace. It writes full answer snapshots for semantic review and exits unsuccessfully when evaluation assertions fail.

```powershell
# Windows: refresh the saved backend key for this process.
Set-ExecutionPolicy -Scope Process Bypass -Force
. ./scripts/environment.ps1
.venv/Scripts/python.exe scripts/adversarial_live.py --output-dir .runtime/my-adversarial-run
.venv/Scripts/python.exe scripts/adversarial_live.py --dataset data/evaluation_injection.json --injection-fixture tests/fixtures/injection_source.md --output-dir .runtime/my-injection-run
```

On Linux, use `.venv/bin/python` with the same arguments after exporting the backend key. These commands call live OpenRouter and consume credits. The injection fixture is intentionally hostile test data; it is **not** part of the 24-document corpus. First-run failures, independent semantic reviews, and subsequent regression runs are retained in [the adversarial record](ADVERSARIAL_TESTING.md). These cases become regression tests after their results inform changes, not untouched held-out evidence.

The development agent's final semantic inspection is also an explicit quality report, separate from automatic model judgments. Run `python scripts/record_semantic_review.py docs/evaluation-results/adversarial-semantic-review.json` to import those known findings into a local workspace's quality history. This makes the warning visible in the UI, is idempotent, performs no model calls, and does not create user feedback or change source truth. It describes this checked-in release, not a new evaluation of subsequently modified data or code. A later fix requires a newly reviewed report, not deletion of the failure history.
