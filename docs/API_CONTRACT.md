# Shared implementation contract

All endpoints are same-origin under `/api`. Errors use `{detail: string}` with an appropriate non-2xx status. API credentials never leave the backend.

The local server accepts exact loopback Host names (`localhost`, `127.0.0.1`, `::1`); `ALLOWED_HOSTS` can configure an explicit JSON list. Browser mutations must originate from the same scheme, host, and port. CLI requests without an Origin header remain supported. API bodies are bounded to 64 KiB, including streamed requests, except the exact `POST /api/documents/upload` route, which streams at most 32 MiB. These controls do not add authentication or authorize public hosting.

## Queries

`POST /query` takes `{question: string}`. Its response is:

```typescript
type Evidence = {
  chunk_id: string; document_id: string; filename: string; title: string;
  author: string | null; attendees: string[]; date: string | null;
  domain: string; priority: string | null; locator: string; text: string;
};
type QueryResult = {
  query_id: string; question: string;
  status: 'answered' | 'partial' | 'needs_routing';
  claims: {text: string; citations: {chunk_id: string; quote: string}[]}[];
  evidence: Evidence[];
  routing: {recipient: string; reason: string; draft_question: string; evidence_ids: string[]}[];
  message: string; created_at: string;
};
```

`GET /query/{query_id}` returns the persisted response. `GET /sources/{document_id}` returns metadata and evidence chunks. `GET /sources/{document_id}/file` downloads the immutable original source version. `GET /sources` returns `{items: [...]}` with document summaries.

## Documents, uploads, and search

`GET /sources` returns active documents with `document_id`, `filename`, `created_at`, `sha256`, `chunk_count`, `version_count`, `origin: 'corpus'|'uploaded'`, and existing source/enrichment metadata: `title`, `author`, `attendees`, `date`, `domain`, `priority`, `decisions`, `action_items`, and `warnings`. Excluded-source warnings are visible. Paths on the server are never returned.

`GET /sources/{document_id}` returns stored source/enrichment metadata plus `active`, `chunks: Evidence[]`, and `versions: {document_id, filename, sha256, active, created_at}[]`, newest first. Count the returned chunks for the detail view; `chunk_count` is a list-summary field. Detail warnings are the stored ingestion warnings; the active list also adds current source-quarantine notices. Any retained version ID can be inspected or downloaded. Changing a source does not rewrite earlier query snapshots.

`POST /documents/upload?filename=example.md` accepts **raw file bytes** with `Content-Type: application/octet-stream`, one file per request. It supports `.md`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, and `.xlsx`; legacy formats require LibreOffice. Filenames must be plain names, at most 200 UTF-8 bytes, without path separators, control characters, hidden-file prefixes, Windows reserved device names, or trailing dots/spaces. The body is streamed to temporary local storage and rejected after 32 MiB even without a Content-Length. The normal 64 KiB API limit and Host/Origin controls remain enforced elsewhere.

Successful response: `{filename, status: 'ingested'|'unchanged', document_id, chunks, warnings: string[]}`; HTTP 201 for ingestion and 200 for unchanged content. Indexing failures return `{filename, status:'failed', warnings:[], error, detail, category}` with an appropriate non-2xx status; filename/body/request validation errors use `{detail}`. Concurrent uploads of the same normalized, case-insensitive filename return HTTP 409. Identical bytes under that filename remain unchanged when enrichment/embedding configuration is unchanged; changed bytes or effective model options create a version. A differently named file is a separate attributed source.

Uploads live under `.runtime/uploads`, separately from the 24-document seed corpus. Replacement is atomic and guarded by a database lease across app instances. Failed indexing restores the previous successful uploaded bytes and active version; archived originals and saved answers remain intact. Uploading never invokes directory synchronization, retires seed documents, resets the workspace, or sends email. A source excluded for AI-targeted instructions remains inspectable but is omitted from search/answers.

`GET /upload-samples` returns exactly two cards: `{items: [{id,title,filename,description,before_question,after_question,download_url}]}`. `GET /upload-samples/{id}/file` downloads only the corresponding known committed file. The files are outside `data/corpus`, introduce a fourth fictional engagement, and are never automatically ingested. See [upload practice](UPLOAD_SAMPLES.md).

