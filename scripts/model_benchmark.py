"""Explicit live model benchmark with frozen gold labels and a shared spend cap.

No production history or source files are mutated. All automatic results are
screening signals; a candidate is not selected without independent gold review.
"""
import argparse
import asyncio
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import statistics
import time
from uuid import uuid4

import httpx

from app.config import Settings
from app.extractors import ExtractionError, discover_soffice, extract_document
from app.ingestion import ENRICH_PROMPT, ingest_file
from app.models import Enrichment, SupportCheck
from app.provider import OpenRouter, ProviderError
from app.service import ANSWER_PIPELINE_VERSION, ANSWER_PROMPT, CHECK_PROMPT, COVERAGE_PROMPT, KnowledgeService
from app.store import Store, now

ROOT = Path(__file__).resolve().parents[1]
RUNNER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
MODELS = ["openai/gpt-4.1-mini", "openai/gpt-5.6-luna", "deepseek/deepseek-v4-pro-0813",
          "moonshotai/kimi-k3", "openai/gpt-6-astra", "anthropic/claude-fable-5.1"]
AUTHORIZED_BUDGET_USD = 40.0  # User increased the shared total from USD15 on September20; prior spend is retained.
# Explicit per-million price ceilings, not assumptions about cheapest routing.
PRICE_CAPS = {MODELS[0]: (0.5, 2.0), MODELS[1]: (0.3, 1.5), MODELS[2]: (1.5, 5.0),
              MODELS[3]: (3.0, 15.0), MODELS[4]: (10.0, 50.0), MODELS[5]: (10.0, 50.0),
              "openai/text-embedding-3-small": (0.03, 0.0)}
HARD_CASES = ["threshold-conflict-applied", "user-instruction-injection", "drill-is-not-incident"]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BudgetExceeded(ProviderError):
    def __init__(self):
        super().__init__("The benchmark's shared spend limit cannot safely cover another request.", category="benchmark_budget", status_code=503)


