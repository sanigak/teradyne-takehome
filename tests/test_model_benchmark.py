"""The explicitly live benchmark must bound spend and isolate canonical fixtures."""
import asyncio
import json
import subprocess
import sys
from types import SimpleNamespace

import httpx
import pytest

from app.store import Store, now
from app.models import Enrichment
from scripts import model_benchmark as benchmark


PAYLOAD = {"model": benchmark.MODELS[0], "max_tokens": 512, "messages": []}


async def test_parallel_reservations_never_dispatch_over_budget(tmp_path):
    ledger = benchmark.BudgetLedger(tmp_path / "budget.json", .02)
    results = await asyncio.gather(*(ledger.reserve(PAYLOAD, "test") for _ in range(40)), return_exceptions=True)
    assert 0 < ledger.accounted() <= .02
    assert any(isinstance(result, benchmark.BudgetExceeded) for result in results)
    assert len(ledger.value["attempts"]) == sum(isinstance(result, dict) for result in results)


async def test_followup_reserve_is_not_spendable_by_main_benchmark(tmp_path):
    ledger = benchmark.BudgetLedger(tmp_path / "budget.json", .02, reserve_for_followup=.019)
    with pytest.raises(benchmark.BudgetExceeded):
        await ledger.reserve(PAYLOAD, "would-consume-followup")
    assert ledger.accounted() == 0


async def test_transport_releases_unused_reservation_and_counts_each_attempt(tmp_path):
    ledger = benchmark.BudgetLedger(tmp_path / "budget.json", 15)
    mock = httpx.MockTransport(lambda request: httpx.Response(200, json={"usage": {"cost": .0001}}))
    async with httpx.AsyncClient(transport=benchmark.MeteredTransport(ledger, "test", mock)) as client:
        await client.post("https://provider.invalid", json=PAYLOAD)
        await client.post("https://provider.invalid", json=PAYLOAD)
    assert ledger.accounted() == pytest.approx(.0002)
    assert len(ledger.value["attempts"]) == 2
    assert all(row["reserved_usd"] > row["accounted_usd"] for row in ledger.value["attempts"])


@pytest.mark.parametrize("failure", ["timeout", "cancelled", "missing_cost"])
async def test_unknown_billing_keeps_entire_reserved_bound(tmp_path, failure):
    ledger = benchmark.BudgetLedger(tmp_path / "budget.json", 15)

    def upstream(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("test")
        if failure == "cancelled":
            raise asyncio.CancelledError()
        return httpx.Response(200, json={"usage": {}})

    async with httpx.AsyncClient(transport=benchmark.MeteredTransport(ledger, "test", httpx.MockTransport(upstream))) as client:
        try:
            await client.post("https://provider.invalid", json=PAYLOAD)
        except (httpx.ReadTimeout, asyncio.CancelledError):
            pass
    row = ledger.value["attempts"][0]
    assert row["accounted_usd"] == row["reserved_usd"] > 0
    assert ledger.summary()["unknown_cost_attempts"] == 1


async def test_rejected_request_is_zero_but_reported_charge_is_preserved(tmp_path):
    ledger = benchmark.BudgetLedger(tmp_path / "budget.json", 15)
    for body, expected in [({"error": "unsupported parameter"}, 0), ({"usage": {"cost": .0001}}, .0001)]:
        row = await ledger.reserve(PAYLOAD, "test")
        await ledger.settle(row, response=httpx.Response(400, json=body))
        assert row["accounted_usd"] == expected


async def test_budget_increase_preserves_spend_and_refuses_unauthorized_limit(tmp_path):
    path = tmp_path / "budget.json"
    original = benchmark.BudgetLedger(path, 15)
    record = await original.reserve(PAYLOAD, "prior-run")
    await original.settle(record, response=httpx.Response(200, json={"usage": {"cost": .0001}}))
    upgraded = benchmark.BudgetLedger(path, 40)
    assert upgraded.accounted() == .0001
    assert upgraded.value["attempts"][0]["attempt_id"] == record["attempt_id"]
    assert upgraded.value["limit_changes"][0]["from_usd"] == 15
    with pytest.raises(ValueError):
        benchmark.BudgetLedger(path, 40.01)
    with pytest.raises(ValueError):
        benchmark.BudgetLedger(path, 15)


def test_exclusive_run_lock_blocks_second_process_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, "ROOT", tmp_path)
    output = tmp_path / ".runtime" / "benchmark"
    output.mkdir(parents=True)
    (output / "run.lock").write_text("12345")
    with pytest.raises(SystemExit, match="Another benchmark owns"):
        benchmark.run_exclusive(SimpleNamespace(output=output))
    assert (output / "run.lock").read_text() == "12345"


