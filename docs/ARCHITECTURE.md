# Architecture and decisions

```mermaid
flowchart LR
  A[Committed synthetic corpus] --> B[Extract text and source locations]
  W[Documents upload] --> B
  B --> C[Shared OpenRouter enrichment]
  C --> D[(SQLite versions, chunks and vectors)]
  Q[Question in React or API] --> R[FTS5 plus semantic retrieval]
  D --> R
  R --> P[Assess requested information without a proposed answer]
  P --> G[Structured cited claims]
  P --> H[Gap and evidence-based handoff]
  G --> V[Validate citations and check support]
  V --> U[Claims and source dialogs]
  V --> H[Gap and evidence-based handoff]
  U --> F[Feedback and review queue]
  H --> O[Editable simulated outbox]
  E[Release checks and daily full suite] --> R
  E --> M[Persisted quality results and alerts]
```

## Ingestion and provenance

Deterministic extractors preserve author/attendee and date metadata before any model call. Word extraction follows paragraphs and tables in document order. Presentations preserve slide, shape, table, and notes locations. Workbooks retain sheet names and cell ranges, include header context, and identify formulas whose cached results are unavailable. The service does not calculate a missing result.

Legacy Office files are converted in a temporary directory with a separate LibreOffice user profile, a deadline, and output verification. Originals remain unchanged and are archived by document version. Word locators after conversion identify normalized structural positions, not original page numbers.

Ingestion supports both the folder CLI and the Documents screen. Browser uploads stream one raw file per request with a 32 MiB bound, validated filenames, isolated storage, and a cross-process filename lease. Replacements publish only after successful extraction, enrichment, and persistence; failures restore the prior uploaded original. Uploaded files remain separate from identically named seed documents. Processing reports per-file outcomes and unchanged duplicates. The same enrichment prompt applies to all formats. Source identities never come from the model.

SQLite stores active and historical document versions, location-bearing chunks, cached embeddings, query snapshots, feedback, review items, outbox entries, operational events, and evaluations. Source content hashes and a processing-profile fingerprint determine whether ingestion can be skipped. A new active version does not rewrite previous answers. Archived originals make old citation downloads work even when the source folder changes.

Extraction operates on a byte snapshot, so the text and archived hash cannot diverge if a source changes during processing. Publishing uses a serialized compare-and-replace: a slower stale ingestion cannot overwrite a newer version. Author/date headers are read only from the leading metadata region; an `Author:` string in body text is not promoted to attribution. Explicit folder ingestion retires missing paths after successful discovery, preserving historical rows. Linked directories are not followed. Extraction limits are 32 MiB per source, 64 MiB expanded OOXML, 10,000 archive parts, and 200,000 declared spreadsheet cells.

## Retrieval and grounded answers

SQLite FTS5 lexical ranking and exact cosine similarity over cached vectors are merged using reciprocal-rank fusion. Exact vector search is sufficient for this 24-document dataset and removes a separate vector-service dependency. Queries use the same configured embedding model and dimensions as the corpus; a changed model requires re-ingestion.

Developer tools exposes retrieval-only `POST /api/search` and the complete `POST /api/query` pipeline, showing their actual JSON responses and shell-safe reproduction commands. Search can populate embedding cache and operational metrics, but does not create answer snapshots, user history, knowledge gaps, or feedback.

Before ranking, the application screens all active chunks of every document for recognizable AI control instructions, role impersonation, and verifier manipulation. Any flagged document is excluded as a whole from question-time model context, citations, and routing, with a visible health warning; its original remains inspectable. This boundary was added after a live source attack fooled both generator and reviewer. Unicode/HTML normalization catches simple obfuscations, but unflagged content is not proven trustworthy. Convincing fabricated business facts and unseen attacks remain a limitation, and legitimate documents discussing prompt syntax may need review. Invalid cached vectors are rebuilt; invalid stored vectors produce an operational error, not an apparent knowledge gap. Scaled cosine avoids floating-point overflow and underflow.

Before generation, an answer-blind assessment decomposes the question and checks the evidence for each requested component. This prevents a fluent proposed answer from anchoring the coverage judgment. The backend derives answer status from those components: a correctly quoted statement that a requested value is unknown does not become an answered question.

The generation request includes only retrieved passages with stable chunk IDs and trusted attribution metadata. Each immutable chunk receives a deterministic catalog of contiguous source spans. The model returns schema-constrained claims selecting chunk and span IDs; the backend rejects invented IDs and resolves quotations directly from stored source text. This avoids asking the model to reproduce exact quotations. A separate model call reviews whether each claim's selected passages, taken together, support every clause and whether requested information is omitted. It receives each claim's cited context, without a pool of uncited coverage values. One bounded repair can correct a rejected or incomplete draft; remaining failed claims are omitted. Incomplete evidence or unresolved contradictions produces partial/abstaining output. A false-positive verifier judgment remains a limitation documented by the adversarial review.

