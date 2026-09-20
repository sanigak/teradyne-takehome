"""Explicit final validation sharing the benchmark's USD40 spend history and lock.

From the configured environment on Windows or Linux:
    python -m scripts.revision_live smoke
    python -m scripts.revision_live ingest
    python -m scripts.revision_live serve

Serve binds only 127.0.0.1:8011, clones canonical sources, and never schedules
evaluations. Every provider attempt remains metered until the server stops.
Stop the normal workspace server before auditing its main ingestion database.
"""
import argparse
import asyncio
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings
from app.ingestion import ENRICH_PROMPT, SUPPORTED, ingest_directory
from app.models import Enrichment
from app.provider import ProviderError
from app.store import Store, now
from scripts.model_benchmark import BudgetExceeded, BudgetLedger, BenchmarkRouter, MeteredTransport, PRICE_CAPS, sha

BENCHMARK = ROOT / ".runtime/model-benchmark"
IDENTITY = ("author", "attendees", "date")


@contextmanager
def exclusive(benchmark=BENCHMARK):
    """Do not reset history or steal a lock, including after a previous crash."""
    if not (benchmark / "spend-ledger.json").is_file():
        raise ValueError("Existing benchmark spend-ledger.json is required; no new budget is created.")
    lock = benchmark / "run.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("Another benchmark or revision validation owns run.lock. Wait for it to finish.") from None
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        ledger = BudgetLedger(benchmark / "spend-ledger.json", 40)
        if ledger.accounted() >= 40:
            raise BudgetExceeded()
        yield ledger
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


def manifest(settings):
    expected = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))["files"]
    paths = [path for path in settings.corpus_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED]
    if len(expected) != 24 or {path.name for path in paths} != {row["filename"] for row in expected} or len(paths) != 24:
        raise ValueError("Final validation requires exactly the 24 canonical manifest sources.")
    for row in expected:
        if sha(settings.corpus_dir / row["filename"]) != row["sha256"]:
            raise ValueError("Canonical source bytes differ from the committed manifest.")
    return expected


def documents(store):
    with store.connect() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM documents")]


def canonical_rows(rows, expected, settings):
    selected = []
    for item in expected:
        path = str((settings.corpus_dir / item["filename"]).resolve())
        matches = [row for row in rows if row["active"] and row["source_path"] == path]
        if len(matches) != 1:
            raise ValueError("Each canonical source must have exactly one active version.")
        row = matches[0]
        metadata = json.loads(row["metadata"])
        if row["sha256"] != item["sha256"] or any(metadata[key] != item[key] for key in IDENTITY):
            raise ValueError("Canonical hash or deterministic attribution differs from the manifest.")
        selected.append(row)
    return selected


def clone_canonical(settings, destination, expected):
    """SQLite backup captures WAL safely; prune only this new isolated copy."""
    source_path = settings.data_dir / "workspace.sqlite3"
    if not source_path.is_file() or destination.exists():
        raise ValueError("The source database must exist and the clone destination must be new.")
    destination.mkdir(parents=True)
    with closing(sqlite3.connect(source_path.resolve().as_uri() + "?mode=ro", uri=True)) as source:
        with closing(sqlite3.connect(destination / "workspace.sqlite3")) as target:
            source.backup(target)
    store = Store(destination)
    selected = canonical_rows(documents(store), expected, settings)
    with store.connect() as connection:
        for table in ("feedback", "review", "outbox", "queries", "events", "evaluations", "embedding_cache"):
            connection.execute(f"DELETE FROM {table}")
        keep = {row["id"] for row in selected}
        for row in documents(store):
            if row["id"] not in keep:
                connection.execute("DELETE FROM chunks_fts WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id=?)", (row["id"],))
                connection.execute("DELETE FROM chunks WHERE document_id=?", (row["id"],))
                connection.execute("DELETE FROM documents WHERE id=?", (row["id"],))
        for row in selected:
            archived = Path(row["original_path"])
            if not archived.is_file() or sha(archived) != row["sha256"]:
                raise ValueError("A canonical archived original failed its integrity check.")
            copied = destination / "originals" / row["id"] / row["filename"]
            copied.parent.mkdir(parents=True)
            shutil.copyfile(archived, copied)
            connection.execute("UPDATE documents SET original_path=? WHERE id=?", (str(copied), row["id"]))
        # Keep source-vector caching, without retaining cached private questions.
        for chunk in connection.execute("SELECT text,embedding,embedding_model FROM chunks").fetchall():
            vector = json.loads(chunk["embedding"])
            key = hashlib.sha256((chunk["embedding_model"] + "\0" + str(len(vector)) + "\0" + chunk["text"]).encode()).hexdigest()
            connection.execute("INSERT OR REPLACE INTO embedding_cache VALUES(?,?)", (key, chunk["embedding"]))
    with store.connect() as connection:
        connection.execute("VACUUM")
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return store


