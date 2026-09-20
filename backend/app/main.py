import asyncio
import json
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .evaluation import daily_evaluation_loop, quality
from .models import Feedback, OutboxDraft, Question, QueryResult, ReviewUpdate
from .provider import OpenRouter, ProviderError
from .retrieval import evidence_from_row
from .service import KnowledgeService
from .store import Store, encode, identifier, now


def create_app(settings: Settings | None = None, *, provider=None):
    settings = settings or Settings()
    store = Store(settings.data_dir)
    provider = provider or OpenRouter(settings, store)
    service = KnowledgeService(settings, store, provider)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(daily_evaluation_loop(service)) if settings.daily_evaluation else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        await provider.close()

    app = FastAPI(title="AI Consulting Knowledge Workspace", version="0.1.0", lifespan=lifespan)
    app.state.store, app.state.service, app.state.settings = store, service, settings

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": "; ".join(error["msg"] for error in exc.errors()[:3])})

    @app.get("/api/health")
    def health():
        docs, chunks = store.counts()
        warnings = []
        if not settings.configured:
            warnings.append("Set OPENROUTER_API_KEY in the server environment or project-root .env and restart the service.")
        if not docs:
            warnings.append("No documents are ingested. Run python -m app ingest.")
        with store.connect() as conn:
            rows = conn.execute("SELECT filename,metadata FROM documents WHERE active=1").fetchall()
            models = {row[0] for row in conn.execute("SELECT DISTINCT c.embedding_model FROM chunks c JOIN documents d ON c.document_id=d.id WHERE d.active=1")}
            outcomes = conn.execute("SELECT payload FROM events WHERE kind='ingestion' ORDER BY id DESC LIMIT 100").fetchall()
        for row in rows:
            warnings.extend(f"{row['filename']}: {warning}" for warning in json.loads(row["metadata"])["warnings"])
        seen = set()
        for row in outcomes:
            outcome = json.loads(row[0])
            if outcome["filename"] not in seen:
                if outcome["status"] == "failed":
                    warnings.append(f"{outcome['filename']}: {outcome['error']}")
                seen.add(outcome["filename"])
        model_matches = (not models or models == {settings.openrouter_embedding_model}) and all(json.loads(row["metadata"]).get("embedding_dimensions") == settings.openrouter_embedding_dimensions for row in rows)
        if not model_matches:
            warnings.append("Embedding model or dimensions changed; run python -m app ingest again.")
        return {"configured": settings.configured, "ready": settings.configured and docs > 0 and model_matches,
                "document_count": docs, "chunk_count": chunks, "model": settings.openrouter_model,
                "review_model": settings.openrouter_review_model, "warnings": warnings}

    @app.post("/api/query", response_model=QueryResult)
    async def query(value: Question):
        return await service.query(value.question)

    @app.get("/api/query/{query_id}", response_model=QueryResult)
    def get_query(query_id: str):
        result = store.get_query(query_id)
        if result is None:
            raise HTTPException(404, "Query not found.")
        return result

    @app.get("/api/sources")
    def sources():
        with store.connect() as conn:
            rows = conn.execute("SELECT d.*,count(c.id) AS chunk_count FROM documents d LEFT JOIN chunks c ON c.document_id=d.id WHERE d.active=1 GROUP BY d.id ORDER BY d.filename").fetchall()
        return {"items": [{"document_id": row["id"], "filename": row["filename"], "created_at": row["created_at"], "chunk_count": row["chunk_count"], **json.loads(row["metadata"])} for row in rows]}

    def source_row(document_id):
        with store.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Source version not found.")
        return row

    @app.get("/api/sources/{document_id}")
    def source(document_id: str):
        row = source_row(document_id)
        with store.connect() as conn:
            chunks = conn.execute("SELECT c.*,d.filename,d.metadata FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.document_id=? ORDER BY c.rowid", (document_id,)).fetchall()
        return {"document_id": document_id, "filename": row["filename"], "active": bool(row["active"]),
                "sha256": row["sha256"], "created_at": row["created_at"], **json.loads(row["metadata"]),
                "chunks": [evidence_from_row(chunk).model_dump() for chunk in chunks]}

    @app.get("/api/sources/{document_id}/file")
    def source_file(document_id: str):
        row = source_row(document_id)
        path = Path(row["original_path"]).resolve()
        if not path.is_relative_to(store.data_dir / "originals") or not path.is_file():
            raise HTTPException(404, "The stored source file is unavailable; restore the runtime original-file archive.")
        return FileResponse(path, filename=row["filename"], headers={"X-Content-Type-Options": "nosniff"})

    @app.post("/api/feedback", status_code=201)
    def feedback(value: Feedback):
        try:
            return store.feedback(value.model_dump())
        except KeyError:
            raise HTTPException(404, "Query not found.") from None

    @app.get("/api/feedback")
    def get_feedback():
        with store.connect() as conn:
            rows = conn.execute("SELECT * FROM feedback ORDER BY created_at DESC").fetchall()
        return {"items": [dict(row) for row in rows]}

    @app.get("/api/review")
    def review():
        return store.reviews()

    @app.get("/api/gaps")
    def gaps():
        return store.reviews("gap")

    @app.get("/api/corrections")
    def corrections():
        return store.reviews("corrected")

    @app.patch("/api/review/{review_id}")
    def update_review(review_id: str, value: ReviewUpdate):
        with store.connect() as conn:
            cursor = conn.execute("UPDATE review SET status=?,resolution_note=? WHERE id=?", (value.status, value.resolution_note.strip(), review_id))
            if cursor.rowcount != 1:
                raise HTTPException(404, "Review item not found.")
        return next(item for item in store.reviews()["items"] if item["id"] == review_id)

    @app.post("/api/outbox", status_code=201)
    def create_outbox(value: OutboxDraft):
        answer = store.get_query(value.query_id)
        if not answer:
            raise HTTPException(404, "Query not found.")
        allowed = {item["chunk_id"] for item in answer["evidence"]}
        if not set(value.evidence_ids).issubset(allowed):
            raise HTTPException(422, "Outbox evidence must belong to the originating query.")
        record = {"id": identifier(), **value.model_dump(), "status": "simulated", "created_at": now()}
        with store.connect() as conn:
            conn.execute("INSERT INTO outbox VALUES(?,?,?)", (record["id"], encode(record), record["created_at"]))
        return record

    @app.get("/api/outbox")
    def outbox():
        with store.connect() as conn:
            rows = conn.execute("SELECT payload FROM outbox ORDER BY created_at DESC").fetchall()
        return {"items": [json.loads(row[0]) for row in rows]}

    @app.get("/api/quality")
    def get_quality():
        return quality(store)

    @app.get("/api/metrics")
    def metrics():
        return store.metrics()

    @app.api_route("/api/{unknown:path}", methods=["GET", "POST", "PATCH", "DELETE", "PUT"])
    def unknown_api(unknown: str):
        raise HTTPException(404, "API endpoint not found.")

    if settings.frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    else:
        @app.get("/")
        def missing_frontend():
            return JSONResponse({"detail": "Build the interface with npm ci && npm run build in frontend, then restart. API documentation is at /docs."}, status_code=503)
    return app


app = create_app()
