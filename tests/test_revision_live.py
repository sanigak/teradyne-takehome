"""Final live helper safeguards; every provider interaction here is test-only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import httpx
import pytest

from app.models import Enrichment
from app.store import Store, now
from scripts import revision_live as live


def ledger_file(path, spend=0):
    path.mkdir(parents=True)
    value = {"limit_usd": 40, "attempts": [{"reserved_usd": spend, "accounted_usd": spend}] if spend else []}
    (path / "spend-ledger.json").write_text(json.dumps(value), encoding="utf-8")


def test_shared_lock_and_existing_budget_cannot_be_bypassed(tmp_path):
    with pytest.raises(ValueError, match="Existing benchmark"):
        with live.exclusive(tmp_path):
            pytest.fail("No history may not create another budget")
    ledger_file(tmp_path / "benchmark", .25)
    with live.exclusive(tmp_path / "benchmark") as ledger:
        assert ledger.accounted() == .25
        with pytest.raises(ValueError, match="owns run.lock"):
            with live.exclusive(tmp_path / "benchmark"):
                pytest.fail("Concurrent process entered")
    assert not (tmp_path / "benchmark/run.lock").exists()
    ledger_file(tmp_path / "exhausted", 40)
    with pytest.raises(live.BudgetExceeded):
        with live.exclusive(tmp_path / "exhausted"):
            pytest.fail("Exhausted ledger entered")
    assert not (tmp_path / "exhausted/run.lock").exists()


def test_clone_preserves_canonical_originals_but_excludes_history_and_same_name_upload(settings, store, tmp_path):
    filename = "canonical.md"
    content = b"Fictional canonical source"
    original = settings.data_dir / filename
    original.write_bytes(content)
    metadata = {"author": "Avery", "attendees": ["Avery"], "date": "2026-09-20"}
    expected = [{"filename": filename, "sha256": hashlib.sha256(content).hexdigest(), **metadata}]
    private = "PRIVATE_HISTORY_SENTINEL_DO_NOT_CLONE"
    with store.connect() as connection:
        for doc_id, source_path in (("canonical", str((settings.corpus_dir / filename).resolve())), ("uploaded", str(tmp_path / "uploads" / filename))):
            connection.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", (doc_id, source_path, filename, expected[0]["sha256"], 1, str(original), json.dumps(metadata), now()))
            connection.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?)", (doc_id, doc_id, "Canonical source" if doc_id == "canonical" else private, "paragraph 1", "[1,0,0]", "embedding-test"))
            connection.execute("INSERT INTO chunks_fts VALUES(?,?)", (doc_id, "Canonical source" if doc_id == "canonical" else private))
        connection.execute("INSERT INTO queries VALUES(?,?,?,?)", ("private-query", private, now(), 0))
        connection.execute("INSERT INTO feedback VALUES(?,?,?,?,?)", ("feedback", "private-query", "corrected", private, now()))
        connection.execute("INSERT INTO review VALUES(?,?,?,?,?,?,?,?)", ("review", "gap", "private-query", private, private, "open", "", now()))
        connection.execute("INSERT INTO outbox VALUES(?,?,?)", ("outbox", private, now()))
        connection.execute("INSERT INTO embedding_cache VALUES(?,?)", (private, "[1,0,0]"))
    clone = live.clone_canonical(settings, tmp_path / "clone", expected)
    assert clone.counts() == (1, 1)
    assert store.counts() == (2, 2)
    with clone.connect() as connection:
        for table in ("queries", "review", "feedback", "outbox", "events", "evaluations"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        row = connection.execute("SELECT * FROM documents").fetchone()
        assert Path(row["original_path"]).is_relative_to(clone.data_dir)
        assert Path(row["original_path"]).read_bytes() == content
        assert connection.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM embedding_cache").fetchone()[0] == 1
    assert private.encode() not in clone.path.read_bytes()
    with store.connect() as connection:
        assert connection.execute("SELECT result FROM queries").fetchone()[0] == private


async def test_smoke_uses_shared_metering_price_caps_and_never_saves_secret(settings, tmp_path, monkeypatch):
    settings.openrouter_embedding_dimensions = 1536
    dispatched = []
    def upstream(request):
        payload = json.loads(request.content)
        dispatched.append(payload)
        if "messages" in payload:
            assert payload["provider"]["ignore"] == ["openai/flex"]
            assert payload["provider"]["max_price"] == {"prompt": .5, "completion": 2.0}
            value = Enrichment(domain="Deployment", priority="High", decisions=["Read-only"], action_items=[])
            body = {"choices": [{"finish_reason": "stop", "message": {"content": value.model_dump_json()}}]}
        else:
            assert payload["dimensions"] == 1536
            body = {"data": [{"index": 0, "embedding": [1.0] * 1536}]}
        return httpx.Response(200, json={**body, "usage": {"cost": .0001}})
    transport = live.MeteredTransport
    monkeypatch.setattr(live, "MeteredTransport", lambda ledger, label: transport(ledger, label, httpx.MockTransport(upstream)))
    ledger = live.BudgetLedger(tmp_path / "ledger.json", 40)
    report = tmp_path / "report.json"
    # The current default review model may be changed by the selection task.
    settings.openrouter_model = settings.openrouter_review_model = "openai/gpt-4.1-mini"
    assert await live.execute("smoke", settings, ledger, tmp_path / "smoke", report) == 0
    assert len(dispatched) == len(ledger.value["attempts"]) == 2
    assert ledger.accounted() == pytest.approx(.0002)
    saved = report.read_text(encoding="utf-8")
    assert settings.openrouter_api_key.get_secret_value() not in saved
    assert json.loads(saved)["embedding_dimensions"] == 1536


async def test_ingestion_repeat_makes_zero_additional_calls_and_preserves_all_versions(settings, store, provider):
    expected = []
    settings.corpus_dir.mkdir()
    for index in range(24):
        path = settings.corpus_dir / f"fictional-{index}.md"
        path.write_text(f"# Fictional {index}\n\nAuthor: Avery\nDate: 2026-09-20\nAttendees: Avery\n\nDecision: Keep the pilot read-only.\n", encoding="utf-8")
        expected.append({"filename": path.name, "sha256": live.sha(path), "author": "Avery", "attendees": ["Avery"], "date": "2026-09-20"})
    class CountingLedger:
        @property
        def value(self):
            return {"attempts": provider.calls}
    first = await live.audit_ingestion(settings, store, provider, CountingLedger(), expected)
    assert first["passed"] and first["first_ingestion"]["ingested"] == 24
    assert first["repeat_ingestion"]["unchanged"] == 24 and first["repeat_provider_requests"] == 0
    before_ids = {row["id"] for row in live.documents(store)}
    # A profile change legitimately creates versions while preserving old proof.
    settings.openrouter_model = "openai/gpt-4.1"
    second = await live.audit_ingestion(settings, store, provider, CountingLedger(), expected)
    assert second["passed"] and second["versions_checked"] == 48
    assert before_ids.issubset({row["id"] for row in live.documents(store)})


async def test_server_uses_isolated_store_metered_provider_loopback_and_no_schedule(settings, tmp_path, monkeypatch):
    import uvicorn
    settings.openrouter_embedding_dimensions = 1536
    settings.openrouter_model = settings.openrouter_review_model = "openai/gpt-4.1-mini"
    settings.daily_evaluation = True  # Helper must explicitly override this.
    clone = Store(tmp_path / "isolated")
    monkeypatch.setattr(live, "manifest", lambda _: [])
    monkeypatch.setattr(live, "clone_canonical", lambda *_: clone)
    served = []
    class Server:
        def __init__(self, config):
            self.config = config
        async def serve(self):
            config = self.config
            assert config.host == "127.0.0.1" and config.port == 8011
            assert config.app.state.settings.data_dir == clone.data_dir
            assert not config.app.state.settings.daily_evaluation
            assert isinstance(config.app.state.service.provider, live.BenchmarkRouter)
            async with config.app.router.lifespan_context(config.app):
                served.append(config.app)
    monkeypatch.setattr(uvicorn, "Server", Server)
    ledger = live.BudgetLedger(tmp_path / "ledger.json", 40)
    report = tmp_path / "server.json"
    assert await live.execute("serve", settings, ledger, tmp_path / "unused", report) == 0
    assert len(served) == 1 and not ledger.value["attempts"]
    assert not settings.data_dir.exists()
    assert json.loads(report.read_text(encoding="utf-8"))["passed"] is None


@pytest.mark.parametrize("entrypoint", [["-m", "scripts.revision_live"], ["scripts/revision_live.py"]])
def test_help_does_not_read_credentials_or_make_calls(entrypoint):
    result = subprocess.run([sys.executable, *entrypoint, "--help"], cwd=live.ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "smoke" in result.stdout and "127.0.0.1:8011" in result.stdout