class BudgetLedger:
    def __init__(self, path, limit, reserve_for_followup=0):
        self.path, self.lock = path, asyncio.Lock()
        self.upstream_pause = None
        if not 0 <= reserve_for_followup < limit:
            raise ValueError("Follow-up reserve must leave a positive benchmark allocation.")
        self.reserve_for_followup = reserve_for_followup
        if not 0 < limit <= AUTHORIZED_BUDGET_USD:
            raise ValueError("Benchmark budget must be positive and cannot exceed the user-authorized USD40 total.")
        self.value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"limit_usd": limit, "attempts": []}
        if self.value["limit_usd"] != limit:
            if limit < self.value["limit_usd"]:
                raise ValueError("Do not reduce an existing ledger limit or reset its spend history.")
            self.value.setdefault("limit_changes", []).append({"from_usd": self.value["limit_usd"], "to_usd": limit, "created_at": now(), "reason": "Explicit user authorization increased the total benchmark budget; prior spend retained."})
            self.value["limit_usd"] = limit
            write_json(self.path, self.value)

    def accounted(self):
        return sum(record.get("accounted_usd", record["reserved_usd"]) for record in self.value["attempts"])

    async def reserve(self, payload, label):
        model = payload["model"]
        prompt_price, output_price = PRICE_CAPS[model]
        # At most one token per UTF-8 byte plus generous framing/schema margin;
        # double input allowance also covers cache-write premiums. Output includes
        # reasoning, bounded by max_tokens. No tools/search/images are requested.
        input_bound = 2 * (len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 2048)
        output_bound = payload.get("max_tokens", 0)
        reserve = (input_bound * prompt_price + output_bound * output_price) / 1_000_000
        async with self.lock:
            if self.upstream_pause:
                raise ProviderError("Benchmark paused after an upstream billing or reservation limit; remaining calls were not dispatched.", category="benchmark_upstream_pause", status_code=503)
            if self.accounted() + reserve > self.value["limit_usd"] - self.reserve_for_followup:
                raise BudgetExceeded()
            record = {"attempt_id": uuid4().hex, "model": model, "label": label, "created_at": now(),
                      "reserved_usd": reserve, "input_token_bound": input_bound, "output_token_bound": output_bound}
            self.value["attempts"].append(record)
            write_json(self.path, self.value)
            return record

    async def settle(self, record, *, response=None, elapsed=0, transport_error=False):
        async with self.lock:
            usage = {}
            if response is not None:
                record["http_status"] = response.status_code
                try:
                    body = response.json()
                    usage = body.get("usage", {}) if isinstance(body, dict) else {}
                    error = body.get("error", {}) if isinstance(body, dict) else {}
                    metadata = error.get("metadata", {}) if isinstance(error, dict) else {}
                    if isinstance(metadata, dict):
                        known_sources = {"openrouter_in_flight_budget", "openrouter_key_limit", "openrouter_credits"}
                        known_reasons = {"in_flight_budget_exhausted", "weight_exceeds_budget"}
                        safe_metadata = {key: value for key, value in metadata.items() if isinstance(value, str) and ((key == "limit_source" and value in known_sources) or (key == "reason" and value in known_reasons))}
                        if safe_metadata:
                            record["upstream_limit_metadata"] = safe_metadata
                    serving_provider = body.get("provider") if isinstance(body, dict) else None
                    if isinstance(serving_provider, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9 _./()-]{0,80}", serving_provider):
                        record["serving_provider"] = serving_provider
                    choices = body.get("choices", []) if isinstance(body, dict) else []
                    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                        first = choices[0]
                        content = first.get("message", {}).get("content") if isinstance(first.get("message"), dict) else None
                        record["response_diagnostic"] = {"finish_reason": first.get("finish_reason") if first.get("finish_reason") in {"stop", "length", "error", "content_filter", "tool_calls"} else "other",
                                                          "content_type": type(content).__name__, "content_characters": len(content) if isinstance(content, str) else None}
                except (ValueError, RecursionError):
                    pass
            usage = usage if isinstance(usage, dict) else {}
            cost = usage.get("cost")
            if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0:
                record.update(accounted_usd=cost, reported_cost_usd=cost, cost_basis="provider_usage.cost")
            elif response is not None and response.status_code in {400, 401, 402, 403, 404, 422, 429}:
                record.update(accounted_usd=0.0, cost_basis="rejected_before_completion")
            else:
                # Unknown billing, including timed-out/cancelled attempts, keeps
                # the full reserved amount charged against this local cap.
                record.update(accounted_usd=record["reserved_usd"], cost_basis="unknown_cost_reserved_bound")
            record["elapsed_seconds"] = round(elapsed, 3)
            record["transport_error"] = transport_error
            record["usage"] = {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cost", "completion_tokens_details", "prompt_tokens_details") if key in usage}
            write_json(self.path, self.value)
            if record["accounted_usd"] > record["reserved_usd"] + 0.000001:
                raise RuntimeError("Provider charge exceeded the conservative reservation; benchmark stopped.")

    def summary(self):
        return {"limit_usd": self.value["limit_usd"], "accounted_usd": round(self.accounted(), 6),
                "reserved_for_followup_usd": self.reserve_for_followup,
                "reported_cost_usd": round(sum(r.get("reported_cost_usd", 0) for r in self.value["attempts"]), 6),
                "attempts": len(self.value["attempts"]),
                "unknown_cost_attempts": sum(r.get("cost_basis") == "unknown_cost_reserved_bound" for r in self.value["attempts"])}


class MeteredTransport(httpx.AsyncBaseTransport):
    def __init__(self, ledger, label, inner=None):
        self.ledger, self.label = ledger, label
        self.inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        payload = json.loads(request.content)
        record = await self.ledger.reserve(payload, self.label)
        started = time.monotonic()
        try:
            response = await self.inner.handle_async_request(request)
            await response.aread()
        except BaseException:
            await asyncio.shield(self.ledger.settle(record, elapsed=time.monotonic() - started, transport_error=True))
            raise
        await self.ledger.settle(record, response=response, elapsed=time.monotonic() - started)
        return response

    async def aclose(self):
        await self.inner.aclose()


class BenchmarkRouter(OpenRouter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.structured_outputs = []
        self.metered_transport = kwargs.get("transport") if isinstance(kwargs.get("transport"), MeteredTransport) else None

    async def structured(self, schema, system, content, **kwargs):
        input_snapshot = json.loads(json.dumps(content, ensure_ascii=False))
        result = await super().structured(schema, system, content, **kwargs)
        # These benchmark inputs contain only the frozen fictional corpus. Keep
        # parsed model responses so service-level ID/coverage failures remain
        # diagnosable without recording credentials or private reasoning.
        self.structured_outputs.append({"schema": schema.__name__, "model": kwargs.get("model") or self.settings.openrouter_model,
                                        "input": input_snapshot, "result": result.model_dump()})
        return result

    async def request(self, endpoint, payload):
        if endpoint == "chat/completions":
            prompt, completion = PRICE_CAPS[payload["model"]]
            # OpenRouter max_price units are USD per million tokens.
            payload.setdefault("provider", {})["max_price"] = {"prompt": prompt, "completion": completion}
            payload["provider"]["ignore"] = ["openai/flex"]
        try:
            return await super().request(endpoint, payload)
        except ProviderError:
            if self.metered_transport:
                ledger = self.metered_transport.ledger
                previous = next((row for row in reversed(ledger.value["attempts"]) if row["label"] == self.metered_transport.label), None)
                if previous and previous.get("http_status") == 402:
                    ledger.upstream_pause = previous.get("upstream_limit_metadata", {"http_status": 402})
                    ledger.value["last_upstream_pause"] = {"created_at": now(), **ledger.upstream_pause}
                    write_json(ledger.path, ledger.value)
            raise


def settings_for(model, path, review_model=None):
    review_model = review_model or model
    options = {candidate: {"temperature": 0.0 if candidate == MODELS[0] else None,
                          "reasoning_effort": None if candidate == MODELS[0] else "high",
                          "max_output_tokens": 8000, "allow_fallbacks": True,
                          "provider_ignore": ["openai/flex"]} for candidate in {model, review_model}}
    return Settings(_env_file=None, openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", ""),
                    openrouter_model=model, openrouter_review_model=review_model, openrouter_model_options=options,
                    data_dir=path, daily_evaluation=False, provider_timeout_seconds=120, operation_timeout_seconds=360)


def corpus_directory(output, label):
    """A new corpus namespace never changes the shared budget/lock namespace."""
    if label is None:
        return output
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", label):
        raise ValueError("Corpus label must be a short lowercase slug, without paths or traversal.")
    directory = (output / "corpora" / label).resolve()
    if not directory.is_relative_to(output.resolve()):
        raise ValueError("Corpus directory must remain within the existing benchmark runtime output.")
    return directory


def canonical_json_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def corpus_snapshot(store):
    records = []
    with store.connect() as db:
        for document in db.execute("SELECT * FROM documents WHERE active=1 ORDER BY filename"):
            metadata = json.loads(document["metadata"])
            chunks = [{"chunk_id": row["id"], "locator": row["locator"], "text": row["text"],
                       "text_sha256": hashlib.sha256(row["text"].encode("utf-8")).hexdigest(),
                       "embedding_model": row["embedding_model"]}
                      for row in db.execute("SELECT * FROM chunks WHERE document_id=? ORDER BY rowid", (document["id"],))]
            records.append({"document_id": document["id"], "filename": document["filename"],
                            "source_sha256": document["sha256"], "metadata": metadata,
                            "metadata_sha256": canonical_json_sha(metadata), "chunks": chunks})
    return records


def prepare_canonical(source_db, output, gold, *, require_source_metadata_match=False):
    store = Store(output)
    if store.counts()[0]:
        if store.counts()[0] != 24:
            raise ValueError("Existing benchmark corpus must have exactly24 documents.")
        with store.connect() as db:
            for item in gold["enrichment_gold"]:
                row = db.execute("SELECT * FROM documents WHERE filename=? AND sha256=? AND active=1", (item["filename"], item["sha256"])).fetchone()
                if row is None or any(json.loads(row["metadata"])[key] != item[key] for key in ("author", "attendees", "date")):
                    raise ValueError("Existing benchmark source identity differs from frozen canonical gold.")
        if require_source_metadata_match:
            source = sqlite3.connect(source_db.resolve().as_uri() + "?mode=ro", uri=True)
            source.row_factory = sqlite3.Row
            try:
                with store.connect() as target:
                    for item in gold["enrichment_gold"]:
                        current = source.execute("SELECT id,metadata FROM documents WHERE filename=? AND sha256=? AND active=1", (item["filename"], item["sha256"])).fetchone()
                        copied = target.execute("SELECT id,metadata FROM documents WHERE filename=? AND active=1", (item["filename"],)).fetchone()
                        if current is None or current["id"] != copied["id"] or canonical_json_sha(json.loads(current["metadata"])) != canonical_json_sha(json.loads(copied["metadata"])):
                            raise ValueError("The source corpus changed after this label was frozen; choose a new corpus label instead of silently reusing stale metadata.")
            finally:
                source.close()
        return store
    source = sqlite3.connect(source_db.resolve().as_uri() + "?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        with store.connect() as target:
            for item in gold["enrichment_gold"]:
                row = source.execute("SELECT * FROM documents WHERE filename=? AND sha256=? AND active=1", (item["filename"], item["sha256"])).fetchone()
                if row is None:
                    raise ValueError(f"Canonical active source/hash absent: {item['filename']}")
                metadata = json.loads(row["metadata"])
                for name in ("author", "attendees", "date"):
                    if metadata[name] != item[name]:
                        raise ValueError(f"Attribution mismatch for {item['filename']}: {name}")
                target.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?)", tuple(row))
                for chunk in source.execute("SELECT * FROM chunks WHERE document_id=?", (row["id"],)):
                    target.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?)", tuple(chunk))
                    target.execute("INSERT INTO chunks_fts VALUES(?,?)", (chunk["id"], chunk["text"]))
            # Hash-keyed vectors contain no source/query text or user history.
            for cache in source.execute("SELECT * FROM embedding_cache"):
                target.execute("INSERT OR IGNORE INTO embedding_cache VALUES(?,?)", tuple(cache))
    finally:
        source.close()
    if store.counts()[0] != 24:
        raise ValueError("Canonical fixture must have exactly24 active sources.")
    return store


def numeric_values(text):
    return {str(Decimal(value.replace(",", "")).normalize()) for value in re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w.])", text)}


