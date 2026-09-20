import json

import httpx
import pytest
from pydantic import ValidationError

from app.config import ModelOptions, Settings
from app.models import Enrichment
from app.provider import OpenRouter


def response(usage=None):
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
        "domain": "Release governance", "priority": None, "decisions": [], "action_items": []
    })}}], "usage": usage}


async def test_reasoning_model_omits_unsupported_temperature_without_weakening_schema(settings, store):
    model = "openai/gpt-5.6-luna"
    settings = settings.model_copy(update={"openrouter_model": model, "openrouter_model_options": {
        model: ModelOptions(reasoning_effort="medium", max_output_tokens=12000,
                            provider_order=["openai"], provider_ignore=["openai/flex"], allow_fallbacks=False)
    }})
    def handler(request):
        payload = json.loads(request.content)
        assert "temperature" not in payload
        assert payload["reasoning"] == {"effort": "medium"}
        assert payload["max_tokens"] == 12000
        assert payload["provider"] == {"require_parameters": True, "order": ["openai"], "ignore": ["openai/flex"], "allow_fallbacks": False}
        assert payload["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(200, json=response())
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    assert (await provider.structured(Enrichment, "Classify", {"text": "Source"})).domain == "Release governance"
    await provider.close()


async def test_generation_and_review_options_do_not_leak_between_model_ids(settings, store):
    review = "anthropic/claude-fable-5.1"
    settings = settings.model_copy(update={"openrouter_model_options": {
        review: ModelOptions(reasoning_effort="high", max_output_tokens=8000)
    }})
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=response())
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(handler))
    await provider.structured(Enrichment, "Classify", {})
    await provider.structured(Enrichment, "Classify", {}, model=review)
    assert calls[0]["temperature"] == 0 and "reasoning" not in calls[0]
    assert calls[0]["max_tokens"] == 4000
    assert "temperature" not in calls[1] and calls[1]["reasoning"] == {"effort": "high"}
    await provider.close()


@pytest.mark.parametrize("options", [
    {"temperature": float("nan")}, {"temperature": 3}, {"reasoning_effort": "invented"},
    {"max_output_tokens": True}, {"max_output_tokens": 100000000},
    {"headers": {"Authorization": "unsafe"}}, {"allow_fallbacks": "false"},
])
def test_model_configuration_rejects_unsafe_or_unbounded_options(options):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, openrouter_model_options={"candidate": options})


@pytest.mark.parametrize("cost", [.0123, "secret-cost", -1, True, 10 ** 500])
async def test_cost_telemetry_is_numeric_and_does_not_log_provider_text(cost, settings, store):
    provider = OpenRouter(settings, store, transport=httpx.MockTransport(lambda request: httpx.Response(
        200, json=response({"total_tokens": 15, "prompt_tokens": 10, "completion_tokens": 5,
                            "completion_tokens_details": {"reasoning_tokens": 2}, "cost": cost})
    )))
    await provider.structured(Enrichment, "Classify", {})
    with store.connect() as conn:
        event = json.loads(conn.execute("SELECT payload FROM events WHERE kind='provider'").fetchone()[0])
    assert event["prompt_tokens"] == 10 and event["reasoning_tokens"] == 2
    assert (event.get("cost_usd") == .0123) if cost == .0123 else "cost_usd" not in event
    assert "secret-cost" not in json.dumps(event)
    await provider.close()
