"""Bounded local uploads, immutable sample downloads, and retrieval-only search."""

import asyncio
import hashlib
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import time
import unicodedata

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import Field
from starlette.requests import ClientDisconnect

from .config import ROOT
from .extractors import ExtractionError, MAX_SOURCE_BYTES, SUPPORTED_EXTENSIONS
from .ingestion import ingest_file
from .models import Question
from .provider import ProviderError
from .retrieval import retrieve
from .source_safety import source_instruction_warnings
from .store import identifier


SAMPLES = [
    {"id": "juniper-kickoff", "title": "Juniper Harbor kickoff", "filename": "juniper_kickoff_brief.md",
     "description": "Add a new fictional engagement with an approved sandbox-review time, place, and coordinator.",
     "before_question": "When and where is Juniper Harbor's sandbox review, and who coordinates it?",
     "after_question": "When and where is Juniper Harbor's sandbox review, and who coordinates it?"},
    {"id": "juniper-escalation", "title": "Juniper Harbor escalation playbook", "filename": "juniper_escalation_playbook.md",
     "description": "Add the pilot's missing-answer escalation process and its accountable reviewer.",
     "before_question": "What is Juniper Harbor's process for a missing warranty-policy answer, including its owner and review cadence?",
     "after_question": "What is Juniper Harbor's process for a missing warranty-policy answer, including its owner and review cadence?"},
]


class SearchRequest(Question):
    limit: int = Field(default=10, ge=1, le=50)


