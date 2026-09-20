from app.models import CoverageAssessment, SupportCheck
from app.service import KnowledgeService


async def test_supported_but_incomplete_answer_is_partial(settings, store, provider, ingested):
    original = provider.structured
    async def omitted_component(schema, system, content, **kwargs):
        if schema is CoverageAssessment:
            chunk = content["evidence"][0]["chunk_id"]
            return CoverageAssessment(relevant_chunk_ids=[chunk], coverage=[
                {"requested_component": "production approval", "provided_value": "human approval", "evidence_state": "present", "supporting_chunk_ids": [chunk]},
                {"requested_component": "audit log retention", "provided_value": "90 days", "evidence_state": "present", "supporting_chunk_ids": [chunk]},
            ])
        if schema is SupportCheck:
            # The draft only answers approval. That fact is true, but it omits
            # the requested duration even though the source contains it.
            return SupportCheck(checks=[{"claim_index": 0, "supported": True}], answer_complete=False)
        return await original(schema, system, content, **kwargs)
    provider.structured = omitted_component
    answer = await KnowledgeService(settings, store, provider).query("What approval does Atlas require and how long must audit logs be retained?")
    assert answer.status == "partial"
    assert len(answer.claims) == 1 and answer.routing
    assert store.reviews("gap")["items"][0]["query_id"] == answer.query_id


async def test_support_judge_cannot_borrow_uncited_coverage_values(settings, store, provider, ingested):
    original = provider.structured
    observed = []
    async def inspect_context(schema, system, content, **kwargs):
        if schema is SupportCheck:
            observed.append(content)
            assert "evidence" not in content
            assert all(set(component) == {"requested_component", "evidence_state"} for component in content["request_coverage"])
            for claim in content["claims"]:
                assert {item["chunk_id"] for item in claim["cited_source_context"]} == {item["chunk_id"] for item in claim["citations"]}
        return await original(schema, system, content, **kwargs)
    provider.structured = inspect_context
    await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert len(observed) == 1


async def test_one_support_repair_can_recover_without_saving_rejected_draft(settings, store, provider, ingested):
    original = provider.structured
    reviews = 0
    async def repairable(schema, system, content, **kwargs):
        nonlocal reviews
        if schema is SupportCheck:
            reviews += 1
            return SupportCheck(checks=[{"claim_index": 0, "supported": reviews == 2}], answer_complete=True)
        if schema.__name__ == "DraftAnswer" and reviews:
            assert content["support_feedback"]["unsupported_claim_indexes"] == [0]
        return await original(schema, system, content, **kwargs)
    provider.structured = repairable
    answer = await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert answer.status == "answered" and reviews == 2
    assert store.metrics()["query_count"] == 1 and store.reviews()["items"] == []


async def test_support_repair_is_bounded_and_repeated_failures_are_removed(settings, store, provider, ingested):
    provider.supported = False
    answer = await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert answer.status == "needs_routing" and not answer.claims
    assert sum(name == "DraftAnswer" for name, _ in provider.calls) == 2
    assert sum(name == "SupportCheck" for name, _ in provider.calls) == 2
    assert store.metrics()["query_count"] == 1
