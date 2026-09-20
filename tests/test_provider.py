import json

import httpx
import pytest
from pydantic import ValidationError

from app.models import Citation, Claim, Enrichment
from app.provider import OpenRouter, ProviderError


def chat_response(content):
    return {"id": "test-request", "choices": [{"finish_reason": "stop", "message": {"content": content}}], "usage": {"total_tokens": 12}}


async def test_structured_output_request_and_validation(settings, store):
    def handler(request):
        assert request.headers["authorization"] == "Bearer test-only-key"
        payload = json.loads(request.content)
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
        return httpx.Response(200, json=chat_response(json.dumps({"domain": "Atlas", "priority": None, "decisions": [], "action_items": []})))
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    result = await provider.structured(Enrichment, "test", {"text": "source"})
    assert result.domain == "Atlas"
    assert store.metrics()["provider_tokens"] == 12
    await provider.close()


async def test_optional_null_usage_does_not_break_success(settings, store):
    response = chat_response(json.dumps({"domain": "Atlas", "priority": None, "decisions": [], "action_items": []}))
    response["usage"] = None
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)))
    assert (await provider.structured(Enrichment, "test", {"text": "source"})).domain == "Atlas"
    assert store.metrics()["provider_tokens"] == 0
    await provider.close()


async def test_explicit_review_model_overrides_generation_model(settings, store):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == settings.openrouter_review_model
        return httpx.Response(200, json=chat_response(json.dumps({"domain": "Atlas", "priority": None, "decisions": [], "action_items": []})))
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    await provider.structured(Enrichment, "test", {"text": "source"}, model=settings.openrouter_review_model)
    await provider.close()


@pytest.mark.parametrize("response", [
    {"error": {"code": 500, "message": "secret provider error test-only-key"}},
    {"choices": []},
    chat_response("not-json"),
    chat_response('{"domain":"Atlas","priority":null,"decisions":[],"action_items":[],"extra":"bad"}'),
    {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
])
async def test_invalid_body_is_safe_provider_failure(response, settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)))
    with pytest.raises(ProviderError) as error:
        await provider.structured(Enrichment, "test", {"text": "source"})
    assert "test-only-key" not in str(error.value)
    with store.connect() as conn:
        events = " ".join(row[0] for row in conn.execute("SELECT payload FROM events"))
    assert "test-only-key" not in events
    await provider.close()


@pytest.mark.parametrize("failure", ["rate_limit", "timeout", "tls_record"])
async def test_transient_errors_retry_at_most_three_times(failure, settings, store, monkeypatch):
    attempts = []
    async def no_sleep(delay):
        pass
    monkeypatch.setattr("app.provider.asyncio.sleep", no_sleep)
    def handler(request):
        attempts.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("do not leak secret", request=request)
        if failure == "tls_record":
            import ssl
            raise ssl.SSLError("bad record mac; do not leak provider details")
        return httpx.Response(429, headers={"Retry-After": "0"})
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError):
        await provider.embeddings(["text"])
    assert len(attempts) == 3
    assert store.metrics()["provider_failures"] == 3
    await provider.close()


async def test_certificate_verification_failure_is_not_bypassed_or_retried(settings, store):
    import ssl
    calls = []
    def handler(request):
        calls.append(request)
        raise ssl.SSLCertVerificationError("certificate verification failed")
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="certificate validation"):
        await provider.embeddings(["text"])
    assert len(calls) == 1
    await provider.close()


async def test_retry_can_recover(settings, store, monkeypatch):
    attempts = []
    async def no_sleep(delay):
        pass
    monkeypatch.setattr("app.provider.asyncio.sleep", no_sleep)
    def handler(request):
        attempts.append(request)
        return httpx.Response(503) if len(attempts) == 1 else httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 0, 0]}]})
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    assert await provider.embeddings(["text"]) == [[1, 0, 0]]
    assert len(attempts) == 2
    await provider.close()


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404])
async def test_account_and_request_errors_are_not_retried(status, settings, store):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "test-only-key"})
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError):
        await provider.embeddings(["text"])
    assert len(calls) == 1
    await provider.close()


@pytest.mark.parametrize("data", [
    [],
    [{"index": 0, "embedding": [1, 0]}],
    [{"index": 1, "embedding": [1, 0, 0]}],
    [{"index": 0, "embedding": [0, 0, 0]}],
    [{"index": 0, "embedding": ["NaN", 0, 1]}],
])
async def test_invalid_embeddings_fail_closed(data, settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": data})))
    with pytest.raises(ProviderError, match="invalid vectors"):
        await provider.embeddings(["source"])
    await provider.close()


def test_whitespace_only_claims_and_quotes_are_invalid():
    with pytest.raises(ValidationError):
        Citation(chunk_id="x", quote=" \n ")
    with pytest.raises(ValidationError):
        Claim(text="   ", citations=[{"chunk_id": "x", "quote": "source"}])


@pytest.mark.parametrize("value,state,ids", [("unknown", "missing", []), (None, "present", ["source"]), ("agreed value", "present", [])])
def test_inconsistent_component_coverage_fails_closed(value, state, ids):
    from app.models import ComponentCoverage
    with pytest.raises(ValidationError):
        ComponentCoverage(requested_component="approved value", provided_value=value, evidence_state=state, supporting_chunk_ids=ids)
