import pytest

from app.provider import ProviderError
from app.service import KnowledgeService


async def test_supported_answer_is_grounded_and_persisted(settings, store, provider, ingested):
    answer = await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert answer.status == "answered"
    assert answer.claims[0].citations[0].chunk_id == answer.evidence[0].chunk_id
    assert answer.evidence[0].author == "Elena Rivera"
    assert answer.evidence[0].domain == "Atlas release governance"
    assert store.get_query(answer.query_id) == answer.model_dump()
    assert store.reviews()["items"] == []


@pytest.mark.parametrize("mode", ["fabricated_id", "fabricated_quote"])
async def test_invalid_citation_repair_is_bounded_and_never_persisted(mode, settings, store, provider, ingested):
    provider.mode = mode
    with pytest.raises(ProviderError, match="citation"):
        await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert len([call for call in provider.calls if call[0] == "DraftAnswer"]) == 2
    assert store.reviews()["items"] == []
    assert store.metrics()["query_count"] == 0


async def test_failed_support_check_abstains_and_routes_only_source_people(settings, store, provider, ingested):
    provider.supported = False
    answer = await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert answer.status == "needs_routing"
    assert answer.claims == []
    assert {route.recipient for route in answer.routing} == {"Elena Rivera", "Marcus Chen"}
    assert len(store.reviews("gap")["items"]) == 1


async def test_conflicts_are_partial_and_keep_evidence(settings, store, provider, ingested):
    provider.mode = "conflict"
    answer = await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert answer.status == "partial"
    assert answer.claims and answer.evidence and answer.routing


async def test_related_gap_has_evidence_and_draft(settings, store, provider, ingested):
    provider.mode = "gap"
    answer = await KnowledgeService(settings, store, provider).query("When is Atlas approval due?")
    assert answer.status == "needs_routing"
    assert answer.evidence
    assert "When is Atlas approval due?" in answer.routing[0].draft_question
    assert answer.routing[0].evidence_ids == [answer.evidence[0].chunk_id]


async def test_irrelevant_evidence_gate_prevents_invented_experts(settings, store, provider, ingested):
    provider.mode = "unrelated"
    answer = await KnowledgeService(settings, store, provider).query("What is the best recipe for muffins?")
    assert answer.status == "needs_routing"
    assert answer.evidence == answer.claims == answer.routing == []


async def test_no_retrieval_evidence_skips_generation(settings, store, provider, ingested):
    answer = await KnowledgeService(settings, store, provider).query("Explain galactic quasars.")
    assert answer.status == "needs_routing"
    assert not answer.routing
    assert not [call for call in provider.calls if call[0] == "DraftAnswer"]


async def test_semantic_paraphrase_retrieves_with_no_lexical_match(settings, store, provider, ingested):
    answer = await KnowledgeService(settings, store, provider).query("Is a person required to authorize go-live?")
    assert answer.status == "answered"
    assert answer.evidence[0].filename == "atlas.md"


async def test_evaluations_do_not_pollute_user_metrics_or_gap_queue(settings, store, provider, ingested):
    provider.mode = "gap"
    await KnowledgeService(settings, store, provider).query("When is Atlas approval due?", evaluation=True)
    assert store.metrics()["query_count"] == 0
    assert store.reviews()["items"] == []


async def test_embedding_model_mismatch_is_operational_failure(settings, store, provider, ingested):
    settings.openrouter_embedding_model = "different/model"
    with pytest.raises(ProviderError, match="Re-ingest"):
        await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert store.reviews()["items"] == []


async def test_citation_repair_can_recover_without_persisting_bad_attempt(settings, store, provider, ingested):
    original = provider.structured
    attempts = 0
    async def repair(schema, system, content, **kwargs):
        nonlocal attempts
        if schema.__name__ == "DraftAnswer":
            if attempts:
                assert content["previous_response"]["claims"]
                assert content["validation_issues"][0]["reason"].startswith("unknown quote_id")
            provider.mode = "fabricated_quote" if attempts == 0 else "answered"
            attempts += 1
        return await original(schema, system, content, **kwargs)
    provider.structured = repair
    answer = await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert answer.status == "answered"
    assert attempts == 2
    assert store.metrics()["query_count"] == 1


async def test_incomplete_verification_is_an_operational_error(settings, store, provider, ingested):
    from app.models import SupportCheck
    original = provider.structured
    async def incomplete(schema, system, content, **kwargs):
        if schema is SupportCheck:
            return SupportCheck(checks=[])
        return await original(schema, system, content, **kwargs)
    provider.structured = incomplete
    with pytest.raises(ProviderError, match="verification response was incomplete"):
        await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert store.metrics()["query_count"] == 0
    assert store.reviews()["items"] == []


