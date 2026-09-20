import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app.extractors import ExtractionError, discover_soffice
from app.ingestion import ingest_directory
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_matches_committed_original_bytes():
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        path = ROOT / "data" / "corpus" / item["filename"]
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == item["sha256"], item["filename"]
        if path.suffix == ".md":
            assert b"\r\n" not in content, "Markdown must use canonical LF so Git clones preserve the manifest hash."


async def test_all_24_sources_ingest_with_originals_and_attribution(settings, store, provider):
    """Full pipeline with genuine Office parsing and test-only model responses."""
    try:
        settings.soffice_path = discover_soffice()
    except ExtractionError:
        pytest.skip("Full 24-source integration requires LibreOffice; set SOFFICE_PATH.")
    corpus = ROOT / "data" / "corpus"
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    outcomes = await ingest_directory(corpus, store=store, provider=provider, settings=settings)
    assert outcomes["failed"] == 0, outcomes
    assert outcomes["ingested"] == 24
    app = create_app(settings, provider=provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        health = (await client.get("/api/health")).json()
        assert health["ready"] is True
        assert health["document_count"] == 24
        assert health["chunk_count"] >= 24
        sources = (await client.get("/api/sources")).json()["items"]
        by_name = {item["filename"]: item for item in sources}
        for expected in manifest["files"]:
            item = by_name[expected["filename"]]
            assert item["author"] == expected["author"]
            assert item["attendees"] == expected["attendees"]
            assert item["date"] == expected["date"]
            detail = (await client.get(f"/api/sources/{item['document_id']}")).json()
            assert detail["chunks"] and all(chunk["locator"] for chunk in detail["chunks"])
            original = await client.get(f"/api/sources/{item['document_id']}/file")
            assert original.status_code == 200
            assert hashlib.sha256(original.content).hexdigest() == expected["sha256"]
    call_count = len(provider.calls)
    repeated = await ingest_directory(corpus, store=store, provider=provider, settings=settings)
    assert repeated["unchanged"] == 24
    assert repeated["ingested"] == repeated["failed"] == 0
    assert len(provider.calls) == call_count
    assert len(list((store.data_dir / "originals").glob("*/*"))) == 24