def safe_filename(value: str) -> str:
    filename = unicodedata.normalize("NFC", value)
    if (not filename or len(filename.encode("utf-8")) > 200 or filename != filename.strip()
            or filename.endswith(".") or filename.startswith(".")
            or re.search(r'[\\/:*?"<>|]', filename)
            or any(unicodedata.category(character).startswith("C") for character in filename)
            or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", filename.split(".")[0], re.I)):
        raise HTTPException(422, "Use a plain filename without paths, control characters, or reserved device names (maximum 200 UTF-8 bytes).")
    if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise HTTPException(415, "Supported files: .md, .doc, .docx, .ppt, .pptx, .xls, and .xlsx.")
    return filename


def create_documents_router(settings, store, provider):
    router = APIRouter(prefix="/api")
    with store.connect() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS upload_leases (name_key TEXT PRIMARY KEY, token TEXT NOT NULL, expires_at REAL NOT NULL)")

    def acquire_lease(key, token):
        with store.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT expires_at FROM upload_leases WHERE name_key=?", (key,)).fetchone()
            if current and current[0] > time.time():
                raise HTTPException(409, "This filename is already being indexed. Wait for that upload to finish, then retry.")
            connection.execute("INSERT OR REPLACE INTO upload_leases VALUES(?,?,?)", (key, token, time.time() + settings.operation_timeout_seconds + 60))

    @router.get("/upload-samples")
    def upload_samples():
        return {"items": [{**sample, "download_url": f"/api/upload-samples/{sample['id']}/file"} for sample in SAMPLES]}

    @router.get("/upload-samples/{sample_id}/file")
    def sample_file(sample_id: str):
        sample = next((sample for sample in SAMPLES if sample["id"] == sample_id), None)
        if sample is None:
            raise HTTPException(404, "Upload sample not found.")
        directory = (ROOT / "data/upload_samples").resolve()
        path = directory / sample["filename"]
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(directory):
            raise HTTPException(404, "Upload sample file is unavailable.")
        return FileResponse(path, filename=sample["filename"], media_type="text/markdown", headers={"X-Content-Type-Options": "nosniff"})

    @router.post("/search")
    async def search(value: SearchRequest):
        if not settings.configured:
            raise ProviderError("Set OPENROUTER_API_KEY in the backend environment before searching documents.", category="configuration", status_code=503)
        try:
            async with asyncio.timeout(settings.operation_timeout_seconds):
                evidence = await retrieve(value.question, store=store, provider=provider, settings=settings.model_copy(update={"retrieval_limit": value.limit}))
        except TimeoutError:
            raise ProviderError("Document search exceeded its operation deadline. Retry the search.", category="timeout", status_code=503) from None
        return {"question": value.question, "evidence": [item.model_dump() for item in evidence], "count": len(evidence),
                "message": "Relevant source passages. Search does not generate or verify an answer." if evidence else "No matching source passages were found."}

    @router.post("/documents/upload")
    async def upload(request: Request, filename: str):
        filename = safe_filename(filename)
        if not settings.configured:
            raise ProviderError("Set OPENROUTER_API_KEY in the backend environment before uploading and indexing documents.", category="configuration", status_code=503)
        if request.headers.get("content-type", "").lower().startswith("multipart/"):
            raise HTTPException(415, "Send the file bytes directly with application/octet-stream and the filename query parameter.")
        uploads = store.data_dir / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        if uploads.is_symlink() or uploads.is_junction() or not uploads.resolve().is_relative_to(store.data_dir):
            raise HTTPException(503, "Upload storage is unavailable. Restore the local runtime uploads directory.")
        descriptor, temporary = tempfile.mkstemp(prefix="incoming-", suffix=".part", dir=uploads)
        stage = Path(temporary)
        key = hashlib.sha256(filename.casefold().encode("utf-8")).hexdigest()
        token, locked, committed = identifier(), False, False
        target = uploads / key / ("source" + Path(filename).suffix.lower())
        backup = stage.with_suffix(".backup")
        replaced = False
        try:
            total = 0
            with os.fdopen(descriptor, "wb") as stream:
                async for part in request.stream():
                    total += len(part)
                    if total > MAX_SOURCE_BYTES:
                        raise HTTPException(413, "Upload exceeds the 32 MiB file limit.")
                    stream.write(part)
            if not total:
                raise HTTPException(422, "The selected file is empty.")
            acquire_lease(key, token)
            locked = True
            target.parent.mkdir(exist_ok=True)
            if target.parent.is_symlink() or target.parent.is_junction() or not target.resolve().is_relative_to(uploads.resolve()):
                raise HTTPException(503, "Upload storage is unavailable. Restore the local runtime uploads directory.")
            with store.connect() as connection:
                current = connection.execute("SELECT * FROM documents WHERE source_path=? AND active=1", (str(target.resolve()),)).fetchone()
            if current:
                original = Path(current["original_path"])
                if (not original.is_file() or not original.resolve().is_relative_to(store.data_dir / "originals")
                        or hashlib.sha256(original.read_bytes()).hexdigest() != current["sha256"]):
                    raise HTTPException(503, "The previous source archive is unavailable or corrupt. Restore it before replacing this upload.")
                shutil.copyfile(original, backup)
            async with asyncio.timeout(settings.operation_timeout_seconds):
                os.replace(stage, target)
                replaced = True
                outcome = await ingest_file(target, store=store, provider=provider, settings=settings, original_filename=filename)
                committed = True
            with store.connect() as connection:
                chunks = connection.execute("SELECT text FROM chunks WHERE document_id=? ORDER BY rowid", (outcome["document_id"],)).fetchall()
            flagged = source_instruction_warnings("\n\n".join(row[0] for row in chunks))
            if flagged:
                outcome["warnings"] = [*outcome["warnings"], "Excluded from answers and search: " + "; ".join(flagged)]
            outcome["chunks"] = len(chunks)
            store.event("ingestion", outcome)
            return JSONResponse(outcome, status_code=201 if outcome["status"] == "ingested" else 200)
        except (ProviderError, ExtractionError, ValueError, TimeoutError, ClientDisconnect, OSError, sqlite3.Error) as error:
            if isinstance(error, ProviderError):
                message, category, status = str(error), error.category, error.status_code
            elif isinstance(error, TimeoutError):
                message, category, status = "Document indexing exceeded its operation deadline. Retry the upload.", "timeout", 503
            elif isinstance(error, ClientDisconnect):
                message, category, status = "The upload was interrupted before all file bytes arrived.", "upload", 400
            elif isinstance(error, (OSError, sqlite3.Error)):
                message, category, status = "Local document storage is unavailable. Check free disk space and retry the upload.", "storage", 503
            else:
                message, category, status = str(error), "extraction", 422
            message = message.replace(settings.openrouter_api_key.get_secret_value(), "[redacted]")[:1000]
            outcome = {"filename": filename, "status": "failed", "warnings": [], "error": message, "detail": message, "category": category}
            store.event("ingestion", outcome)
            return JSONResponse(outcome, status_code=status)
        finally:
            if replaced and not committed:
                if backup.is_file():
                    os.replace(backup, target)
                else:
                    target.unlink(missing_ok=True)
            stage.unlink(missing_ok=True)
            backup.unlink(missing_ok=True)
            if locked:
                with store.connect() as connection:
                    connection.execute("DELETE FROM upload_leases WHERE name_key=? AND token=?", (key, token))

    return router