def test_canonical_copy_excludes_uploads_history_and_detects_tampering(tmp_path):
    source = Store(tmp_path / "source")
    gold = {"enrichment_gold": []}
    with source.connect() as db:
        for index in range(25):
            filename, digest = f"source-{index}.md", f"hash-{index}"
            metadata = {"author": "Avery Test", "attendees": ["Avery Test"], "date": "2026-09-01"}
            db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", (str(index), filename, filename, digest, 1, filename, json.dumps(metadata), now()))
            db.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?)", (f"chunk-{index}", str(index), "Fictional source", "paragraph 1", "[1,0,0]", "test-embedding"))
            if index < 24:
                gold["enrichment_gold"].append({"filename": filename, "sha256": digest, **metadata})
        db.execute("INSERT INTO queries VALUES(?,?,?,?)", ("private-history", "{}", now(), 0))
        db.execute("INSERT INTO embedding_cache VALUES(?,?)", ("cache", "[1,0,0]"))
    target = benchmark.prepare_canonical(source.path, tmp_path / "target", gold)
    with target.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 24
        assert db.execute("SELECT COUNT(*) FROM queries").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == 24
        assert db.execute("SELECT COUNT(*) FROM embedding_cache").fetchone()[0] == 1
        db.execute("UPDATE documents SET sha256='tampered' WHERE id='0'")
    with pytest.raises(ValueError, match="source identity"):
        benchmark.prepare_canonical(source.path, tmp_path / "target", gold)
    with source.connect() as db:
        assert db.execute("SELECT sha256 FROM documents WHERE id='0'").fetchone()[0] == "hash-0"
        assert db.execute("SELECT COUNT(*) FROM queries").fetchone()[0] == 1


def test_hybrid_has_explicit_model_options_and_separate_latency(tmp_path):
    settings = benchmark.settings_for(benchmark.MODELS[1], tmp_path, benchmark.MODELS[4])
    assert settings.openrouter_review_model == benchmark.MODELS[4]
    assert set(settings.openrouter_model_options) == {benchmark.MODELS[1], benchmark.MODELS[4]}
    assert all(value.reasoning_effort == "high" and value.temperature is None for value in settings.openrouter_model_options.values())
    records = [{"model": "candidate", "record_type": "control", "elapsed_seconds": 1, "correct": True},
               {"model": "candidate", "record_type": "pipeline", "elapsed_seconds": 60, "assessment": {"mechanical_pass": True}}]
    summary = benchmark.summarize(records, benchmark.BudgetLedger(tmp_path / "ledger.json", 15))["models"]["candidate"]
    assert summary["latency_by_record_type"]["pipeline"]["median_seconds"] == 60
    assert summary["latency_by_record_type"]["control"]["median_seconds"] == 1
    assert summary["quality_gate"] == "not_decided_without_independent_review"


def test_blind_packet_preserves_unicode_and_hides_model_identity(tmp_path):
    from scripts.blind_model_benchmark import blind_reports
    report, packet, mapping = (tmp_path / filename for filename in ("report.json", "packet.json", "mapping.json"))
    title = "Beacon \u2014 caf\u00e9 \U0001f6e0"
    benchmark.write_json(report, {"gold_sha256": "frozen", "records": [{"record_type": "pipeline", "model": "secret-candidate-name", "review_model": "secret-reviewer", "case_id": "case", "gold": {"question": title}, "answer": {"query_id": "private-id", "created_at": "private-time", "claims": [{"text": title}]}, "elapsed_seconds": 1000}]})
    assert blind_reports([report], packet, mapping, "pipeline") == 1
    text = packet.read_text(encoding="utf-8")
    assert title in text
    assert all(private not in text for private in ("secret-candidate-name", "secret-reviewer", "private-id", "private-time", "elapsed_seconds"))
    assert json.loads(text)["records"][0]["answer"]["claims"][0]["text"] == title
    with pytest.raises(ValueError, match="Preserve existing"):
        blind_reports([report], packet, mapping, "pipeline")


