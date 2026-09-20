# Executed live evaluations

These sanitized reports were produced by actual OpenRouter calls, not test providers. Query IDs refer to the developer's ignored local runtime database; a fresh installation generates its own IDs. No credential, raw request header, or runtime database is included.

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
