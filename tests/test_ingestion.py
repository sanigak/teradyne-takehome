import json

import pytest

from app.ingestion import cached_embeddings, ingest_directory, ingest_file
from app.provider import ProviderError
from conftest import SOURCE_TEXT


async def test_ingestion_idempotence_attribution_and_cached_vectors(settings, store, provider, source):
    first = await ingest_file(source, store=store, provider=provider, settings=settings)
    count = len(provider.calls)
    second = await ingest_file(source, store=store, provider=provider, settings=settings)
    assert second["status"] == "unchanged"
    assert second["document_id"] == first["document_id"]
    assert len(provider.calls) == count
    with store.connect() as conn:
        metadata = json.loads(conn.execute("SELECT metadata FROM documents").fetchone()[0])
    assert metadata["author"] == "Elena Rivera"
    assert metadata["date"] == "2026-08-01"
    assert metadata["attendees"] == ["Elena Rivera", "Marcus Chen"]
    await cached_embeddings(store, provider, settings, ["a paraphrase"])
    count = len(provider.calls)
    await cached_embeddings(store, provider, settings, ["a paraphrase"])
    assert len(provider.calls) == count


async def test_new_version_preserves_old_source_and_chunks(settings, store, provider, source, ingested):
    source.write_text(SOURCE_TEXT.replace("90 days", "180 days"), encoding="utf-8")
    newer = await ingest_file(source, store=store, provider=provider, settings=settings)
    assert newer["document_id"] != ingested["document_id"]
    with store.connect() as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY created_at").fetchall()
        chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
    from pathlib import Path
    assert [row["active"] for row in rows] == [0, 1]
    assert "90 days" in Path(rows[0]["original_path"]).read_text(encoding="utf-8")
    assert "180 days" in Path(rows[1]["original_path"]).read_text(encoding="utf-8")
    assert chunks >= 2
    assert store.counts()[0] == 1


async def test_failed_refresh_preserves_last_good_version(settings, store, provider, source, ingested):
    source.write_text(SOURCE_TEXT + "\nA new decision.\n", encoding="utf-8")
    provider.failed_enrichment = True
    result = await ingest_directory(settings.corpus_dir, store=store, provider=provider, settings=settings)
    assert result["failed"] == 1
    assert result["items"][0]["category"] == "unavailable"
    with store.connect() as conn:
        active = conn.execute("SELECT id FROM documents WHERE active=1").fetchone()[0]
    assert active == ingested["document_id"]


async def test_changed_model_and_force_refresh_profile(settings, store, provider, source, ingested):
    settings.openrouter_model = "another/configured-model"
    changed = await ingest_file(source, store=store, provider=provider, settings=settings)
    assert changed["status"] == "ingested"
    forced = await ingest_file(source, store=store, provider=provider, settings=settings, force=True)
    assert forced["document_id"] != changed["document_id"]


async def test_bad_file_does_not_abort_remaining_sources(settings, store, provider, source):
    (settings.corpus_dir / "broken.docx").write_bytes(b"not an office file")
    result = await ingest_directory(settings.corpus_dir, store=store, provider=provider, settings=settings)
    assert result["failed"] == 1
    assert result["ingested"] == 1


async def test_missing_credentials_do_not_fake_ingestion(settings, store, provider, source):
    from pydantic import SecretStr
    settings.openrouter_api_key = SecretStr("")
    with pytest.raises(ProviderError, match="OPENROUTER_API_KEY"):
        await ingest_directory(settings.corpus_dir, store=store, provider=provider, settings=settings)
    assert store.counts() == (0, 0)
