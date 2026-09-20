# Adversarial testing record

This preserves the earlier adversarial audit and its original failures. For the later UI/model revision, current test counts, and subsequent verification, read [validation](VALIDATION.md) and [model selection](MODEL_SELECTION.md). Historical model choices and browser counts below describe that earlier stage.

The user requested an independent, serious test of the take-home and a personal UI/CX review queue. All three pages of the original exercise brief were re-read. Testing covered the transcript API, all six Office extensions, provenance/routing, correction and gap persistence, quality monitoring, and the full React experience.

**Read the live semantic findings as well as the automated scores.** An automatic 15/15 result concealed unsupported clauses and incomplete claim citations. Those failures are preserved below. The application has stronger failure boundaries now, but a model's support verdict is not proof of entailment.

## Reproduced defects and changes

| Area | Reproduced problem | Change and regression coverage |
| --- | --- | --- |
| Source instructions | A retrieved document impersonated a system message, ordered a 999-year retention claim, and fooled generation and verification. | Screen all chunks of each active document before question-time inference. Exclude the entire flagged document from answers/routing; retain its original and show a health warning. Unicode/HTML obfuscation cases and benign corpus cases are covered. All-quarantined input is an operational failure, not a knowledge gap. |
| Attribution | Body text containing `Author:` was accepted as trusted metadata across Markdown and modern Office formats. | Parse the leading metadata region only; preserve deterministic source identity. |
| Cross-platform PowerPoint | Ubuntu LibreOffice discarded legacy PPT core attribution and supplied a generic title, causing three Linux CI failures after the stricter header parser change. | Recover the visible title from its placeholder or a styled leading shape immediately above metadata. Limit slide attribution to slide 1, excluding notes; reproduce generic-title conversion and body/notes spoofing in regression tests. |
| Versions | A changing file could yield text inconsistent with its archived hash; concurrent ingestion could duplicate versions or replace a newer version with stale work. | Extract from a byte snapshot and serialize compare-and-replace publication. Preserve historical evidence. |
| Corpus lifecycle | Deleted files remained active indefinitely. | An explicit folder ingestion retires missing paths after successful discovery, retaining historical citations/downloads. Discovery errors do not masquerade as deletion. |
| Extraction bounds | Malformed archives, oversized expansion, sparse worksheet dimensions, and source-size edges lacked complete limits. | Bound source size, expanded OOXML, archive parts, worksheet cell ranges, and legacy conversion time; report per-file failures. |
| Provider protocol | Malformed choices/message structures escaped as HTTP 500s; booleans/strings were coerced into trusted verifier fields or vectors; duplicate JSON keys and extreme retry values were ambiguous. | Strict Pydantic types, unambiguous JSON, numeric finite vectors, bounded retry timing, sanitized operational errors and telemetry. |
| Local API | Arbitrary Host names and cross-origin browser mutations were accepted; body size lacked a stream-level bound. | Exact local Host allowlist, same-origin browser mutation checks, 64 KiB API body bound. CLI use remains supported. |
| Retrieval | Invalid cached/stored vectors could become errors or apparent semantic nonmatches; extreme finite scales overflowed/underflowed cosine. | Rebuild invalid cached vectors, fail visibly on corrupt stored vectors, and scale cosine safely. |
| Claim checking | Individually true claims could omit requested components; uncited evidence in the review payload could influence judgments. | Explicit completeness verdict, per-claim cited context, no uncited coverage values in the support payload, one bounded support-repair attempt, and missing-component messages. Semantic limitations remain below. |
| Quality monitoring | A passing canary could hide a failing full suite; a correct abstention status could mask invented routing. | Retain latest alerts per dataset/suite; assert empty unrelated evidence/routing, valid recipient attribution, and substantive answer shapes. Persistent amber UI badges expose quality failures/read errors. |
| UI state | A late Ask response overwrote a newer selection; a late review refresh hid new feedback; resolution notes disappeared across navigation; Ctrl+Enter bypassed readiness. | Request ordering, persisted editor state, and one shared submission guard, with failing-before/passing-after browser regressions. |
| UI resilience | Malformed successful responses crashed React; 320px navigation overflowed; mobile evidence remained off-screen; dialog focus jumped. | Runtime response validation, bounded layout, explicit evidence focus/scroll, focus restoration and trapping. Write errors retain editable input. |

