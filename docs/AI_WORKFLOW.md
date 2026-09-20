# AI development record

## Primary tool and starting point

Codex was the primary coding assistant in the user's local IDE/workspace workflow. The workspace began with only the three-page take-home PDF. The project was designed and implemented from that empty starting point rather than copied from another application. No web chat was used as the primary development interface.

## User decisions

- Python/FastAPI and React/TypeScript.
- Live OpenRouter access, with credentials in a server-side environment variable.
- A fictional AI-deployment consulting firm serving its internal delivery team.
- A knowledge workspace with Ask, Review Queue, and Outbox views.
- An explicitly simulated local outbox instead of real email delivery.
- Repository-first delivery; a Cloudflare demo tunnel remains outside the implementation.

## Development process

1. Extracted and independently reviewed every page of the exercise brief.
2. Checked the empty workspace and available runtimes before selecting implementation details.
3. Confirmed OpenRouter structured-output and embeddings capabilities and LibreOffice's genuine legacy conversion filters against official documentation.
4. Agreed the plan with the user, including all six Office formats and per-claim evidence.
5. Established `docs/API_CONTRACT.md` before parallel implementation. Delegated the backend, frontend, and synthetic corpus/extractors to separate Codex agents with explicit file ownership.
6. Integrated locally, reviewed failure handling and grounding boundaries, ran automated checks, and inspected the interface and generated document renders.
7. Ran actual OpenRouter connectivity, full-corpus ingestion, and the evaluation suite after the user configured `OPENROUTER_API_KEY`. Used the first run's failures to improve general grounding and answerability handling, and retained those initial results in the validation record.
8. Created the public repository through the user's authenticated GitHub browser session and prepared exact-byte publication through the connected GitHub tools.
9. Retained failed live evaluations rather than changing labels. Replaced model-copied quotations with backend-resolved source span IDs, separated answer-blind coverage from claim verification, and selected a separately configurable GPT-4.1 reviewer after direct comparisons exposed anchoring and scope errors with the original pipeline. The independent audit's original 4/6 score remains visible alongside its corrected 6/6 regression rerun.
10. At the user's explicit request to re-read the brief and conduct serious adversarial testing, independently re-extracted all three PDF pages and delegated separate backend/provider, ingestion/provenance, and UI investigations. Root ownership covered retrieval, claim verification, evaluation, integration, and final reporting. New tests reproduced faults before fixes where practical; parameterized protocol corruption cases exercise actual trust boundaries rather than restating implementations.
11. Froze 15 new live questions and a separate malicious-source fixture, tested them in SQLite backups, and asked an independent agent to review actual claims and citations. The first 15/15 automatic score became 13/15 under that semantic review. A malicious source successfully produced an invented answer accepted by the model verifier. Those findings led to document quarantine before question-time inference, narrower citation checking, explicit answer-completeness checking, and visible missing-component messages. Failed and intermediate runs remain in the repository record.
12. Preserved this turn's development artifacts: `data/evaluation_adversarial.json`, `data/evaluation_injection.json`, the hostile test fixture, source-screening rules, new adversarial tests, reusable live-audit/reingestion scripts, semantic-review reports, and the user's hands-on UI/CX queue. Credentials were accessed only from the backend environment; no key was copied into prompts, fixtures, screenshots, or the repository.
13. Published the exact tested Git tree and inspected Linux CI, which exposed three legacy PowerPoint attribution failures absent on Windows. Reproduced LibreOffice's generic-title/missing-author boundary, recovered visibly marked leading titles, and restricted attribution to the first slide without notes. The focused 24-document and adversarial ingestion suite passed on Windows; the fix was resubmitted for Linux verification. Preserved the failed CI link in the validation record.

## Reusable instructions and prompts

`AGENTS.md` contains project rules. The extraction/enrichment, answer, and evidence-review prompts are committed beside their implementation in the backend. `scripts/generate_corpus.py` contains the synthetic organization/document specifications rather than relying on private notes. Test questions and expected sources are committed in `data/evaluation.json`.

The bundled PDF, document, presentation, and spreadsheet guidance used during development is copied in full under `.agents/skills`. These are provenance snapshots and design/QA guidance, not application dependencies. The user's explicit plan for reproducible Python corpus generators takes precedence over bundled guidance that assumes a hosted artifact runtime. There are no symlinks to a personal skills directory. Normally installed Python, Node, and LibreOffice are ordinary prerequisites, not hidden workspace artifacts.

## Review focus

Human-readable code and tests are the submission, not a claim that AI output was automatically correct. Review focused on exact attribution, stale/contradictory evidence, malformed/provider error responses, fabricated or empty citations, source-version retention, query/feedback persistence, and honest distinction between mocked tests and live model evaluation. See `docs/VALIDATION.md` for actual outcomes.

## External technical references

- [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
- [OpenRouter embeddings API](https://openrouter.ai/docs/api/api-reference/embeddings/create-embeddings)
- [OpenRouter error handling](https://openrouter.ai/docs/api_reference/errors-and-debugging)
- [LibreOffice conversion filters](https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html)
- [LibreOffice command-line options](https://help.libreoffice.org/latest/en-US/text/shared/guide/start_parameters.html)

External documentation explains public dependencies. No private project, external prompt, or outside file is required to reproduce the application.