def test_blind_helper_direct_script_entrypoint_needs_no_import_path_hacks():
    result = subprocess.run([sys.executable, str(benchmark.ROOT / "scripts/blind_model_benchmark.py"), "--help"], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert "--parts" in result.stdout


def test_balanced_blind_packets_include_operational_failures(tmp_path):
    from scripts.blind_model_benchmark import blind_reports
    report, output, mapping = (tmp_path / filename for filename in ("report.json", "blind.json", "mapping.json"))
    records = []
    for model in ("candidate-a", "candidate-b", "candidate-c"):
        for index in range(6):
            record = {"record_type": "pipeline", "model": model, "review_model": model, "case_id": str(index), "gold": {"question": str(index)}}
            record.update({"error_category": "invalid_verification", "error": "Invalid references"} if index == 0 else {"answer": {"claims": []}})
            records.append(record)
    benchmark.write_json(report, {"gold_sha256": "frozen", "records": records})
    assert blind_reports([report], output, mapping, "pipeline", parts=3) == 18
    keys = json.loads(mapping.read_text(encoding="utf-8"))
    errors = 0
    for path in tmp_path.glob("blind-part*.json"):
        packet = json.loads(path.read_text(encoding="utf-8"))["records"]
        assert len(packet) == 6
        for model in ("candidate-a", "candidate-b", "candidate-c"):
            assert sum(keys[row["anonymous_id"]]["model"] == model for row in packet) == 2
        errors += sum("operational_error" in row for row in packet)
    assert errors == 3


async def test_benchmark_trace_preserves_parsed_output_without_credentials(settings, store):
    settings = settings.model_copy(update={"openrouter_model": benchmark.MODELS[0]})
    payloads = []

    def upstream(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"domain": "Fictional Atlas", "priority": None, "decisions": [], "action_items": []})}}]})

    provider = benchmark.BenchmarkRouter(settings, store, transport=httpx.MockTransport(upstream))
    try:
        content = {"text": "Fictional source"}
        await provider.structured(Enrichment, "Classify", content)
        content["repair_instruction"] = "Later mutation"
        assert provider.structured_outputs[0]["schema"] == "Enrichment"
        assert provider.structured_outputs[0]["result"]["domain"] == "Fictional Atlas"
        assert "repair_instruction" not in provider.structured_outputs[0]["input"]
        assert settings.openrouter_api_key.get_secret_value() not in json.dumps(provider.structured_outputs)
        assert payloads[0]["provider"]["max_price"] == {"prompt": .5, "completion": 2.0}
        assert payloads[0]["provider"]["ignore"] == ["openai/flex"]
    finally:
        await provider.close()


async def test_upstream_credit_failure_pauses_queue_and_saves_only_known_metadata(tmp_path, settings, store):
    ledger = benchmark.BudgetLedger(tmp_path / "budget.json", 40)
    calls = []

    def upstream(request):
        calls.append(request)
        return httpx.Response(402, json={"error": {"metadata": {"limit_source": "openrouter_key_limit", "reason": [], "private": "test-only-sensitive-data"}}})

    transport = benchmark.MeteredTransport(ledger, "test-credit-failure", httpx.MockTransport(upstream))
    provider = benchmark.BenchmarkRouter(settings, store, transport=transport)
    try:
        with pytest.raises(benchmark.ProviderError):
            await provider.structured(Enrichment, "Classify", {"text": "Fictional source"})
        assert ledger.upstream_pause == {"limit_source": "openrouter_key_limit"}
        with pytest.raises(benchmark.ProviderError) as paused:
            await provider.structured(Enrichment, "Classify", {"text": "Another fictional source"})
        assert paused.value.category == "benchmark_upstream_pause"
        assert len(calls) == 1
        assert "test-only-sensitive-data" not in json.dumps(ledger.value)
    finally:
        await provider.close()


