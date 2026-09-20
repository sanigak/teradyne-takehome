"""Explicit live, bounded reviewer comparison on previously saved audit answers.

Run from the configured backend environment. No mock provider is used. The output
contains fictional evidence and model judgments, never credentials or headers.
"""
import argparse
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

import httpx

from app.config import Settings
from app.models import SupportCheck
from app.provider import OpenRouter, ProviderError
from app.service import CHECK_PROMPT
from app.store import Store, now


MODELS = ["openai/gpt-4.1", "anthropic/claude-sonnet-5"]
SPECS = [
    ("uncited-observation", "threshold-conflict-applied", 1, False, "conflicting"),
    ("unqualified-logging", "user-instruction-injection", 0, False, "present"),
    ("unsupported-negative", "drill-is-not-incident", 1, False, "present"),
    ("valid-historical-assumption", "historical-scope", 0, True, "present"),
    ("valid-inclusive-boundary", "inclusive-stop-boundary", 0, True, "present"),
]


class AuditedRouter(OpenRouter):
    async def request(self, endpoint, payload):
        # Sonnet 5's official supported-parameters list excludes temperature.
        # Keeping require_parameters=True with temperature would reject routing.
        if payload["model"] == "anthropic/claude-sonnet-5":
            payload.pop("temperature", None)
        response = await super().request(endpoint, payload)
        self.last_usage = response.get("usage", {})
        return response


async def run(snapshot, output):
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("Set OPENROUTER_API_KEY in the backend environment before this explicit live test.")
    output.mkdir(parents=True, exist_ok=True)
    report = json.loads(snapshot.read_text(encoding="utf-8"))
    settings = Settings(_env_file=None, data_dir=output, daily_evaluation=False)
    store = Store(output)
    async with httpx.AsyncClient(timeout=30) as client:
        catalog = (await client.get("https://openrouter.ai/api/v1/models")).json()["data"]
    models = {item["id"]: item for item in catalog if item["id"] in MODELS}
    if set(models) != set(MODELS):
        raise SystemExit("A requested reviewer is absent from the official OpenRouter catalog.")
    results = []
    semaphore = asyncio.Semaphore(2)

    async def compare(model, spec):
        name, case, index, expected, state = spec
        answer = report["answers"][case]
        claim = answer["claims"][index]
        ids = {citation["chunk_id"] for citation in claim["citations"]}
        payload = {"question": answer["question"],
                   "claims": [{"claim_index": 0, **claim, "cited_source_context": [item for item in answer["evidence"] if item["chunk_id"] in ids]}],
                   "request_coverage": [{"requested_component": answer["question"], "evidence_state": state}]}
        async with semaphore:
            provider = AuditedRouter(settings, store)
            started = time.monotonic()
            record = {"case": name, "source_case": case, "claim_index_in_snapshot": index,
                      "model": model, "expected_supported": expected, "input": payload}
            try:
                result = await provider.structured(SupportCheck, CHECK_PROMPT, payload, model=model)
                observed = result.checks[0].supported if len(result.checks) == 1 and result.checks[0].claim_index == 0 else None
                record.update(result=result.model_dump(), observed_supported=observed, correct=observed == expected,
                              usage=provider.last_usage)
            except ProviderError as exc:
                record.update(correct=False, error_category=exc.category, error=str(exc))
            finally:
                record["elapsed_seconds"] = round(time.monotonic() - started, 3)
                await provider.close()
            results.append(record)
            print(json.dumps({key: record[key] for key in ("case", "model", "correct", "elapsed_seconds")} | {"supported": record.get("observed_supported"), "error": record.get("error_category")}), flush=True)

    await asyncio.gather(*(compare(model, spec) for spec in SPECS for model in MODELS))
    result = {"created_at": now(), "snapshot_evaluation_id": report["evaluation"]["id"],
              "prompt_sha256": hashlib.sha256(CHECK_PROMPT.encode()).hexdigest(), "prompt": CHECK_PROMPT,
              "pricing_source": "https://openrouter.ai/api/v1/models",
              "models": {model: {"pricing": value["pricing"], "supported_parameters": value["supported_parameters"]} for model, value in models.items()},
              "temperature_note": "GPT-4.1 uses temperature=0; Sonnet 5 omits temperature because its official supported-parameters list excludes it.",
              "results": results, "provider_metrics": store.metrics()}
    (output / "report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", action="append", choices=MODELS, help="Restrict the comparison to selected model(s).")
    arguments = parser.parse_args()
    if arguments.model:
        MODELS[:] = list(dict.fromkeys(arguments.model))
    asyncio.run(run(arguments.snapshot, arguments.output))
