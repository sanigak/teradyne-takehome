# Validation record

Validation took place on Windows with Python 3.14.7, Node.js 24.19.0, and LibreOffice 26.8.0.3. Tool installations, rendered QA pages, runtime data, and test artifacts are excluded from Git.

## Subsequent adversarial audit

The later audit supersedes the earlier test counts below: **314 Python tests passed, 1 skipped** in 145.71 seconds; **28 Chromium browser tests passed** and the production TypeScript/Vite build passed. The Windows skip requires symlink creation privileges and is not counted as a pass. All real Office formats were exercised with LibreOffice. The complete [adversarial record](ADVERSARIAL_TESTING.md) identifies reproduced defects, fixes, and remaining semantic failures.

Final automatic live results were **12/12** for the original regression set, **6/6** for the earlier audit set, **15/15** for the new adversarial set, and **2/2** for the malicious-source rerun. The 6-case and injection runs preceded the final bounded-support-repair addition; the 12- and 15-case runs exercised it. The independent Codex agent's inspection of the final 15 answers was **12/15**, with three open citation/scope findings. These are not independently human-labeled accuracy results. The support-reviewer control experiment also retained false positives. The semantic report is persisted in `/api/quality` and produces a visible amber quality badge; passing automated checks do not clear it.

Both real UI flows passed without fixtures, including the original-file download, correction/resolution, edited simulated send, reload persistence, and unchanged snapshots. Live reingestion preserved all 24 source identities, 36 chunks, and 48 archived versions; repeating it required zero provider calls. Refer to [the review queue](UI_REVIEW_QUEUE.md) for the user's separate hands-on checks.

## Completed

- Python runtime dependencies installed from the checked-in requirements and the application installed as an editable package.
- All 24 generated source files verified against manifest hashes and source attribution; six legacy files verified as genuine Office compound binaries.
- Extraction checks passed for all seven file extensions, missing metadata, ordered Word tables, grouped slide shapes and notes, formula-cache warnings, malformed files, and legacy conversion failures.
- Final full Python suite: **109 tests passed** with real LibreOffice, including all 24 files ingested through the service, archived-original hash/download checks, idempotent re-ingestion, version history, provider failures, feedback, and quality regression behavior. The earlier 94-test version also passed in a fresh local Git clone.
- React strict TypeScript check and production build passed. npm audit reported zero known vulnerabilities for the locked dependency tree.
- **7 browser workflows passed**: citations/correction/review resolution, routing/outbox, provider errors, mobile layout, missing credentials, unrelated-question abstention, and attendee attribution fallback.
- Desktop and mobile interface screenshots inspected. All 12 Office documents inspected across 28 rendered pages; four Word documents were rerendered after a title-format correction.
- Same-origin FastAPI startup verified: React HTML and API health, quality, metrics, sources, review, and outbox are reachable. Unknown API routes return 404. A question without configured credentials returns an actionable 503 and does not create a knowledge gap.
- Fresh-clone Windows setup created a new virtual environment, installed locked dependencies, built React, and started the application successfully. Transcript generation now writes canonical LF bytes, and all 24 Git-staged source hashes match the manifest. This prevents Windows newline conversion from breaking cloned corpus verification.
- The Windows browser-test wrapper rebuilt the production assets and passed all seven Playwright tests. Documentation links and staged files were checked; credentials, downloaded tools, runtime data, environments, and caches are excluded. Linux reproduction runs in the public [Checks workflow](https://github.com/sanigak/teradyne-takehome/actions/workflows/checks.yml); consult the linked run for its current outcome.

## Live validation

- The explicitly invoked OpenRouter smoke test passed with `openai/gpt-4.1-mini` structured output and `openai/text-embedding-3-small` embeddings with 1,536 dimensions.
- Live ingestion processed all 24 documents successfully into 36 chunks. Re-ingestion reported all 24 unchanged, with no repeated model calls. Conversion and formula-cache notices remain visible through the health endpoint.
- Browser validation against the real running service completed both requested paths: ask, inspect attributed evidence, submit a correction, and resolve the preserved review snapshot; then ask about missing information, select a source-backed recipient, edit all draft fields, and verify the persisted simulated outbox. Validation records are clearly labeled in the ignored local database. No email was delivered.
- The initial 12-case live evaluation passed 8 cases, with 100% valid citations among returned claims. Failures exposed incomplete gap classification, an omitted conflict owner, and a response that exhausted exact-quotation repair. These results triggered implementation fixes; they are not represented as a passing release evaluation.
- Final live regression evaluation: **12/12 passed**. An independent six-case audit initially passed **4/6**, exposing answer-anchored judgment and scope confusion. After separating answer-blind coverage and using GPT-4.1 for review, its regression rerun passed **6/6**. Both final suites reported 100% expected-source recall, expected-fact coverage, citation validity, and abstention accuracy. All initial, interrupted, and final outcomes are retained in [evaluation results](evaluation-results/README.md); these small synthetic results are not a production accuracy estimate.
- Final live HTTP smoke passed against the running FastAPI service, including cited answers, persisted snapshots, source details, and review/outbox/metrics/quality endpoints. The service is configured with 24 documents, 36 chunks, and daily evaluation enabled. The unrelated audit question returned no claims, evidence, or invented recipient; the missing vendor SLA correctly routed first to the explicitly named contract owner.
- Created the public [GitHub repository](https://github.com/sanigak/teradyne-takehome) using the user's authenticated Edge session. Publication uses the connected GitHub tools and compares the complete remote Git tree with the local submission tree. An exact-value credential scan passed across submission files; credentials and local runtime artifacts are excluded.

Test fixtures are isolated to automated tests. The shipped application has no mock-answer or credential-free AI mode. Credentials and raw runtime records remain outside Git.