def assess_mechanics(answer, case):
    by_id = {item["chunk_id"]: item for item in answer["evidence"]}
    failures, review_flags = [], []
    citation_count = valid_citation_count = 0
    cited_filenames = set()
    if answer["status"] != case["expected_status"]:
        failures.append("status_mismatch")
    if case["expected_status"] in {"answered", "partial"} and not answer["claims"]:
        failures.append("missing_substantive_answer")
    if answer["status"] == "needs_routing" and answer["claims"]:
        failures.append("abstention_with_claims")
    for index, claim in enumerate(answer["claims"]):
        quotes = []
        metadata = []
        for citation in claim["citations"]:
            citation_count += 1
            source = by_id.get(citation["chunk_id"])
            if source is None or citation["quote"] not in source["text"]:
                failures.append(f"invalid_citation_claim_{index}")
            else:
                valid_citation_count += 1
                cited_filenames.add(source["filename"])
                quotes.append(citation["quote"])
                metadata.extend([source.get("date") or "", source.get("author") or ""])
        absent_numbers = numeric_values(claim["text"]) - numeric_values(" ".join(quotes + metadata))
        if absent_numbers:
            review_flags.append({"claim_index": index, "kind": "numerical_operand_not_in_selected_quotes", "values": sorted(absent_numbers)})
        if not quotes:
            failures.append(f"claim_{index}_has_no_valid_quote")
    for route in answer["routing"]:
        if not route["evidence_ids"] or any(i not in by_id or route["recipient"] not in {by_id[i]["author"], *by_id[i]["attendees"]} for i in route["evidence_ids"]):
            failures.append("unattributed_routing")
    if case.get("expect_no_routing") and answer["routing"]:
        failures.append("unrelated_routing")
    if case.get("expect_no_evidence") and answer["evidence"]:
        failures.append("unrelated_evidence")
    people = set(case.get("expected_routing_any", []))
    if people and not people.intersection(r["recipient"] for r in answer["routing"]):
        failures.append("missing_expected_contact")
    text = " ".join(c["text"] for c in answer["claims"]).casefold()
    failures.extend("forbidden_text:" + term for term in case.get("forbidden_terms", []) if term.casefold() in text)
    expected_sources = set(case.get("expected_sources", []))
    retrieved = {source["filename"] for source in answer["evidence"]}
    return {"mechanical_pass": not failures, "failures": failures, "semantic_review_flags": review_flags,
            "citation_count": citation_count, "valid_citation_count": valid_citation_count,
            "expected_source_retrieval_recall": len(expected_sources & retrieved) / len(expected_sources) if expected_sources else None,
            "expected_source_citation_recall": len(expected_sources & cited_filenames) / len(expected_sources) if expected_sources else None,
            "expected_sources_missing_from_evidence": sorted(expected_sources - retrieved),
            "source_recall_note": "Diagnostic only; an equivalent source can satisfy the frozen semantic rubric.",
            "semantic_review": "pending_independent_review", "quality_gate_pass": None}


