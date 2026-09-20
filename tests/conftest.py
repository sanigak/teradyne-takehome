from pathlib import Path

import pytest

from app.config import Settings
from app.models import CoverageAssessment, DraftClaim, DraftAnswer, Enrichment, SupportCheck
from app.store import Store


SOURCE_TEXT = """# Atlas release meeting

Author: Elena Rivera
Date: 2026-08-01
Attendees: Elena Rivera; Marcus Chen

Atlas requires human approval before production deployment.
Decision: Atlas must retain audit logs for 90 days.
Action: Marcus Chen will document the rollback procedure.
"""


class FakeProvider:
    """Test-only deterministic transport substitute; never enabled in application code."""
    def __init__(self):
        self.calls = []
        self.mode = "answered"
        self.supported = True
        self.failed_enrichment = False

    async def close(self):
        pass

    async def embeddings(self, texts):
        self.calls.append(("embeddings", texts))
        return [[-1.0, 0.0, 0.0] if "galactic" in text.lower() else [1.0, 0.0, 0.0] for text in texts]

    async def structured(self, schema, system, content, **kwargs):
        from app.provider import ProviderError
        self.calls.append((schema.__name__, content))
        if schema is Enrichment:
            if self.failed_enrichment:
                raise ProviderError("Temporary provider failure.", category="unavailable", status_code=503)
            return Enrichment(domain="Atlas release governance", priority=None, decisions=["Retain audit logs for 90 days."], action_items=["Marcus Chen: document rollback procedure."])
        if schema is SupportCheck:
            return SupportCheck(checks=[{"claim_index": claim["claim_index"], "supported": self.supported} for claim in content["claims"]])
        if schema is CoverageAssessment:
            ids = [] if self.mode == "unrelated" else [content["evidence"][0]["chunk_id"]]
            missing = self.mode in {"unrelated", "gap"}
            return CoverageAssessment(relevant_chunk_ids=ids, coverage=[{"requested_component": "approval", "provided_value": None if missing else "Human approval", "evidence_state": "missing" if missing else "conflicting" if self.mode == "conflict" else "present", "supporting_chunk_ids": ids}])
        assert schema is DraftAnswer
        evidence = content["evidence"]
        if self.mode == "unrelated":
            return DraftAnswer(status="needs_routing", claims=[], missing_information="No relevant evidence.", conflicting_evidence=False, relevant_chunk_ids=[])
        if self.mode == "gap":
            return DraftAnswer(status="needs_routing", claims=[], missing_information="The approval date is absent.", conflicting_evidence=False, relevant_chunk_ids=[evidence[0]["chunk_id"]])
        chunk_id = evidence[0]["chunk_id"]
        quote_id = next(span["quote_id"] for span in evidence[0]["citation_spans"] if "Atlas requires human approval before production deployment." in span["text"])
        if self.mode == "fabricated_id":
            chunk_id = "fabricated"
        if self.mode == "fabricated_quote":
            quote_id = "fabricated-span"
        return DraftAnswer(status="answered", claims=[DraftClaim(text="Atlas requires human approval before production deployment.", citations=[{"chunk_id": chunk_id, "quote_id": quote_id}])], missing_information="", conflicting_evidence=self.mode == "conflict", relevant_chunk_ids=[evidence[0]["chunk_id"]])


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, openrouter_api_key="test-only-key", data_dir=tmp_path / "runtime", corpus_dir=tmp_path / "corpus", evaluation_path=tmp_path / "evaluation.json", daily_evaluation=False, openrouter_embedding_dimensions=3)


@pytest.fixture
def store(settings):
    return Store(settings.data_dir)


@pytest.fixture
def provider():
    return FakeProvider()


@pytest.fixture
def source(settings):
    settings.corpus_dir.mkdir()
    path = settings.corpus_dir / "atlas.md"
    path.write_text(SOURCE_TEXT, encoding="utf-8")
    return path


@pytest.fixture
async def ingested(settings, store, provider, source):
    from app.ingestion import ingest_file
    return await ingest_file(source, store=store, provider=provider, settings=settings)
