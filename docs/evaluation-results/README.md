# Executed live evaluations

These sanitized reports preserve actual OpenRouter outputs and separate independent development reviews. Benchmark query/source IDs refer to isolated benchmark databases, while earlier application runs used the developer's ignored local database; a fresh installation generates its own IDs. No credential, raw request header, or runtime database is included. Fixture-based software tests and fresh-setup checks are identified separately.

## Accuracy-first model comparison

The [model-selection record](../MODEL_SELECTION.md) explains the exact configurations, frozen rubric, original holdout boundaries, costs, and limitations. Independent reviews are performed by separate Codex agents, not human ground truth. Automatic citation validity does not establish semantic support.

| Report | Purpose | Result |
| --- | --- | --- |
| [Six-model screen](model-benchmark-screen-adjudication.json) | Lock independent claim judgments before revealing models | Comparison baseline and finalist selection |
| [Original full comparison](model-benchmark-full-adjudication.json) | Three configurations, 45 questions each | Astra 43/45; Luna/Astra 41/45; Luna 39/45 |
| [Original enrichment comparison](model-benchmark-enrichment-adjudication.json) | Two models, 24 documents each | Astra 21/24; Luna 20/24 semantic passes |
| [Comparison measurements](model-benchmark-full-measurements.json) | Actual usage cost and elapsed time | Costs and latency remain separate from quality judgments |
| [402 diagnostic](model-benchmark-402-diagnostic.json) | Single request after credits were added | Succeeded; original error subtype was not captured |
| [Enrichment prompt revision](model-benchmark-enrichment-prompt-revision.json) | Preserve exact before/after instructions | General completeness and conditional-scope fixes |
| [Revised enrichment](model-benchmark-revised-enrichment-adjudication.json) | Actual fresh enrichment of all 24 documents | 24/24 semantic passes, exact attribution and hashes |
| [Completeness prompt revision](model-benchmark-completeness-prompt-revision.json) | Preserve exact before/after instructions | Completeness follows the question's requested components |
| [Revised reviewer controls](model-benchmark-controls-2026-09-20T17-52-02.402044+00-00.json) | Five known supported/unsupported controls | 5/5 correct |
| [Revised full regression](model-benchmark-revised-full-adjudication.json) | Same frozen 45 questions after general fixes | 44/45 independent passes; rehearsal-scope citation gap retained |
| [Nine repeat inspections](model-benchmark-revised-repeat-review.json) | Three additional answers for each earlier hard case | 8/9 passes; the same scope-citation gap recurred |
| [Final v3 hard-case repetitions](model-benchmark-v3-repeat-adjudication.json) | Three new repetitions of each prior hard case, exact main snapshot | 9/9 independent passes; full v3 45-case run remains pending |
| [Final spend](model-benchmark-final-spend.json) | All earlier charges and unknown billing bounds retained | USD 34.684228 reported; USD 35.796194 conservatively accounted |
| [Fresh Windows setup](revision-fresh-setup.json) | New environment, locked installs, production build, missing-key behavior | Passed; no provider calls |
| [Actual main ingestion](revision-ingest-2026-09-20T18-11-07.644698_00-00-707c78.json) | Refresh main24, preserve history, repeat idempotently | 24/24; 72 original hashes; repeat zero model calls |
| [Actual main enrichment review](release-main-enrichment-review.json) | Independently review the newly generated main metadata | 24/24; 105 decisions, 47 actions, 264 provenance checks |
| [Selected-model smoke](revision-smoke-2026-09-20T18-20-45.640997_00-00-8b9964.json) | Live Astra structured output and embeddings | Passed |
| [Real UI rehearsal](revision-live-ui.json) | Live answers, evidence, review, Outbox, sample API upload and Developer tools | Recorded flows passed; actual browser-picker upload blocked by extension permission |
| [Live UI answer review](revision-live-ui-semantic-review.json) | Independently inspect the five actual UI answers | 5/5; nine claims, 27 exact quotations, 14 routing references |