Generation, enrichment, coverage, and support review default to GPT-6 Astra after the accuracy-first comparison. Generation and review remain separately configurable and use distinct requests; coverage never sees the proposed answer. The initial full comparison scored Astra 43/45, the Luna/Astra hybrid 41/45, and Luna 39/45 under independent semantic inspection. [Model selection](MODEL_SELECTION.md) records subsequent fixes, final validation, costs, and limitations. The application's reviewer is not independent ground truth. Frozen evaluation cases and visible source evidence provide additional checks, and the service uses categorical answer states rather than an uncalibrated confidence percentage.

For spreadsheet citations, the backend can supplement a selected row with exact preceding source rows, including headers and intervening notes. This requires a unique, contiguous mapping from a multi-column first row through the selected row within the same immutable document version and sheet, capped at 20 rows. Missing or ambiguous ranges add nothing. The support reviewer receives this complete selected context; the resolver never guesses which of several stacked tables owns a header or fabricates a combined quotation.

The resolver also supplies an exact source-title quotation when a relevant Markdown or presentation chunk proves its location at the original first line or first shape. The title must match stored provenance, be a whole single-line passage of at most 300 characters, and have a unique native start within the same immutable document version. This preserves framing such as a tabletop rehearsal in each claim's own evidence before support review. It does not synthesize a quotation from metadata or treat a title as proof of every claim. Word paragraph numbering excludes preceding tables, and workbook locators lack sheet order, so those formats receive no automatic title quotation; explicit source-span citations remain available.

Routing recipients are constructed from the relevant source authors and attendees. Deterministic ranking favors explicit named responsibility and question-relevant body passages over document frequency. Each suggestion includes matching source content and evidence IDs; document metadata headers do not substitute for a supporting excerpt. Unrelated queries cannot invent an expert; the user can choose a recipient manually. Editing a recipient is a user action, preserved with the originating query rather than represented as a sourced assertion.

## Feedback and operational behavior

The review queue contains both automatic knowledge gaps and explicit user rejections/corrections. Items retain the original query and answer snapshot. Resolving a review item requires a note and never automatically promotes a correction into authoritative source content.

The outbox persists recipient, subject, body, query, and evidence references. Its status is always `simulated`. No connector, SMTP integration, or real delivery is hidden behind that button.

OpenRouter calls use a shared HTTPX client, bounded retries for transient failures, strict local response validation, and an overall operation deadline. Provider credentials, account-credit failures, unavailable models, and conversion failures remain operational errors rather than knowledge gaps. Provider telemetry stores operational metadata without keys or raw HTTP responses. Validated coverage assessments are retained separately as local SQLite events linked by query ID, so developers can inspect why a response abstained or appeared complete.

FastAPI serves the built React assets and API from one origin. The default host is `127.0.0.1`. Authentication, multi-tenant permissions, real email, OCR, a background worker system, and public hosting are intentionally outside this local evaluation build.

## Configuration

| Variable | Default or purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | Required server-side credential |
| `OPENROUTER_MODEL` | `openai/gpt-6-astra` |
| `OPENROUTER_REVIEW_MODEL` | `openai/gpt-6-astra`; answer-blind coverage and claim verification |
| `OPENROUTER_MODEL_OPTIONS` | JSON keyed by exact model ID; Astra defaults to high reasoning, 8,000 output tokens, omitted temperature, and excluded `openai/flex` route |
| `OPENROUTER_EMBEDDING_MODEL` | `openai/text-embedding-3-small` |
| `SOFFICE_PATH` | Optional explicit LibreOffice executable |
| `DATA_DIR` | `.runtime`, containing the local database and immutable originals |
| `CORPUS_DIR` | `data/corpus` |
| `EVALUATION_PATH` | `data/model_evaluation_gold.json`; all 45 cases by default |
| `DAILY_EVALUATION` | `true`; set `false` to disable the daily live full-suite run |
| `PROVIDER_TIMEOUT_SECONDS` | `120` per provider request |
| `OPERATION_TIMEOUT_SECONDS` | `360` overall, including retries and support repair |
| `OPENROUTER_API_KEY_ENV` | Optional alternate key-variable name mapped by the startup scripts |

The checked-in `.env.example` has no secrets. Environment variables take precedence over `.env` configuration. Runtime artifacts are excluded from the submission.

Model settings are validated independently for each exact model ID. A null temperature omits that parameter for models that do not support it; explicit reasoning effort and output-token limits bound reasoning-model work. Provider routing continues to require the requested structured-output parameters. A pinned provider can disable fallbacks for reproducible comparisons. Operational telemetry records validated numeric token counts and provider-reported cost when present; a missing cost is not recorded as zero. The model comparison records actual settings and provider compatibility rather than assuming every model accepts the same request parameters.
