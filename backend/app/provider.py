import asyncio
import json
import math
import ssl
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .config import Settings
from .store import Store

T = TypeVar("T", bound=BaseModel)


class ProviderError(Exception):
    def __init__(self, message: str, *, category="provider_error", status_code=502):
        self.category = category
        self.status_code = status_code
        super().__init__(message)


class OpenRouter:
    def __init__(self, settings: Settings, store: Store, *, transport=None):
        self.settings, self.store = settings, store
        self.client = httpx.AsyncClient(
            base_url=settings.openrouter_base_url.rstrip("/") + "/",
            headers={"Authorization": "Bearer " + settings.openrouter_api_key.get_secret_value()},
            timeout=settings.provider_timeout_seconds, transport=transport,
        )

    async def close(self):
        await self.client.aclose()

    async def request(self, endpoint: str, payload: dict):
        if not self.settings.configured:
            raise ProviderError("Set OPENROUTER_API_KEY in the server environment or project-root .env, then restart the service.", category="configuration", status_code=503)
        for attempt in range(3):
            started = time.monotonic()
            event = {"operation": endpoint, "model": payload["model"], "attempt": attempt + 1, "success": False}
            delay = 0.25 * (2 ** attempt)
            retryable = False
            try:
                response = await self.client.post(endpoint, json=payload)
                event["http_status"] = response.status_code
                if response.status_code in (401, 403):
                    raise ProviderError("OpenRouter rejected the credentials. Check OPENROUTER_API_KEY and account access.", category="credentials", status_code=503)
                if response.status_code == 402:
                    raise ProviderError("OpenRouter requires account credits. Add credits and retry.", category="credits", status_code=503)
                if response.status_code == 429 or response.status_code >= 500:
                    retryable = True
                    try:
                        delay = min(max(float(response.headers.get("retry-after", delay)), delay), 5)
                    except ValueError:
                        pass
                    raise ProviderError("OpenRouter is temporarily unavailable or rate limited. Retry shortly.", category="unavailable", status_code=503)
                if response.is_error:
                    raise ProviderError("OpenRouter rejected the request. Verify configured model names and provider support for structured output.", category="request")
                try:
                    data = response.json()
                except ValueError:
                    raise ProviderError("OpenRouter returned an unreadable response. Retry the request.", category="invalid_response") from None
                if not isinstance(data, dict) or data.get("error"):
                    raise ProviderError("OpenRouter returned an error response. Retry or check account and model availability.", category="body_error")
                usage = data.get("usage")
                tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
                event.update(success=True, total_tokens=tokens if isinstance(tokens, int) and tokens >= 0 else 0)
                # Only provider IDs, never response text, question content, or credentials.
                if isinstance(data.get("id"), str):
                    event["request_id"] = data["id"][:160]
                return data
            except ssl.SSLCertVerificationError:
                error = ProviderError("OpenRouter TLS certificate validation failed. Check the system trust configuration and network proxy.", category="tls_verification", status_code=503)
                event["failure_category"] = error.category
            except (httpx.RequestError, ssl.SSLError) as exc:
                retryable = True
                error = ProviderError("OpenRouter timed out or could not be reached. Check connectivity and retry.", category="network", status_code=503)
                event["failure_category"] = error.category
            except ProviderError as exc:
                error = exc
                event["failure_category"] = error.category
            finally:
                event["latency_ms"] = round((time.monotonic() - started) * 1000)
                self.store.event("provider", event)
            if not retryable or attempt == 2:
                raise error
            await asyncio.sleep(delay)
        raise AssertionError("Unreachable")

    async def structured(self, schema: type[T], system: str, content: dict, *, model: str | None = None) -> T:
        payload = {
            "model": model or self.settings.openrouter_model,
            "temperature": 0, "max_tokens": 4000, "stream": False,
            "provider": {"require_parameters": True},
            "response_format": {"type": "json_schema", "json_schema": {"name": schema.__name__, "strict": True, "schema": schema.model_json_schema()}},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(content, ensure_ascii=False)}],
        }
        data = await self.request("chat/completions", payload)
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") in ("length", "error") or choice["message"].get("refusal"):
                raise ValueError("Incomplete or refused")
            return schema.model_validate_json(choice["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError, ValidationError):
            self.store.event("validation_failure", {"schema": schema.__name__})
            raise ProviderError("The model returned an invalid or incomplete structured response. Retry the request.", category="invalid_response") from None

    async def embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = await self.request("embeddings", {"model": self.settings.openrouter_embedding_model, "input": texts, "encoding_format": "float", "dimensions": self.settings.openrouter_embedding_dimensions})
        try:
            entries = sorted(data["data"], key=lambda item: item["index"])
            if [item["index"] for item in entries] != list(range(len(texts))):
                raise ValueError("Embedding count mismatch")
            vectors = [[float(v) for v in item["embedding"]] for item in entries]
            dimensions = {len(v) for v in vectors}
            if dimensions != {self.settings.openrouter_embedding_dimensions} or not all(v and all(math.isfinite(x) for x in v) and any(v) for v in vectors):
                raise ValueError("Invalid embedding")
            return vectors
        except (KeyError, TypeError, ValueError):
            raise ProviderError("The embedding provider returned invalid vectors. Retry the request.", category="invalid_embedding") from None