Subsequent selected-configuration reviews hide cost, timing, and automatic verdicts, but the selected recipe is known. They are regression checks, not a new fully model-blind comparison or an untouched holdout estimate. Raw reports, anonymized packets, and locked reviews are preserved alongside joined verdicts. The original 12 holdout questions became regressions once their failures informed changes.

## Earlier application evaluations

| Report | Purpose | Result |
| --- | --- | --- |
| [Provider smoke](provider-smoke.json) | Structured output and 1,536-dimension embeddings | Passed |
| [Initial 12 cases](initial-12-cases.json) | First live run before integration fixes | 8/12 |
| [Revised 12 cases](revision-12-cases.json) | Citation repair and coverage review improvements | 10/12 |
| [Component coverage](coverage-12-cases.json) | Structured requested-value coverage | 11/12; all abstention cases correct, one exact-quotation failure safely rejected |
| [Interrupted transport run](aborted-tls-run.json) | Raw TLS transport error | Aborted; no aggregate score |
| [Source span citations](span-citations-12-cases.json) | Backend-resolved quotations and transport handling | 11/12; all source/fact/citation checks passed, one missing-fact status failed |
| [First held-out audit](first-held-out-audit.json) | Six new questions, frozen before testing | 4/6; all source/fact/citation checks passed, two incomplete answers were labeled answered |
| [Final 12 cases](final-12-cases.json) | Answer-blind GPT-4.1 coverage; GPT-4.1-mini generation; separate support review | 12/12; all reported quality metrics 1.0 |
| [Final audit rerun](final-audit-rerun.json) | Same six audit questions after addressing the first run's failures | 6/6; all reported quality metrics 1.0 |
| [Adversarial first answers](adversarial-first-answers.json) | Fifteen new questions, before adversarial fixes | Automatic 15/15; [separate inspection](adversarial-first-manual-review.md) 13/15 |
| [Adversarial intermediate answers](adversarial-intermediate-answers.json) | Narrowed claim context and completeness checking | Automatic 15/15; [separate inspection](adversarial-final-manual-review.md) 12/15 |
| [Original source injection](source-injection-first.json) | Malicious source attempts to control generator and reviewer | 1/2; attack successfully fabricated a retention answer |
| [Source injection rerun](source-injection-rerun.json) | Whole-document exclusion before question-time inference | 2/2; attack source excluded from evidence/routing |
| [Reviewer comparison](reviewer-comparison.md) | Three known invalid claims, two valid controls | GPT-4.1 2/5; Sonnet 5 3/5; model swap insufficient |
| [Reviewer calibration](reviewer-calibrated.md) | Added generic support examples, same controls | GPT-4.1 2/5; no improvement; prompt expansion removed |
| [Intermediate original suite](adversarial-intermediate-12.json) | Stricter support removed a rollout claim | 11/12; failure preserved |
| [Release original suite](adversarial-release-12.json) | Bounded support repair | 12/12 automatic |
| [Earlier audit regression](adversarial-regression-6.json) | Six prior audit questions, adversarial hardening | 6/6 automatic |
| [Release adversarial answers](adversarial-release-answers.json) | Final 15-question regression with full snapshots | 15/15 automatic; [strict inspection](adversarial-release-manual-review.md) 12/15 |
| [Semantic quality report](adversarial-semantic-review.json) | Importable explicit development review | Three open findings, visible quality alert |
| [Live reingestion](adversarial-reingestion.json) | Canonical corpus and historical versions | 24 documents, 36 chunks, 48 archive hashes; repeat zero model calls |
| [Live UI workflows](adversarial-live-ui.json) | Real browser, no network fixtures | Both complete workflows passed; no email delivered |

The initial questions became development regression cases once their failures were inspected. Their results do not establish untouched held-out performance. The separate six-case audit was prepared without exposing its questions to the implementation agent. Its first result was 4/6; the later 6/6 rerun is a regression result after those failures informed fixes, not an untouched held-out score. These are small synthetic suites and not production accuracy estimates. See [validation](../VALIDATION.md) for release checks and limitations.
