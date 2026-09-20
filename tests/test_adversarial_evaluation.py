import json

from app.evaluation import evaluate, quality
from app.models import Routing
from app.service import KnowledgeService


async def test_passing_canary_cannot_clear_a_full_evaluation_failure(settings, store, provider, ingested):
    settings.evaluation_path.write_text(json.dumps([
        {"id": "okay", "question": "Atlas approval?", "expected_status": "answered"},
        {"id": "regressed", "question": "Atlas approval?", "expected_status": "needs_routing"},
    ]), encoding="utf-8")
    service = KnowledgeService(settings, store, provider)
    full = await evaluate(service)
    canary = await evaluate(service, limit=1)
    assert full["pass_rate"] == .5 and canary["pass_rate"] == 1
    assert quality(store)["latest"]["id"] == canary["id"]
    assert any("held-out-full" in alert and "failed" in alert for alert in quality(store)["alerts"])


async def test_correct_abstention_status_cannot_hide_an_invented_expert(settings, store, provider, ingested):
    answer = await KnowledgeService(settings, store, provider).query("Atlas approval?", evaluation=True)
    answer = answer.model_copy(update={"status": "needs_routing", "claims": [], "routing": [Routing(recipient="Invented Expert", reason="No source", draft_question="Recipe?", evidence_ids=[answer.evidence[0].chunk_id])]})
    settings.evaluation_path.write_text(json.dumps([{"id": "unrelated", "question": "Lemon tart recipe?", "expected_status": "needs_routing", "expect_no_evidence": True, "expect_no_routing": True}]), encoding="utf-8")
    service = KnowledgeService(settings, store, provider)
    async def invalid_answer(*args, **kwargs):
        return answer
    service.query = invalid_answer
    result = await evaluate(service)
    assert result["passed"] == 0
    assert len(result["cases"][0]["behavioral_failures"]) == 3


async def test_empty_answer_cannot_pass_by_vacuous_citation_validity(settings, store, provider, ingested):
    service = KnowledgeService(settings, store, provider)
    answer = await service.query("Atlas approval?", evaluation=True)
    answer = answer.model_copy(update={"claims": []})
    async def invalid_answer(*args, **kwargs):
        return answer
    service.query = invalid_answer
    settings.evaluation_path.write_text(json.dumps([{"id": "empty", "question": "Atlas approval?", "expected_status": "answered"}]), encoding="utf-8")
    result = await evaluate(service)
    assert result["passed"] == 0
    assert "no claims" in result["cases"][0]["behavioral_failures"][0]
