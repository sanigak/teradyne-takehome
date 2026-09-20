import json

import httpx
import pytest
from pydantic import SecretStr

from app.ingestion import ingest_file
from app.main import create_app
from conftest import SOURCE_TEXT


@pytest.fixture
async def client(settings, provider):
    app = create_app(settings, provider=provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        yield client


async def test_missing_key_health_and_actionable_query(tmp_path, provider):
    from app.config import Settings
    settings = Settings(_env_file=None, openrouter_api_key="", data_dir=tmp_path, daily_evaluation=False)
    app = create_app(settings, provider=provider)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        assert not health.json()["configured"]
        assert not health.json()["ready"]
        response = await client.post("/api/query", json={"question": "What is approved?"})
        assert response.status_code == 503
        assert "OPENROUTER_API_KEY" in response.json()["detail"]
        assert (await client.get("/api/gaps")).json()["items"] == []


async def test_empty_corpus_is_not_knowledge_gap(client):
    result = await client.post("/api/query", json={"question": "What does Atlas need?"})
    assert result.status_code == 503
    assert "ingest" in result.json()["detail"]
    assert (await client.get("/api/gaps")).json()["items"] == []


async def test_embedding_dimensions_drift_is_visible_and_prevents_query(client, settings, store, provider, ingested):
    settings.openrouter_embedding_dimensions = 6
    health = (await client.get("/api/health")).json()
    assert health["ready"] is False
    assert any("dimensions changed" in warning for warning in health["warnings"])
    response = await client.post("/api/query", json={"question": "What approval does Atlas require?"})
    assert response.status_code == 503
    assert "dimensions changed" in response.json()["detail"]
    assert store.reviews()["items"] == []


async def test_partial_ingestion_keeps_good_sources_available_and_shows_failure(client, settings, store, provider, source, ingested):
    from app.ingestion import ingest_directory
    (settings.corpus_dir / "broken.docx").write_bytes(b"invalid file")
    await ingest_directory(settings.corpus_dir, store=store, provider=provider, settings=settings)
    health = (await client.get("/api/health")).json()
    assert health["ready"] is True
    assert health["document_count"] == 1
    assert any("broken.docx" in warning for warning in health["warnings"])


async def test_question_feedback_review_roundtrip(client, settings, store, provider, source, ingested):
    response = await client.post("/api/query", json={"question": "What approval does Atlas require?"})
    assert response.status_code == 200
    answer = response.json()
    assert (await client.get(f"/api/query/{answer['query_id']}")).json() == answer
    rejected = await client.post("/api/feedback", json={"query_id": answer["query_id"], "kind": "corrected", "comment": "The approval process needs a second reviewer."})
    assert rejected.status_code == 201
    review = (await client.get("/api/review")).json()["items"][0]
    assert review["answer"] == answer
    source.write_text(SOURCE_TEXT.replace("90 days", "180 days"), encoding="utf-8")
    await ingest_file(source, store=store, provider=provider, settings=settings)
    assert (await client.get("/api/review")).json()["items"][0]["answer"] == answer
    resolved = await client.patch(f"/api/review/{review['id']}", json={"status": "resolved", "resolution_note": "Confirmed with Elena; source update is pending."})
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["answer"] == answer
    assert (await client.get("/api/corrections")).json()["items"][0]["id"] == review["id"]


async def test_source_version_download_and_active_list(client, settings, store, provider, source, ingested):
    original_id = ingested["document_id"]
    source.write_text(SOURCE_TEXT.replace("90 days", "180 days"), encoding="utf-8")
    new = await ingest_file(source, store=store, provider=provider, settings=settings)
    detail = (await client.get(f"/api/sources/{original_id}")).json()
    assert detail["active"] is False
    assert detail["chunks"][0]["locator"]
    original = await client.get(f"/api/sources/{original_id}/file")
    assert original.status_code == 200
    assert "90 days" in original.text
    assert "180 days" not in original.text
    items = (await client.get("/api/sources")).json()["items"]
    assert len(items) == 1 and items[0]["document_id"] == new["document_id"]


async def test_outbox_simulation_persists_and_rejects_forged_evidence(client, provider, ingested):
    provider.mode = "gap"
    answer = (await client.post("/api/query", json={"question": "When is Atlas approval due?"})).json()
    draft = {"query_id": answer["query_id"], "recipient": "Elena Rivera", "subject": "Approval date", "body": "Please confirm the date.", "evidence_ids": [answer["evidence"][0]["chunk_id"]]}
    result = await client.post("/api/outbox", json=draft)
    assert result.status_code == 201
    assert result.json()["status"] == "simulated"
    assert (await client.get("/api/outbox")).json()["items"] == [result.json()]
    draft["evidence_ids"] = ["invented"]
    assert (await client.post("/api/outbox", json=draft)).status_code == 422


async def test_feedback_rate_deduplicates_negative_responses(client, ingested):
    answer = (await client.post("/api/query", json={"question": "What approval does Atlas require?"})).json()
    for kind in ["rejected", "corrected", "corrected"]:
        await client.post("/api/feedback", json={"query_id": answer["query_id"], "kind": kind, "comment": "Please review this answer."})
    metrics = (await client.get("/api/metrics")).json()
    assert metrics["answered_query_count"] == 1
    assert metrics["rejected_or_corrected_query_count"] == 1
    assert metrics["rejection_correction_rate"] == 1


@pytest.mark.parametrize("path,body", [
    ("/api/query", {"question": "   "}),
    ("/api/feedback", {"query_id": "missing", "kind": "rejected", "comment": ""}),
    ("/api/outbox", {"query_id": "missing", "recipient": "   ", "subject": "hi", "body": "hi", "evidence_ids": []}),
])
async def test_invalid_inputs_return_readable_errors(client, path, body):
    response = await client.post(path, json=body)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


async def test_unknown_records_and_unknown_api_are_json_404(client):
    for path in ["/api/query/missing", "/api/sources/missing", "/api/sources/missing/file", "/api/not-real"]:
        response = await client.get(path)
        assert response.status_code == 404
        assert "detail" in response.json()
    assert (await client.post("/api/feedback", json={"query_id": "missing", "kind": "accepted"})).status_code == 404