async def run_query(model, case, repeat, store, ledger, stage, review_model=None):
    settings = settings_for(model, store.data_dir, review_model)
    provider = BenchmarkRouter(settings, store, transport=MeteredTransport(ledger, f"{stage}:{model}:{case['id']}:{repeat}"))
    record = {"model": model, "review_model": settings.openrouter_review_model, "case_id": case["id"], "split": case["split"], "repeat": repeat, "gold": case}
    started = time.monotonic()
    try:
        answer = (await KnowledgeService(settings, store, provider).query(case["question"], evaluation=True)).model_dump()
        record.update(answer=answer, assessment=assess_mechanics(answer, case))
    except ProviderError as error:
        record.update(error_category=error.category, error=str(error), assessment={"mechanical_pass": False, "quality_gate_pass": False})
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        record["structured_outputs"] = provider.structured_outputs
        await provider.close()
    return record


async def reviewer_control(model, control, store, ledger):
    settings = settings_for(model, store.data_dir)
    provider = BenchmarkRouter(settings, store, transport=MeteredTransport(ledger, f"screen-control:{model}:{control['case']}"))
    record = {"model": model, "case_id": control["case"], "expected_supported": control["expected_supported"], "input": control["input"]}
    started = time.monotonic()
    try:
        result = await provider.structured(SupportCheck, CHECK_PROMPT, control["input"], model=model)
        actual = result.checks[0].supported if len(result.checks) == 1 and result.checks[0].claim_index == 0 else None
        record.update(result=result.model_dump(), correct=actual == control["expected_supported"])
    except ProviderError as error:
        record.update(error_category=error.category, error=str(error), correct=False)
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        await provider.close()
    return record


