import asyncio
import hashlib
import json
from datetime import datetime, timezone

from .provider import ProviderError
from .service import normalized
from .store import encode, identifier, now


def quality(store):
    with store.connect() as conn:
        row = conn.execute("SELECT payload FROM evaluations ORDER BY created_at DESC LIMIT 1").fetchone()
        failure = conn.execute("SELECT created_at FROM events WHERE kind='evaluation_failure' ORDER BY id DESC LIMIT 1").fetchone()
    latest = json.loads(row[0]) if row else None
    alerts = list(latest.get("alerts", [])) if latest else ["No evaluation has run yet. Run python -m app evaluate after ingestion."]
    if failure and (not latest or failure[0] > latest["created_at"]):
        alerts.append("Scheduled evaluation failed. Check the evaluation dataset and run python -m app evaluate to diagnose it.")
    return {"latest": latest, "alerts": alerts}


async def evaluate(service, *, limit=None):
    path = service.settings.evaluation_path
    if not path.is_file():
        raise ValueError(f"Evaluation dataset not found: {path}")
    dataset_bytes = path.read_bytes()
    dataset = json.loads(dataset_bytes.decode("utf-8-sig"))
    if not isinstance(dataset, list) or not dataset:
        raise ValueError("Evaluation dataset must be a nonempty JSON list.")
    if limit is not None:
        dataset = dataset[:limit]
    suite = "daily-canary" if limit else "held-out-full"
    dataset_sha256 = hashlib.sha256(dataset_bytes).hexdigest()
    baseline_key = hashlib.sha256(encode({"dataset_sha256": dataset_sha256, "case_ids": [case["id"] for case in dataset]}).encode()).hexdigest()
    with service.store.connect() as conn:
        row = conn.execute("SELECT payload FROM evaluations WHERE json_extract(payload,'$.suite')=? AND json_extract(payload,'$.baseline_key')=? ORDER BY created_at DESC LIMIT 1", (suite, baseline_key)).fetchone()
    previous = json.loads(row[0]) if row else None
    records = []
    for case in dataset:
        try:
            answer = await service.query(case["question"], evaluation=True)
            retrieved = {item.filename for item in answer.evidence}
            expected = set(case.get("expected_sources", []))
            recall = len(retrieved & expected) / len(expected) if expected else None
            text = " ".join(claim.text for claim in answer.claims).casefold()
            terms = case.get("required_terms", [])
            fact_coverage = sum(term.casefold() in text for term in terms) / len(terms) if terms else None
            forbidden_found = [term for term in case.get("forbidden_terms", []) if term.casefold() in text]
            evidence = {item.chunk_id: item for item in answer.evidence}
            citations = [citation for claim in answer.claims for citation in claim.citations]
            valid_citations = sum(citation.chunk_id in evidence and normalized(citation.quote) in normalized(evidence[citation.chunk_id].text) for citation in citations)
            status_match = answer.status == case["expected_status"]
            passed = status_match and not forbidden_found and (recall is None or recall == 1) and (fact_coverage is None or fact_coverage == 1) and valid_citations == len(citations)
            records.append({"id": case["id"], "query_id": answer.query_id, "passed": passed, "status": answer.status,
                            "expected_status": case["expected_status"], "status_match": status_match,
                            "retrieval_recall": recall, "expected_fact_coverage": fact_coverage,
                            "citation_count": len(citations), "valid_citations": valid_citations,
                            "verified_claim_count": len(answer.claims), "forbidden_terms_found": forbidden_found})
        except ProviderError as exc:
            records.append({"id": case["id"], "passed": False, "expected_status": case["expected_status"], "status_match": False,
                            "retrieval_recall": 0 if case.get("expected_sources") else None,
                            "expected_fact_coverage": 0 if case.get("required_terms") else None,
                            "operational_error": exc.category, "message": str(exc)})
    recalls = [r["retrieval_recall"] for r in records if r.get("retrieval_recall") is not None]
    coverage = [r["expected_fact_coverage"] for r in records if r.get("expected_fact_coverage") is not None]
    citation_count = sum(r.get("citation_count", 0) for r in records)
    expected_abstentions = [r for r in records if r.get("expected_status") in ("needs_routing", "partial")]
    result = {"id": identifier(), "created_at": now(), "suite": suite,
              "dataset": path.name, "dataset_sha256": dataset_sha256, "baseline_key": baseline_key,
              "model": service.settings.openrouter_model, "embedding_model": service.settings.openrouter_embedding_model,
              "review_model": service.settings.openrouter_review_model,
              "case_count": len(records), "passed": sum(r["passed"] for r in records),
              "pass_rate": sum(r["passed"] for r in records) / len(records),
              "retrieval_recall": sum(recalls) / len(recalls) if recalls else None,
              "expected_fact_coverage": sum(coverage) / len(coverage) if coverage else None,
              "citation_validity": sum(r.get("valid_citations", 0) for r in records) / citation_count if citation_count else None,
              "abstention_accuracy": sum(r["status_match"] for r in expected_abstentions) / len(expected_abstentions) if expected_abstentions else None,
              "verified_claim_count": sum(r.get("verified_claim_count", 0) for r in records),
              "support_measurement": "Returned claims passed a separate model support check; expected-fact assertions supplement this non-independent judge.",
              "cases": records, "alerts": []}
    if result["pass_rate"] < 1:
        result["alerts"].append(f"{len(records) - result['passed']} of {len(records)} evaluation cases failed. Inspect the case results before release.")
    if any("operational_error" in r for r in records):
        result["alerts"].append("Evaluation encountered provider or configuration failures; these are not organizational knowledge gaps.")
    if previous and previous["suite"] == result["suite"] and result["pass_rate"] < previous["pass_rate"]:
        result["alerts"].append("Pass rate regressed compared with the previous run of this suite.")
    with service.store.connect() as conn:
        conn.execute("INSERT INTO evaluations VALUES(?,?,?)", (result["id"], encode(result), result["created_at"]))
    return result


async def daily_evaluation_loop(service):
    while True:
        try:
            current = quality(service.store)["latest"]
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(current["created_at"])).total_seconds() if current else float("inf")
            if service.settings.configured and service.store.counts()[0] and age >= 86400 and service.settings.evaluation_path.is_file():
                await evaluate(service, limit=3)
        except asyncio.CancelledError:
            raise
        except Exception:
            service.store.event("evaluation_failure", {"category": "scheduler_error"})
        await asyncio.sleep(60)