Additional adversarial checks cover path traversal, SQL-like IDs, forged evidence from another query, concurrent feedback writes, immutable snapshots, provider redirects/timeouts/cancellation, literal malicious markup, retries, and saved review/outbox state after reload.

## Live evidence and unresolved semantic limits

The fresh 15-question set covers historical/current scope, plans versus observations, exact threshold boundaries, mixed-client retention, conflicting approvals, simulation versus actual incidents, absent contracts, user instruction attacks, familiar names without relevant expertise, outside knowledge, claimed authority, Spanish paraphrases, mixed known/unknown components, and unmeasured business outcomes.

- The first run scored **15/15 automatically but 13/15 on independent semantic inspection**. See [the first review](evaluation-results/adversarial-first-manual-review.md).
- A subsequent run again scored **15/15 automatically but 12/15 under the strict per-claim standard**. See [the intermediate review](evaluation-results/adversarial-final-manual-review.md). The remaining issues were an uncited observed number inside one claim, a conditional logging rule stated globally, and an extra negative about what data a rehearsal involved.
- The original malicious-source test scored **1/2**: the invented retention claim was accepted. After application-level exclusion, its rerun scored **2/2**, and the attack document reached neither final evidence nor routing. The fixture remains committed outside the normal corpus.
- A controlled experiment presented three known bad claims and two valid controls to reviewers. GPT-4.1 classified **2/5** correctly; Sonnet 5 classified **3/5** correctly. Added prompt examples did not improve GPT-4.1's **2/5**. The model defaults remain unchanged; the unsuccessful prompt expansion was removed. Exact inputs, results, timing, and recorded costs are in [the reviewer comparison](evaluation-results/reviewer-comparison.md) and [calibration report](evaluation-results/reviewer-calibrated.md).

These results do **not** justify declaring every returned claim fully supported. Treat the strict semantic failures as open quality findings, even if a later phrasing or run passes. Bounded repair helps a model correct rejected output; it cannot repair an error that the verifier incorrectly accepts. Recognizable instruction screening also does not detect every possible attack or convincing fabricated business facts. Larger independent labels and evidence-level support checks would be required before treating this as a production knowledge authority.

The same questions become regression data after failures inform changes. No rerun is described as an untouched held-out score. Reports distinguish real OpenRouter calls, deterministic transport substitutes, and browser network fixtures.

The final release regression returned **12/12** on the original suite and **15/15** on automatic adversarial assertions. A separate Codex development agent inspected the actual final answers and retained **12/15** under the strict semantic standard; this is independent of the application's judge, **not a human ground-truth review**. See [the final inspection](evaluation-results/adversarial-release-manual-review.md) and [exact answer snapshots](evaluation-results/adversarial-release-answers.json). Its three open findings are imported into local quality history as a separate semantic-review suite. A passing daily canary cannot clear that amber warning.

## Ingestion and UI verification

Live reingestion processed **24 documents into 36 chunks**, preserving authors, attendees, dates, and all previous versions. **48 archived-original hashes** passed. Repeating ingestion returned **24 unchanged with zero provider calls**. See [the reingestion report](evaluation-results/adversarial-reingestion.json).

Two live browser workflows passed without network fixtures: answer → evidence → original download → correction → resolved review, and missing SLA → edited recipient/subject/body → simulated outbox → reload → original query. The driver verified exactly one feedback and one simulated send, preserved snapshots/notes, and found no JavaScript or console errors. Records are labeled `Adversarial UI rehearsal`; no email was delivered. See [the live UI report](evaluation-results/adversarial-live-ui.json). Desktop screenshots were visually inspected. The separate browser suite includes **28 passing Chromium scenarios**; it is not a formal accessibility audit.

## Reproduce and review

Run the backend and UI suites through `scripts/run.ps1 test` / `ui-test` on Windows or `scripts/run.sh test` / `ui-test` on Linux. See [evaluation commands](EVALUATION.md#reproduce-the-adversarial-live-audit) for isolated live audits, and [validation](VALIDATION.md) for final executed counts. A Windows symlink privilege skip is reported rather than counted as a pass; the Linux CI environment can exercise that case.

The user's ordered **[UI/CX review queue](UI_REVIEW_QUEUE.md)** has exact questions, actions, expected facts, failure criteria, keyboard/mobile/recovery checks, and an issue template. Start with its P0 flows. In particular, inspect whether each claim's selected passages, taken together, support **every clause**: visible source IDs and exact quotations alone do not establish semantic correctness.
