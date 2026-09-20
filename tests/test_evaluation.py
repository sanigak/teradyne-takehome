import json

from app.evaluation import evaluate, quality
from app.service import KnowledgeService


def test_scheduler_failures_are_visible_on_quality_endpoint(store):
    store.event("evaluation_failure", {"category": "scheduler_error"})
    assert any("Scheduled evaluation failed" in alert for alert in quality(store)["alerts"])


async def test_heldout_evaluation_persists_quality_and_detects_regression(settings, store, provider, ingested):
    settings.evaluation_path.write_text(json.dumps([{"id": "approval", "question": "What approval does Atlas require?", "expected_status": "answered", "expected_sources": ["atlas.md"], "required_terms": ["human approval"], "forbidden_terms": ["autonomous approval"]}]), encoding="utf-8")
    service = KnowledgeService(settings, store, provider)
    result = await evaluate(service)
    assert result["pass_rate"] == result["retrieval_recall"] == result["citation_validity"] == 1
    assert result["verified_claim_count"] == 1
    assert store.metrics()["query_count"] == 0
    await evaluate(service, limit=1)
    provider.mode = "gap"
    regression = await evaluate(service)
    assert regression["pass_rate"] == 0
    assert any("regressed" in message for message in regression["alerts"])
    assert quality(store)["latest"]["id"] == regression["id"]
    assert store.reviews()["items"] == []


async def test_operational_errors_count_against_abstention_accuracy(settings, store, provider, ingested):
    from app.provider import ProviderError
    settings.evaluation_path.write_text(json.dumps([{"id": "missing", "question": "When is Atlas approval due?", "expected_status": "needs_routing", "expected_sources": ["atlas.md"], "required_terms": []}]), encoding="utf-8")
    async def unavailable(*args):
        raise ProviderError("Provider unavailable.", category="unavailable")
    provider.embeddings = unavailable
    result = await evaluate(KnowledgeService(settings, store, provider))
    assert result["pass_rate"] == result["abstention_accuracy"] == result["retrieval_recall"] == 0
    assert result["cases"][0]["operational_error"] == "unavailable"
    assert store.reviews()["items"] == []


async def test_regression_baselines_do_not_compare_different_datasets(settings, store, provider, ingested):
    case = {"id": "approval", "question": "What approval does Atlas require?", "expected_status": "answered", "expected_sources": ["atlas.md"], "required_terms": []}
    settings.evaluation_path.write_text(json.dumps([case]), encoding="utf-8")
    service = KnowledgeService(settings, store, provider)
    first = await evaluate(service)
    case["id"] = "separate-audit-question"
    settings.evaluation_path.write_text(json.dumps([case]), encoding="utf-8")
    provider.mode = "gap"
    second = await evaluate(service)
    assert first["dataset_sha256"] != second["dataset_sha256"]
    assert first["baseline_key"] != second["baseline_key"]
    assert second["pass_rate"] == 0
    assert not any("regressed" in alert for alert in second["alerts"])
