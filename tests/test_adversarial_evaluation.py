import json
import asyncio
import hashlib
import pytest
from datetime import datetime, timedelta, timezone

from app.evaluation import claim_daily_evaluation, evaluate, evaluation_identity, quality
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
    assert quality(store)["open_finding_count"] == 1
    assert {entry["suite"]: entry["failed_cases"] for entry in quality(store)["suites"]} == {"daily-canary": 0, "held-out-full": 1}

    # A passing rerun of the same full suite resolves its current finding,
    # while the failed historical record remains available in SQLite.
    settings.evaluation_path.write_text(json.dumps([
        {"id": "okay", "question": "Atlas approval?", "expected_status": "answered"},
        {"id": "regressed", "question": "Atlas approval?", "expected_status": "answered"},
    ]), encoding="utf-8")
    await evaluate(service)
    assert quality(store)["open_finding_count"] == 0
    with store.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM evaluations").fetchone()[0] == 3


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


async def test_versioned_gold_runs_all_cases_without_claiming_semantic_certification(settings, store, provider, ingested):
    case = {"id": "fact", "question": "Atlas approval?", "expected_status": "answered",
            "required_facts": ["Independent semantic review remains required."]}
    settings.evaluation_path.write_text(json.dumps({"version": 1, "cases": [case]}), encoding="utf-8")
    result = await evaluate(KnowledgeService(settings, store, provider))
    assert result["case_count"] == 1
    assert "independent review" in result["support_measurement"]
    with store.connect() as conn:
        attempt = json.loads(conn.execute("SELECT payload FROM events WHERE kind='evaluation_started'").fetchone()[0])
    assert attempt["dataset_sha256"] == result["dataset_sha256"]
    assert attempt["suite"] == "held-out-full"


async def test_daily_runs_full_configured_suite_despite_a_recent_unrelated_or_short_check(settings, store, provider, ingested, monkeypatch):
    import app.evaluation as module
    settings.evaluation_path.write_text('[{"id":"daily"}]', encoding="utf-8")
    digest = hashlib.sha256(settings.evaluation_path.read_bytes()).hexdigest()
    record = {"dataset_sha256": digest, "suite": "daily-canary", "model": settings.openrouter_model,
              "review_model": settings.openrouter_review_model}
    store.event("evaluation_started", record)
    store.event("evaluation_started", {**record, "suite": "held-out-full", "dataset_sha256": "another-dataset"})
    calls = []
    async def run(*args, **kwargs):
        calls.append(kwargs)
    async def stop(_):
        raise asyncio.CancelledError
    monkeypatch.setattr(module, "evaluate", run)
    monkeypatch.setattr(module.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        await module.daily_evaluation_loop(KnowledgeService(settings, store, provider))
    assert calls == [{}]  # No implicit three-case truncation.


async def test_daily_attempt_backoff_survives_interruption_and_expires_after_a_day(settings, store, provider, ingested, monkeypatch):
    import app.evaluation as module
    settings.evaluation_path.write_text('[{"id":"daily"}]', encoding="utf-8")
    service = KnowledgeService(settings, store, provider)
    record = {**evaluation_identity(service, settings.evaluation_path.read_bytes()), "suite": "held-out-full"}
    store.event("evaluation_started", record)  # No completion report: interrupted request.
    calls = []
    async def run(*args, **kwargs):
        calls.append(kwargs)
    async def stop(_):
        raise asyncio.CancelledError
    monkeypatch.setattr(module, "evaluate", run)
    monkeypatch.setattr(module.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        await module.daily_evaluation_loop(service)
    assert not calls
    with store.connect() as conn:
        conn.execute("UPDATE events SET created_at=? WHERE kind='evaluation_started'",
                     ((datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),))
    with pytest.raises(asyncio.CancelledError):
        await module.daily_evaluation_loop(service)
    assert calls == [{}]


def test_parallel_servers_claim_only_one_daily_paid_run_and_model_options_trigger_fresh_check(settings, store, provider):
    from concurrent.futures import ThreadPoolExecutor
    from app.config import ModelOptions
    settings.evaluation_path.write_text('[{"id":"daily"}]', encoding="utf-8")
    service = KnowledgeService(settings, store, provider)
    with ThreadPoolExecutor(max_workers=4) as executor:
        claims = list(executor.map(lambda _: claim_daily_evaluation(service), range(4)))
    assert sum(claims) == 1
    settings.openrouter_model_options = {settings.openrouter_model: ModelOptions(reasoning_effort="high")}
    assert claim_daily_evaluation(service)
    assert not claim_daily_evaluation(service)
