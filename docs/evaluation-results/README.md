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

The initial questions became development regression cases once their failures were inspected. Their results do not establish untouched held-out performance. The separate six-case audit was prepared without exposing its questions to the implementation agent. Its first result was 4/6; the later 6/6 rerun is a regression result after those failures informed fixes, not an untouched held-out score. These are small synthetic suites and not production accuracy estimates. See [validation](../VALIDATION.md) for release checks and limitations.
