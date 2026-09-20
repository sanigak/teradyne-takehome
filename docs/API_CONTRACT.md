# Shared implementation contract

All endpoints are same-origin under `/api`. Errors use `{detail: string}` with an appropriate non-2xx status. API credentials never leave the backend.

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

## Feedback and review

`POST /feedback` takes `{query_id, kind: 'accepted'|'rejected'|'corrected', comment: string}` and returns `{id}`. Rejections/corrections require a nonempty comment.

`GET /review` returns `{items: ReviewItem[]}`. Each item has `id`, `kind` (`gap`, `rejected`, or `corrected`), `query_id`, `question`, `answer` (full QueryResult), `comment`, `status` (`open` or `resolved`), `created_at`, and `resolution_note`.

`PATCH /review/{id}` takes `{status: 'open'|'resolved', resolution_note: string}`. `GET /gaps`, `GET /feedback`, and `GET /corrections` expose the corresponding records.

## Outbox

`POST /outbox` takes `{query_id, recipient, subject, body, evidence_ids: string[]}`. Returns a stored item with `id`, these same fields, `status: 'simulated'`, and `created_at`. `GET /outbox` returns `{items: [...]}`. This never sends real email.

## Status

`GET /health` returns `{configured: boolean, ready: boolean, document_count: number, chunk_count: number, model: string, review_model: string, warnings: string[]}`. Missing credentials or an empty corpus make `ready` false.

`GET /quality` returns `{latest: object|null, alerts: string[]}`. `GET /metrics` returns operational counters and rejection/correction rate. Health remains callable when credentials are absent.

## Extractor boundary

`backend/app/extractors.py` exposes `extract_document(path: Path, *, soffice_path: str|None = None) -> ExtractedDocument`. Dataclasses: `ExtractedChunk(text: str, locator: str)` and `ExtractedDocument(title: str, author: str|None, attendees: list[str], date: str|None, chunks: list[ExtractedChunk], warnings: list[str])`. Extraction is deterministic; enrichment is separate. Exceptions must explain the file failure. Only `.md`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx` are supported. Source filename/path/hash are assigned by ingestion. No fallback mock metadata or fabricated attribution.
