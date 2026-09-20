"""Explicit live ingestion audit; preserves source history and uses provider credits.

Run through the configured backend environment. The report is sanitized for
submission; the complete per-file run is retained only in ignored runtime data.
"""

import asyncio
import argparse
import hashlib
import json
from pathlib import Path

from app.config import ROOT, Settings
from app.ingestion import ingest_directory
from app.provider import OpenRouter
from app.store import Store, now


class CountingOpenRouter(OpenRouter):
    requests = 0

    async def request(self, endpoint, payload):
        self.requests += 1
        return await super().request(endpoint, payload)


def documents(store, *, active=False):
    with store.connect() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM documents" + (" WHERE active=1" if active else ""))]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "docs/evaluation-results/adversarial-reingestion.json",
                        help="Sanitized output report; choose a new filename to preserve earlier audits.")
    args = parser.parse_args()
    settings = Settings(daily_evaluation=False)
    store = Store(settings.data_dir)
    provider = CountingOpenRouter(settings, store)
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    previous = {row["filename"]: row for row in documents(store, active=True)}
    previous_ids = {row["id"] for row in documents(store)}
    try:
        first = await ingest_directory(settings.corpus_dir, store=store, provider=provider, settings=settings)
        first_requests = provider.requests
        print(json.dumps({"phase": "first_ingestion", "ingested": first["ingested"], "failed": first["failed"], "provider_requests": first_requests}), flush=True)
        (settings.data_dir / "adversarial-reingestion.json").write_text(json.dumps(first, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if first["failed"]:
            raise RuntimeError("Live ingestion reported failures; inspect ignored runtime outcome report.")
        active = documents(store, active=True)
        checks = []
        for expected in manifest["files"]:
            matches = [row for row in active if row["filename"] == expected["filename"]]
            assert len(matches) == 1, "Each manifest file must have exactly one active version."
            row = matches[0]
            metadata = json.loads(row["metadata"])
            old = json.loads(previous[row["filename"]]["metadata"]) if row["filename"] in previous else None
            checks.append({"filename": expected["filename"],
                           "sha256_matches_manifest": row["sha256"] == expected["sha256"],
                           "attribution_matches_manifest": all(metadata[key] == expected[key] for key in ("author", "attendees", "date")),
                           "attribution_matches_previous_version": None if old is None else all(metadata[key] == old[key] for key in ("author", "attendees", "date"))})
        all_documents = documents(store)
        archive_failures = [row["filename"] for row in all_documents if not Path(row["original_path"]).is_file() or hashlib.sha256(Path(row["original_path"]).read_bytes()).hexdigest() != row["sha256"]]
        history_preserved = previous_ids.issubset({row["id"] for row in all_documents})
        repeat = await ingest_directory(settings.corpus_dir, store=store, provider=provider, settings=settings)
        repeat_requests = provider.requests - first_requests
        document_count, chunk_count = store.counts()
        passed = (all(check["sha256_matches_manifest"] and check["attribution_matches_manifest"] and check["attribution_matches_previous_version"] is not False for check in checks)
                  and not archive_failures and history_preserved and document_count == 24 and chunk_count == 36
                  and repeat["unchanged"] == 24 and not repeat["failed"] and not repeat["ingested"] and repeat_requests == 0)
        report = {"created_at": now(), "passed": passed, "live_provider": "OpenRouter",
                  "enrichment_model": settings.openrouter_model, "embedding_model": settings.openrouter_embedding_model,
                  "first_ingestion": {key: first[key] for key in ("ingested", "unchanged", "failed", "retired", "skipped")},
                  "first_provider_requests": first_requests,
                  "repeat_ingestion": {key: repeat[key] for key in ("ingested", "unchanged", "failed", "retired", "skipped")},
                  "repeat_provider_requests": repeat_requests, "active_documents": document_count, "active_chunks": chunk_count,
                  "historical_versions_checked": len(all_documents), "all_archived_original_hashes_match": not archive_failures,
                  "archive_failures": archive_failures, "previous_document_history_preserved": history_preserved, "files": checks}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "files"}, indent=2), flush=True)
        if not passed:
            raise RuntimeError("Live ingestion audit failed; inspect sanitized report.")
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