async def enrich(model, item, store, ledger):
    with store.connect() as db:
        row = db.execute("SELECT * FROM documents WHERE filename=? AND active=1", (item["filename"],)).fetchone()
        chunks = db.execute("SELECT text FROM chunks WHERE document_id=? ORDER BY rowid", (row["id"],)).fetchall()
    metadata = json.loads(row["metadata"])
    text = "\n\n".join(chunk[0] for chunk in chunks)
    settings = settings_for(model, store.data_dir)
    provider = BenchmarkRouter(settings, store, transport=MeteredTransport(ledger, f"enrichment:{model}:{item['filename']}"))
    record = {"model": model, "filename": item["filename"], "gold": item, "source_text": text}
    started = time.monotonic()
    try:
        original = Path(row["source_path"])
        if sha(original) != item["sha256"]:
            raise ValueError("Canonical source changed before benchmark re-ingestion.")
        # The production fingerprint includes prompt/extractor/embedding versions
        # as well as model options. Delegate reuse to it so a prompt revision
        # cannot silently reuse stale enrichment during final certification.
        outcome = await ingest_file(original, store=store, provider=provider, settings=settings, force=False)
        already_enriched = outcome["status"] == "unchanged"
        with store.connect() as db:
            fresh = db.execute("SELECT * FROM documents WHERE id=?", (outcome["document_id"],)).fetchone()
        updated = json.loads(fresh["metadata"])
        result = Enrichment.model_validate({key: updated[key] for key in Enrichment.model_fields})
        record.update(result=result.model_dump(), reused_existing=already_enriched, ingestion_outcome=outcome, source_hash_stable=fresh["sha256"] == item["sha256"],
                      priority_matches=result.priority == item["priority"],
                      attribution_stable=all(updated[name] == item[name] for name in ("author", "attendees", "date")),
                      semantic_review="pending_independent_review")
    except ProviderError as error:
        record.update(error_category=error.category, error=str(error))
    except (ExtractionError, ValueError) as error:
        record.update(error_category="extraction_or_canonical_identity", error=str(error))
    finally:
        record["elapsed_seconds"] = round(time.monotonic() - started, 3)
        await provider.close()
    return record


