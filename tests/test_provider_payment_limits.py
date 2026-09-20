import asyncio
import json

import httpx
import pytest

from app.provider import OpenRouter, ProviderError


def rejection(metadata, headers=None):
    return httpx.Response(402, headers=headers, json={"error": {
        "message": "private provider detail test-only-key",
        "metadata": {**metadata, "balance": "test-only-key", "raw": "secret"},
    }})


@pytest.mark.parametrize("retry_after,expected", [("7.5", 7.5), ("9999", 60), ("nan", 2), ("bad", 2), ("-1", 2)])
async def test_transient_payment_capacity_recovers_with_bounded_retry_after(retry_after, expected, settings, store, monkeypatch):
    calls, sleeps = [], []
    async def no_sleep(delay):
        sleeps.append(delay)
    monkeypatch.setattr("app.provider.asyncio.sleep", no_sleep)
    def handler(request):
        calls.append(request)
        return rejection({"limit_source": "openrouter_in_flight_budget", "reason": "in_flight_budget_exhausted"}, {"Retry-After": retry_after}) if len(calls) == 1 else httpx.Response(200, json={"ok": True})
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    assert await provider.request("chat/completions", {"model": "candidate"}) == {"ok": True}
    assert len(calls) == 2 and sleeps == [expected]
    with store.connect() as conn:
        events = [json.loads(row[0]) for row in conn.execute("SELECT payload FROM events WHERE kind='provider'")]
    assert events[0]["limit_source"] == "openrouter_in_flight_budget"
    assert events[0]["failure_category"] == "capacity"
    assert "test-only-key" not in json.dumps(events) and "secret" not in json.dumps(events)
    await provider.close()


async def test_capacity_retry_exhaustion_is_operational_failure(settings, store, monkeypatch):
    calls, sleeps = [], []
    async def no_sleep(delay):
        sleeps.append(delay)
    monkeypatch.setattr("app.provider.asyncio.sleep", no_sleep)
    def handler(request):
        calls.append(request)
        return rejection({"limit_source": "openrouter_in_flight_budget"})
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as error:
        await provider.request("chat/completions", {"model": "candidate"})
    assert error.value.category == "capacity" and error.value.status_code == 503
    assert len(calls) == 3 and sleeps == [2, 4]
    await provider.close()


@pytest.mark.parametrize("metadata,category,phrase", [
    ({"limit_source": "openrouter_key_limit"}, "key_limit", "key's spending allowance"),
    ({"limit_source": "openrouter_credits", "reason": "weight_exceeds_budget"}, "request_budget", "estimates this request"),
    ({"limit_source": "openrouter_credits"}, "credits", "Check account credits"),
    ({"limit_source": "test-only-key", "reason": "test-only-key"}, "credits", "Check account credits"),
    ({"limit_source": ["openrouter_in_flight_budget"]}, "credits", "Check account credits"),
])
async def test_nontransient_payment_classifications_do_not_retry(metadata, category, phrase, settings, store):
    calls = []
    def handler(request):
        calls.append(request)
        return rejection(metadata)
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError) as error:
        await provider.request("chat/completions", {"model": "candidate"})
    assert error.value.category == category and phrase in str(error.value)
    assert len(calls) == 1
    with store.connect() as conn:
        event_text = " ".join(row[0] for row in conn.execute("SELECT payload FROM events"))
    assert "test-only-key" not in event_text + str(error.value)
    await provider.close()


@pytest.mark.parametrize("body", ['not json', '[]', '{"error":null}', '{"error":{"metadata":[]}}', '{"error":{"metadata":{"limit_source":"openrouter_in_flight_budget","limit_source":"openrouter_key_limit"}}}'])
async def test_malformed_payment_error_is_safe_generic_failure(body, settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(402, text=body)))
    with pytest.raises(ProviderError) as error:
        await provider.request("chat/completions", {"model": "candidate"})
    assert error.value.category == "credits"
    assert "Add credits" not in str(error.value)
    await provider.close()


async def test_operation_cancellation_interrupts_capacity_wait(settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: rejection(
        {"limit_source": "openrouter_in_flight_budget"}, {"Retry-After": "60"})))
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(.02):
            await provider.request("chat/completions", {"model": "candidate"})
    assert store.metrics()["provider_failures"] == 1
    await provider.close()