def test_adjudication_preserves_failed_verdict_and_rejects_mismatched_mapping(tmp_path, monkeypatch):
    from scripts import adjudicate_model_benchmark as adjudicate
    monkeypatch.setattr(adjudicate, "ROOT", tmp_path)
    source = tmp_path / "answer.json"
    source.write_text(json.dumps({"records": [{"model": "candidate", "review_model": "reviewer", "case_id": "case1"}]}), encoding="utf-8")
    mapping = tmp_path / "mapping.json"
    value = {"anon": {"source_report": "answer.json", "record_index": 0, "model": "candidate", "review_model": "reviewer", "case_id": "case1", "filename": None}}
    mapping.write_text(json.dumps(value), encoding="utf-8")
    review = tmp_path / "review.json"
    review.write_text(json.dumps({"reviewer": "independent agent", "records": [{"anonymous_id": "anon", "case_id": "case1", "passed": False, "rationale": "Required fact omitted"}]}), encoding="utf-8")
    result = adjudicate.join_reviews([review], [mapping], tmp_path / "joined.json", 2)
    assert result["complete"] is False
    assert result["configurations"][0]["passed"] == 0
    assert result["configurations"][0]["pending"] == 1
    assert result["records"][0]["original_review"]["rationale"] == "Required fact omitted"
    value["anon"]["case_id"] = "wrong-case"
    mapping.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="no longer matches"):
        adjudicate.join_reviews([review], [mapping], tmp_path / "invalid.json", 2)


@pytest.mark.parametrize("label", ["../outside", "..", "C:\\outside", "/outside", "folder/name", "", "a" * 65])
def test_corpus_label_rejects_paths_and_traversal(tmp_path, label):
    with pytest.raises(ValueError, match="Corpus label"):
        benchmark.corpus_directory(tmp_path, label)


def test_new_corpus_label_freezes_current_metadata_without_resetting_ledger_or_history(tmp_path):
    output = tmp_path / "benchmark"
    output.mkdir()
    ledger_path = output / "spend-ledger.json"
    ledger_bytes = b'{"limit_usd":40,"attempts":[{"reported_cost_usd":1.5}]}'
    ledger_path.write_bytes(ledger_bytes)
    source = Store(tmp_path / "source")
    gold = {"enrichment_gold": []}
    with source.connect() as db:
        for index in range(24):
            metadata = {"author": "Avery Test", "attendees": ["Avery Test"], "date": "2026-09-01", "domain": "original"}
            filename, digest = f"source-{index}.md", f"hash-{index}"
            db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", (str(index), filename, filename, digest, 1, filename, json.dumps(metadata), now()))
            db.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?)", (f"chunk-{index}", str(index), "Fictional source", "paragraph 1", "[1,0,0]", "test-embedding"))
            gold["enrichment_gold"].append({"filename": filename, "sha256": digest, **metadata})
    old = benchmark.prepare_canonical(source.path, output / "candidate", gold)
    with old.connect() as db:
        db.execute("INSERT INTO queries VALUES(?,?,?,?)", ("preserved-old-attempt", "{}", now(), 0))
    changed = {**metadata, "domain": "fresh main enrichment", "decisions": ["Keep source scope."]}
    with source.connect() as db:
        db.execute("UPDATE documents SET metadata=? WHERE id='0'", (json.dumps(changed),))
    labelled = benchmark.corpus_directory(output, "release-v3-main") / "candidate"
    fresh = benchmark.prepare_canonical(source.path, labelled, gold, require_source_metadata_match=True)
    snapshot = benchmark.corpus_snapshot(fresh)
    assert len(snapshot) == 24
    assert snapshot[0]["metadata"] == changed
    assert snapshot[0]["metadata_sha256"] == benchmark.canonical_json_sha(changed)
    assert snapshot[0]["chunks"][0]["text"] == "Fictional source"
    with fresh.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM queries").fetchone()[0] == 0
    with old.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM queries").fetchone()[0] == 1
        assert json.loads(db.execute("SELECT metadata FROM documents WHERE id='0'").fetchone()[0])["domain"] == "original"
    assert ledger_path.read_bytes() == ledger_bytes
    with source.connect() as db:
        db.execute("UPDATE documents SET metadata=? WHERE id='0'", (json.dumps({**changed, "domain": "later mutation"}),))
    with pytest.raises(ValueError, match="choose a new corpus label"):
        benchmark.prepare_canonical(source.path, labelled, gold, require_source_metadata_match=True)
    assert ledger_path.read_bytes() == ledger_bytes