async def test_supported_absence_statement_is_routed_when_requested_value_is_unknown(settings, store, provider, source):
    from app.ingestion import ingest_file
    from app.models import CoverageAssessment, DraftAnswer
    source.write_text("# Launch review\n\nAuthor: Elena Rivera\nDate: 2026-08-01\n\nNo execution date has been approved.\n", encoding="utf-8")
    await ingest_file(source, store=store, provider=provider, settings=settings)
    original = provider.structured
    async def absence(schema, system, content, **kwargs):
        if schema is DraftAnswer:
            raise AssertionError("A missing value must be routed before answer generation.")
        if schema is CoverageAssessment:
            assert "claims" not in content and "request_coverage" not in content
            assert kwargs["model"] == settings.openrouter_review_model
            chunk = content["evidence"][0]["chunk_id"]
            return CoverageAssessment(relevant_chunk_ids=[chunk], coverage=[{"requested_component": "approved execution date", "provided_value": None, "evidence_state": "missing", "supporting_chunk_ids": [chunk]}])
        return await original(schema, system, content, **kwargs)
    provider.structured = absence
    answer = await KnowledgeService(settings, store, provider).query("What is the approved execution date?")
    assert answer.status == "needs_routing"
    assert not answer.claims and answer.evidence and answer.routing
    assert len(store.reviews("gap")["items"]) == 1


async def test_verifier_can_downgrade_generator_overconfidence(settings, store, provider, ingested):
    from app.models import CoverageAssessment
    original = provider.structured
    async def partial(schema, system, content, **kwargs):
        if schema is CoverageAssessment:
            chunk = content["evidence"][0]["chunk_id"]
            return CoverageAssessment(relevant_chunk_ids=[chunk], coverage=[{"requested_component": "approval", "provided_value": "Human approval", "evidence_state": "present", "supporting_chunk_ids": [chunk]}, {"requested_component": "date", "provided_value": None, "evidence_state": "missing", "supporting_chunk_ids": []}])
        return await original(schema, system, content, **kwargs)
    provider.structured = partial
    answer = await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert answer.status == "partial"
    assert answer.claims and answer.routing


async def test_coverage_cannot_reference_unknown_source(settings, store, provider, ingested):
    from app.models import CoverageAssessment
    original = provider.structured
    async def unknown_source(schema, system, content, **kwargs):
        if schema is CoverageAssessment:
            return CoverageAssessment(relevant_chunk_ids=[], coverage=[{"requested_component": "approval", "provided_value": "Human approval", "evidence_state": "present", "supporting_chunk_ids": ["fabricated"]}])
        return await original(schema, system, content, **kwargs)
    provider.structured = unknown_source
    with pytest.raises(ProviderError, match="unknown evidence"):
        await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert store.metrics()["query_count"] == 0
    assert store.reviews()["items"] == []


async def test_coverage_is_answer_blind_and_review_calls_use_separate_model(settings, store, provider, ingested):
    from app.models import CoverageAssessment, DraftAnswer, SupportCheck
    original = provider.structured
    calls = []
    async def observed(schema, system, content, **kwargs):
        calls.append(schema)
        if schema is CoverageAssessment:
            assert set(content) == {"question", "evidence"}
            assert kwargs["model"] == settings.openrouter_review_model
        if schema is DraftAnswer:
            assert "request_coverage" in content
            assert not kwargs.get("model")
        if schema is SupportCheck:
            assert content["claims"]
            assert kwargs["model"] == settings.openrouter_review_model
        return await original(schema, system, content, **kwargs)
    provider.structured = observed
    await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert calls == [CoverageAssessment, DraftAnswer, SupportCheck]


def test_citation_catalog_resolves_exact_original_contiguous_spans():
    from app.models import DraftAnswer, Evidence
    from app.service import citation_spans, valid_claims
    text = "Unsigned estimate.\n\nProposed fee\n\nThe fee is USD 1,000."
    evidence = Evidence(chunk_id="source", document_id="doc", filename="proposal.docx", title="Proposal", author=None, attendees=[], date=None, domain="Commercial", priority=None, locator="Paragraphs 1-3", text=text)
    spans = citation_spans(text)
    assert [span["text"] for span in spans] == ["Unsigned estimate.", "Proposed fee", "The fee is USD 1,000."]
    draft = DraftAnswer(status="answered", claims=[{"text": "The unsigned estimate is USD 1,000.", "citations": [{"chunk_id": "source", "quote_id": "p1"}, {"chunk_id": "source", "quote_id": "p3"}]}], missing_information="", conflicting_evidence=False, relevant_chunk_ids=["source"])
    result = valid_claims(draft, [evidence])
    assert [citation.quote for citation in result[0].citations] == ["Unsigned estimate.", "The fee is USD 1,000."]
    assert all(citation.quote in text for citation in result[0].citations)
