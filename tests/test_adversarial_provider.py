"""Hostile upstream payloads must become safe, bounded operational errors."""
import json

import httpx
import pytest

from app.models import Enrichment, SupportCheck
from app.provider import OpenRouter, ProviderError


def completion(content, reason="stop"):
    return {"choices": [{"finish_reason": reason, "message": {"content": content}}]}


GOOD_CONTENT = json.dumps({"domain": "Atlas", "priority": None, "decisions": [], "action_items": []})


@pytest.mark.parametrize("response", [
    {"choices": None}, {"choices": {}}, {"choices": "oops"}, {"choices": [None]},
    {"choices": [False]}, {"choices": [[]]}, {"choices": [{}]},
    {"choices": [{"message": None}]}, {"choices": [{"message": "secret test-only-key"}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": None}}]},
    {"choices": [{"finish_reason": "stop", "message": {"content": {}}}]},
    completion(GOOD_CONTENT, "content_filter"), completion(GOOD_CONTENT, "tool_calls"),
    completion(GOOD_CONTENT, None), completion("[" * 1500 + "]" * 1500),
    completion('{"domain":"Atlas","domain":"forged","priority":null,"decisions":[],"action_items":[]}'),
])
async def test_structural_chat_corruption_never_escapes_as_server_error(response, settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)))
    try:
        with pytest.raises(ProviderError) as failure:
            await provider.structured(Enrichment, "test", {})
        assert failure.value.category == "invalid_response"
        assert "test-only-key" not in str(failure.value)
        with store.connect() as conn:
            assert "test-only-key" not in " ".join(row[0] for row in conn.execute("SELECT payload FROM events"))
    finally:
        await provider.close()


@pytest.mark.parametrize("checks", [
    [{"claim_index": False, "supported": True}],
    [{"claim_index": "0", "supported": True}],
    [{"claim_index": 0, "supported": "true"}],
    [{"claim_index": 0, "supported": 1}],
    [{"claim_index": 0.0, "supported": True}],
])
async def test_verifier_rejects_type_coercion(checks, settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=completion(json.dumps({"checks": checks, "answer_complete": True})))))
    try:
        with pytest.raises(ProviderError) as failure:
            await provider.structured(SupportCheck, "test", {})
        assert failure.value.category == "invalid_response"
    finally:
        await provider.close()


async def test_duplicate_verifier_support_keys_fail_closed(settings, store):
    body = '{"checks":[{"claim_index":0,"supported":false,"supported":true}],"answer_complete":true}'
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=completion(body))))
    try:
        with pytest.raises(ProviderError) as failure:
            await provider.structured(SupportCheck, "test", {})
        assert failure.value.category == "invalid_response"
    finally:
        await provider.close()


@pytest.mark.parametrize("entries", [
    None, {}, "100", [None], [False], [{}],
    [{"index": False, "embedding": [1, 0, 0]}],
    [{"index": "0", "embedding": [1, 0, 0]}],
    [{"index": 0.0, "embedding": [1, 0, 0]}],
    [{"index": 0, "embedding": "100"}],
    [{"index": 0, "embedding": [True, False, False]}],
    [{"index": 0, "embedding": ["1", "0", "0"]}],
    [{"index": 0, "embedding": [None, 0, 1]}],
    [{"index": 0, "embedding": [10 ** 400, 0, 1]}],
    [{"index": 0, "embedding": [1, 0, 0]}, {"index": 0, "embedding": [1, 0, 0]}],
])
async def test_embedding_corruption_is_never_coerced_or_cached(entries, settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": entries})))
    try:
        with pytest.raises(ProviderError) as failure:
            await provider.embeddings(["source"])
        assert failure.value.category == "invalid_embedding"
        with store.connect() as conn:
            assert conn.execute("SELECT count(*) FROM embedding_cache").fetchone()[0] == 0
    finally:
        await provider.close()


async def test_embedding_order_is_resolved_by_valid_indexes(settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"index": 1, "embedding": [0, 1, 0]}, {"index": 0, "embedding": [1, 0, 0]}]})))
    try:
        assert await provider.embeddings(["first", "second"]) == [[1, 0, 0], [0, 1, 0]]
    finally:
        await provider.close()


@pytest.mark.parametrize("body", [
    '{"data":[],"data":[{"index":0,"embedding":[1,0,0]}]}',
    '{"data":[{"index":0,"embedding":[NaN,0,1]}]}',
    "[" * 1500 + "]" * 1500,
], ids=["duplicate-keys", "non-finite-number", "nested-array"])
async def test_ambiguous_or_nonstandard_provider_json_is_rejected(body, settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body)))
    try:
        with pytest.raises(ProviderError) as failure:
            await provider.embeddings(["source"])
        assert failure.value.category == "invalid_response"
    finally:
        await provider.close()


@pytest.mark.parametrize("request_id", ["test-only-key", "gen-test-only-key", "question content and credentials test-only-key"])
async def test_provider_cannot_echo_credentials_into_request_id_telemetry(request_id, settings, store):
    response = {"id": request_id, "data": [{"index": 0, "embedding": [1, 0, 0]}]}
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)))
    try:
        await provider.embeddings(["source"])
        with store.connect() as conn:
            assert "test-only-key" not in " ".join(row[0] for row in conn.execute("SELECT payload FROM events"))
    finally:
        await provider.close()


async def test_retry_after_is_bounded_and_authorization_never_forwarded(settings, store, monkeypatch):
    delays = []
    requests = []

    async def remember_delay(delay):
        delays.append(delay)

    def handler(request):
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": "9999999"})

    monkeypatch.setattr("app.provider.asyncio.sleep", remember_delay)
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ProviderError):
            await provider.embeddings(["source"])
        assert len(requests) == 3
        assert delays == [5, 5]
        assert all(request.url.host == "openrouter.ai" for request in requests)
    finally:
        await provider.close()


async def test_redirect_cannot_send_credentials_to_third_party(settings, store):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(307, headers={"Location": "https://attacker.invalid/collect"})

    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ProviderError):
            await provider.embeddings(["source"])
        assert len(requests) == 1
        assert requests[0].url.host == "openrouter.ai"
    finally:
        await provider.close()


@pytest.mark.parametrize("retry_after", ["NaN", "Infinity", "-Infinity", "not-a-duration", "-99999"])
async def test_invalid_retry_after_never_escapes_or_creates_unbounded_sleep(retry_after, settings, store, monkeypatch):
    import math
    delays = []

    async def remember_delay(delay):
        assert math.isfinite(delay) and 0 < delay <= 5
        delays.append(delay)

    monkeypatch.setattr("app.provider.asyncio.sleep", remember_delay)
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={"Retry-After": retry_after})))
    try:
        with pytest.raises(ProviderError) as failure:
            await provider.embeddings(["source"])
        assert failure.value.category == "unavailable"
        assert len(delays) == 2
        assert store.metrics()["provider_failures"] == 3
    finally:
        await provider.close()