async def audit_ingestion(settings, store, provider, ledger, expected):
    before = documents(store)
    previous = {row["source_path"]: json.loads(row["metadata"]) for row in before if row["active"]}
    attempts = len(ledger.value["attempts"])
    first = await ingest_directory(settings.corpus_dir, store=store, provider=provider, settings=settings)
    after = documents(store)
    selected = canonical_rows(after, expected, settings)
    archives_ok = all(Path(row["original_path"]).is_file() and sha(Path(row["original_path"])) == row["sha256"] for row in after)
    history_ok = {row["id"] for row in before}.issubset({row["id"] for row in after})
    attribution_ok = all(all(json.loads(row["metadata"])[key] == previous[row["source_path"]][key] for key in IDENTITY)
                         for row in selected if row["source_path"] in previous)
    first_requests = len(ledger.value["attempts"]) - attempts
    repeat = await ingest_directory(settings.corpus_dir, store=store, provider=provider, settings=settings)
    repeat_requests = len(ledger.value["attempts"]) - attempts - first_requests
    summary = lambda outcome: {key: outcome[key] for key in ("ingested", "unchanged", "failed", "retired", "skipped")}
    return {"passed": not first["failed"] and archives_ok and history_ok and attribution_ok and repeat["unchanged"] == 24
            and not repeat["failed"] and not repeat["ingested"] and repeat_requests == 0,
            "first_ingestion": summary(first), "repeat_ingestion": summary(repeat),
            "first_provider_requests": first_requests, "repeat_provider_requests": repeat_requests,
            "canonical_documents": len(selected), "active_documents": store.counts()[0], "active_chunks": store.counts()[1],
            "versions_checked": len(after), "manifest_hashes_and_attribution_match": True,
            "previous_attribution_preserved": attribution_ok, "previous_history_preserved": history_ok,
            "all_archived_original_hashes_match": archives_ok}


async def execute(mode, settings, ledger, runtime, report_path):
    if not settings.configured:
        raise ValueError("Set OPENROUTER_API_KEY in the backend environment or repository .env.")
    if any(model not in PRICE_CAPS for model in (settings.openrouter_model, settings.openrouter_review_model, settings.openrouter_embedding_model)):
        raise ValueError("A configured model has no approved benchmark price ceiling.")
    if settings.openrouter_embedding_dimensions != 1536:
        raise ValueError("Final validation requires 1536-dimensional embeddings.")
    expected = manifest(settings) if mode != "smoke" else None
    store = clone_canonical(settings, runtime, expected) if mode == "serve" else Store(settings.data_dir if mode == "ingest" else runtime)
    effective = settings.model_copy(update={"data_dir": store.data_dir, "daily_evaluation": False})
    provider = BenchmarkRouter(effective, store, transport=MeteredTransport(ledger, "revision-live:" + mode))
    started = now()
    try:
        if mode == "serve":
            import uvicorn
            # app.main also exports an eager default app. Keep that import's
            # setup inside the clone, then close its unused provider client.
            first_import = "app.main" not in sys.modules
            old_environment = {key: os.environ.get(key) for key in ("DATA_DIR", "DAILY_EVALUATION")}
            try:
                os.environ.update(DATA_DIR=str(store.data_dir), DAILY_EVALUATION="false")
                from app.main import app as unused_app, create_app
            finally:
                for key, value in old_environment.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            if first_import:
                await unused_app.state.service.provider.close()
            print("Metered validation server: http://127.0.0.1:8011 (isolated sources; no scheduled evaluations)", flush=True)
            await uvicorn.Server(uvicorn.Config(create_app(effective, provider=provider), host="127.0.0.1", port=8011, access_log=False)).serve()
            result = {"passed": None, "message": "Server session ended; individual UI/API assertions are recorded separately.", "canonical_documents_at_start": 24}
        elif mode == "ingest":
            result = await audit_ingestion(effective, store, provider, ledger, expected)
        else:
            enrichment = await provider.structured(Enrichment, ENRICH_PROMPT, {"title": "Fictional validation note", "text": "Domain: Deployment readiness. Priority: High. Decision: Keep the pilot read-only. Action item: Maya Chen will review the checklist."})
            vectors = await provider.embeddings(["Fictional validation: keep the pilot read-only."])
            result = {"passed": len(vectors) == 1 and len(vectors[0]) == 1536, "structured_enrichment": enrichment.model_dump(), "embedding_dimensions": len(vectors[0])}
    except (ProviderError, ValueError) as exc:
        result = {"passed": False, "error_category": exc.category if isinstance(exc, ProviderError) else "validation_failed",
                  "message": "Live validation did not complete successfully; inspect the safe ingestion checks or provider event categories."}
    finally:
        await provider.close()
    report = {"created_at": started, "completed_at": now(), "mode": mode, "live_provider": "OpenRouter",
              "enrichment_model": effective.openrouter_model, "review_model": effective.openrouter_review_model,
              "embedding_model": effective.openrouter_embedding_model, **result, "shared_budget": ledger.summary()}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"mode": mode, "passed": result["passed"], "report": str(report_path), "shared_budget": ledger.summary()}), flush=True)
    return 1 if result["passed"] is False else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("smoke", "ingest", "serve"))
    parser.add_argument("--report", type=Path, help="New sanitized report path; existing reports are never overwritten.")
    args = parser.parse_args()
    stamp = now().replace(":", "-").replace("+", "_") + "-" + uuid4().hex[:6]
    report = args.report or ROOT / "docs/evaluation-results" / f"revision-{args.mode}-{stamp}.json"
    if report.exists():
        parser.error("Choose a new report path; the existing report will be preserved.")
    try:
        with exclusive() as ledger:
            return asyncio.run(execute(args.mode, Settings(daily_evaluation=False), ledger, ROOT / ".runtime" / f"revision-{args.mode}-{stamp}", report))
    except (ValueError, BudgetExceeded) as exc:
        # These errors are locally defined setup/budget messages, never provider bodies.
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