def summarize(records, ledger):
    models = sorted({record["model"] for record in records})
    summaries = {}
    for model in models:
        selected = [r for r in records if r["model"] == model]
        latency = {}
        for kind in ("pipeline", "control", "enrichment"):
            times = sorted(r["elapsed_seconds"] for r in selected if r["record_type"] == kind and not r.get("reused_existing"))
            if times:
                latency[kind] = {"count": len(times), "median_seconds": round(statistics.median(times), 3),
                                 "p95_seconds": times[max(0, math.ceil(len(times) * .95) - 1)], "maximum_seconds": max(times)}
        summaries[model] = {"count": len(selected), "operational_errors": sum("error_category" in r for r in selected),
                            "mechanical_pass_count": sum(r.get("assessment", {}).get("mechanical_pass", False) for r in selected),
                            "control_correct": sum(r.get("correct", False) for r in selected),
                            "latency_by_record_type": latency, "quality_gate": "not_decided_without_independent_review"}
    return {"models": summaries, "spend": ledger.summary()}


async def main(args):
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("Configure OPENROUTER_API_KEY in the backend environment for this explicitly live benchmark.")
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / ".runtime"):
        raise ValueError("Benchmark runtime output must stay within this repository's .runtime directory.")
    output.mkdir(parents=True, exist_ok=True)
    corpus_output = corpus_directory(output, args.corpus_label)
    if args.stage == "enrichment":
        # Fail before paid requests if the required legacy converter is absent.
        discover_soffice(settings_for(args.models[0], output).soffice_path)
    gold_path = ROOT / "data/model_evaluation_gold.json"
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    digest = sha(gold_path)
    retry_pairs = None
    if args.retry_credits_from:
        prior = json.loads(args.retry_credits_from.read_text(encoding="utf-8"))
        if prior["gold_sha256"] != digest:
            raise ValueError("Credit retry must use the same frozen gold suite.")
        retry_pairs = {(row["model"], row["case_id"]) for row in prior["records"] if row.get("error_category") in {"credits", "benchmark_upstream_pause", "temporary_capacity", "in_flight_budget", "capacity", "key_limit", "request_budget"}}
        if not retry_pairs:
            raise ValueError("The supplied report has no credit/reservation failures to resume.")
        if any(row.get("review_model", row["model"]) != (args.review_model or row["model"]) for row in prior["records"] if (row["model"], row.get("case_id")) in retry_pairs):
            raise ValueError("Credit retry cannot change the candidate/reviewer configuration.")
    frozen = output / "frozen-gold.json"
    if frozen.exists() and sha(frozen) != digest:
        raise ValueError("Gold suite changed after benchmark started; preserve this run and create a new suite version.")
    if not frozen.exists():
        frozen.write_bytes(gold_path.read_bytes())
    ledger = BudgetLedger(output / "spend-ledger.json", args.budget, args.reserve_usd)
    stamp = now().replace(":", "-")
    path = ROOT / "docs/evaluation-results" / f"model-benchmark-{args.stage}-{stamp}.json"
    async with httpx.AsyncClient(timeout=30) as client:
        catalog = (await client.get("https://openrouter.ai/api/v1/models")).json()["data"]
    requested = set(args.models) | ({args.review_model} if args.review_model else set())
    actual = {m["id"]: m for m in catalog if m["id"] in requested}
    if set(actual) != requested:
        raise ValueError("One of the exact requested model IDs is absent from the official catalog.")
    stores = {model: prepare_canonical(args.source_db, corpus_output / model.replace("/", "__"), gold,
                                     require_source_metadata_match=args.corpus_label is not None and args.stage != "enrichment") for model in args.models}
    if args.stage == "enrichment":
        fixture = stores[args.models[0]]
        with fixture.connect() as db:
            legacy_paths = [Path(row[0]) for row in db.execute("SELECT source_path FROM documents WHERE active=1") if Path(row[0]).suffix.lower() in {".doc", ".ppt", ".xls"}]
        for legacy_path in legacy_paths:
            await asyncio.to_thread(extract_document, legacy_path, soffice_path=settings_for(args.models[0], output).soffice_path)
    controls = json.loads((ROOT / "docs/evaluation-results/reviewer-comparison.json").read_text(encoding="utf-8"))["results"]
    controls = [c for c in controls if c["model"] == "openai/gpt-4.1"]
    records = []
    report = {"created_at": now(), "stage": args.stage, "gold_sha256": digest, "gold_counts": {"regression": 33, "original_holdout": 12},
              "answer_pipeline_version": ANSWER_PIPELINE_VERSION,
              "embedding_model": settings_for(args.models[0], output).openrouter_embedding_model,
              "embedding_dimensions": settings_for(args.models[0], output).openrouter_embedding_dimensions,
              "corpus_label": args.corpus_label,
              "corpus_snapshots": {model: corpus_snapshot(store) for model, store in stores.items()},
              "concurrency": args.concurrency,
              "provider_timeout_seconds": settings_for(args.models[0], output).provider_timeout_seconds,
              "operation_timeout_seconds": settings_for(args.models[0], output).operation_timeout_seconds,
              "runner_sha256": RUNNER_SHA256, "price_ceilings_usd_per_million": {m: PRICE_CAPS[m] for m in requested},
              "review_model_override": args.review_model,
              "retry_credits_from": str(args.retry_credits_from) if args.retry_credits_from else None,
              "corpus_configuration": "Screen uses fixed baseline enrichment and cached embeddings; enrichment stage force-reingests canonical24 with candidate, subsequent queries use that active metadata.",
              "catalog": {model: {k: m.get(k) for k in ("id", "canonical_slug", "pricing", "supported_parameters", "reasoning")} for model, m in actual.items()},
              "model_options": {model: {key: value.model_dump() for key, value in settings_for(model, stores[model].data_dir, args.review_model).openrouter_model_options.items()} for model in args.models},
              "prompts": {"enrichment": ENRICH_PROMPT, "coverage": COVERAGE_PROMPT, "answer": ANSWER_PROMPT, "support": CHECK_PROMPT},
              "prompt_sha256": {name: hashlib.sha256(prompt.encode("utf-8")).hexdigest() for name, prompt in {"enrichment": ENRICH_PROMPT, "coverage": COVERAGE_PROMPT, "answer": ANSWER_PROMPT, "support": CHECK_PROMPT}.items()},
              "manual_quality_gate": "Every claim must be checked against frozen gold and own selected quotes by a reviewer independent of this candidate. Pending is not passing.",
              "records": records}
    report["corpus_snapshot_sha256"] = {model: canonical_json_sha(snapshot) for model, snapshot in report["corpus_snapshots"].items()}
    write_json(path, report)
    semaphore = asyncio.Semaphore(args.concurrency)

    async def task(model, mode, value, repeat=0):
        async with semaphore:
            if mode == "control":
                record = await reviewer_control(model, value, stores[model], ledger)
            elif mode == "enrichment":
                record = await enrich(model, value, stores[model], ledger)
            else:
                record = await run_query(model, value, repeat, stores[model], ledger, args.stage, args.review_model)
            record["record_type"] = mode
            records.append(record)
            report["summary"] = summarize(records, ledger)
            write_json(path, report)
            print(json.dumps({"stage": args.stage, "model": model, "case": record.get("case_id", record.get("filename")),
                              "seconds": record["elapsed_seconds"], "error": record.get("error_category"),
                              "control_correct": record.get("correct"), "mechanical": record.get("assessment", {}).get("mechanical_pass"),
                              "spend": ledger.summary()}), flush=True)

    if args.stage in {"screen", "controls"}:
        await asyncio.gather(*(task(model, "control", control) for control in controls for model in args.models))
        if args.stage == "screen":
            await asyncio.gather(*(task(model, "pipeline", case) for case in gold["cases"] if case["id"] in HARD_CASES for model in args.models))
    elif args.stage == "enrichment":
        await asyncio.gather(*(task(model, "enrichment", item) for item in gold["enrichment_gold"] for model in args.models))
    else:
        cases = gold["cases"]
        if args.stage == "holdout":
            cases = [case for case in cases if case["split"] == "untouched_holdout"]
        elif args.stage == "regression":
            cases = [case for case in cases if case["split"] == "regression"]
        elif args.stage == "repeat":
            cases = [case for case in cases if case["id"] in HARD_CASES]
        if args.case_ids:
            cases = [case for case in cases if case["id"] in args.case_ids]
        await asyncio.gather(*(task(model, "pipeline", case, repeat) for repeat in range(args.repeats) for case in cases for model in args.models if retry_pairs is None or (model, case["id"]) in retry_pairs))
    report["summary"] = summarize(records, ledger)
    if args.stage == "enrichment":
        report["corpus_snapshots_after_enrichment"] = {model: corpus_snapshot(store) for model, store in stores.items()}
    report["provider_attempts"] = ledger.value["attempts"]
    report["completed_at"] = now()
    write_json(path, report)
    print(json.dumps({"report": str(path), "summary": report["summary"]}), flush=True)
    if any("error_category" in r or r.get("correct") is False or r.get("assessment", {}).get("mechanical_pass") is False for r in records):
        return 1
    return 0