`POST /search` takes `{question: string, limit?: number}`. The question follows the query API's 3–3000 character validation; `limit` is an integer from 1 to 50, default 10. Response: `{question, evidence: Evidence[], count, message}`. It performs hybrid retrieval, preserves metadata and source locations, and applies source quarantine. It does **not** generate claims, call an answer model, persist a query/history snapshot, create gaps/corrections, or populate the outbox. Embedding/cache/provider operational events may be recorded. Missing credentials, unavailable providers, or invalid stored embeddings are operational errors, not knowledge gaps.

Example from the repository root:

```bash
curl -X POST 'http://127.0.0.1:8000/api/documents/upload?filename=juniper_kickoff_brief.md' \
  -H 'Content-Type: application/octet-stream' --data-binary @data/upload_samples/juniper_kickoff_brief.md
curl -X POST http://127.0.0.1:8000/api/search -H 'Content-Type: application/json' \
  -d '{"question":"When is Juniper Harbor sandbox review?","limit":5}'
```

Equivalent Windows PowerShell commands avoid native-command JSON quoting and send UTF-8 explicitly:

```powershell
$apiBase = 'http://127.0.0.1:8000'
Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$apiBase/api/documents/upload?filename=juniper_kickoff_brief.md" -ContentType 'application/octet-stream' -InFile '.\data\upload_samples\juniper_kickoff_brief.md'
$searchBody = @{ question = 'When is Juniper Harbor sandbox review?'; limit = 5 } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "$apiBase/api/search" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($searchBody))
```

Credentials remain exclusively in the backend environment.

## Feedback and review

`POST /feedback` takes `{query_id, kind: 'accepted'|'rejected'|'corrected', comment: string}` and returns `{id}`. Rejections/corrections require a nonempty comment.

`GET /review` returns `{items: ReviewItem[]}`. Each item has `id`, `kind` (`gap`, `rejected`, or `corrected`), `query_id`, `question`, `answer` (full QueryResult), `comment`, `status` (`open` or `resolved`), `created_at`, and `resolution_note`.

`PATCH /review/{id}` takes `{status: 'open'|'resolved', resolution_note: string}`. `GET /gaps`, `GET /feedback`, and `GET /corrections` expose the corresponding records.

## Outbox

`POST /outbox` takes `{query_id, recipient, subject, body, evidence_ids: string[]}`. Returns a stored item with `id`, these same fields, `status: 'simulated'`, and `created_at`. `GET /outbox` returns `{items: [...]}`. This never sends real email.

## Status

`GET /health` returns `{configured: boolean, ready: boolean, document_count: number, chunk_count: number, model: string, review_model: string, warnings: string[]}`. Missing credentials or an empty corpus make `ready` false.

`GET /quality` returns `{latest: object|null, alerts: string[], open_finding_count: number|null, suites: [...]}`. `open_finding_count` counts failed case instances in the latest report per dataset/suite, not alert messages. Each suite includes `dataset`, `suite`, `created_at`, `case_count`, `passed`, `failed_cases`, `alerts`, `model`, and `review_model`. Existing latest/alerts fields remain compatible. `GET /metrics` returns operational counters and rejection/correction rate. Health remains callable when credentials are absent.

Health warnings name sources excluded because their content attempts to control the answering model. The originals remain downloadable for inspection. A corpus containing only excluded sources is not ready and queries return an operational error rather than creating a knowledge gap. Partial/abstaining response messages identify missing requested components when available. Quality alerts retain unresolved failures from other datasets/suites after a passing run; historical reports remain stored. Scheduled evaluation runs the entire configured dataset daily, while explicit CLI canaries are labeled separately. Automated monitoring does not replace independent semantic review.

Provider errors return safe, actionable messages without creating a knowledge gap. HTTP402 is classified using OpenRouter's documented metadata: temporary in-flight capacity retries at most three attempts, honoring a bounded Retry-After delay; key-allowance and single-request budget failures do not retry. An unclassified402 asks the user to check funding/allowances and settlement without asserting an empty balance. All waits remain cancellable within the operation deadline, and only whitelisted classification values enter provider telemetry.

## Extractor boundary

`backend/app/extractors.py` exposes `extract_document(path: Path, *, soffice_path: str|None = None) -> ExtractedDocument`. Dataclasses: `ExtractedChunk(text: str, locator: str)` and `ExtractedDocument(title: str, author: str|None, attendees: list[str], date: str|None, chunks: list[ExtractedChunk], warnings: list[str])`. Extraction is deterministic; enrichment is separate. Exceptions must explain the file failure. Only `.md`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx` are supported. Source filename/path/hash are assigned by ingestion. No fallback mock metadata or fabricated attribution.