def run_exclusive(args):
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / ".runtime"):
        raise ValueError("Benchmark runtime output must stay within the repository .runtime directory.")
    output.mkdir(parents=True, exist_ok=True)
    lock = output / "run.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise SystemExit("Another benchmark owns this spend ledger. If it crashed, verify no benchmark process is running before removing run.lock.") from None
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        return asyncio.run(main(args))
    finally:
        os.close(descriptor)
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["screen", "controls", "enrichment", "regression", "holdout", "full", "repeat"], required=True)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=MODELS)
    parser.add_argument("--review-model", choices=MODELS, help="One bounded hybrid: alternate reviewer for full pipeline stages; reviewer controls still test each named model.")
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/model-benchmark")
    parser.add_argument("--source-db", type=Path, default=ROOT / ".runtime/workspace.sqlite3")
    parser.add_argument("--corpus-label", help="Freeze a new canonical24 corpus from source-db beneath the SAME output/ledger; labelled query runs reject later source metadata changes.")
    parser.add_argument("--budget", type=float, default=AUTHORIZED_BUDGET_USD)
    parser.add_argument("--reserve-usd", type=float, default=0, help="Leave this amount of the shared cap for repetition/final application validation.")
    parser.add_argument("--concurrency", type=int, default=3, choices=[1, 2, 3, 4])
    parser.add_argument("--repeats", type=int, default=1, choices=[1, 2, 3])
    parser.add_argument("--case-ids", nargs="*")
    parser.add_argument("--retry-credits-from", type=Path, help="Resume only credit/reservation-blocked cases from an immutable prior report, preserving successful and semantic-failure rows.")
    raise SystemExit(run_exclusive(parser.parse_args()))
