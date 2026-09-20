import asyncio
import hashlib
import json
from datetime import datetime, timezone

from .provider import ProviderError
from .service import ANSWER_PIPELINE_VERSION, ANSWER_PROMPT, CHECK_PROMPT, COVERAGE_PROMPT, normalized
from .store import encode, identifier, now


def evaluation_identity(service, dataset_bytes):
    settings = service.settings
    options = {model: settings.openrouter_model_options[model].model_dump()
               for model in sorted({settings.openrouter_model, settings.openrouter_review_model})
               if model in settings.openrouter_model_options}
    profile = {"model": settings.openrouter_model, "review_model": settings.openrouter_review_model,
               "model_options": options, "embedding_model": settings.openrouter_embedding_model,
               "embedding_dimensions": settings.openrouter_embedding_dimensions,
               "answer_pipeline_version": ANSWER_PIPELINE_VERSION,
               "prompts": [ANSWER_PROMPT, COVERAGE_PROMPT, CHECK_PROMPT]}
    return {"dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
            "profile_sha256": hashlib.sha256(encode(profile).encode()).hexdigest(),
            "model": settings.openrouter_model, "review_model": settings.openrouter_review_model,
            "model_options": options}


def quality(store):
    with store.connect() as conn:
        rows = conn.execute("SELECT payload FROM evaluations ORDER BY created_at DESC").fetchall()
        failure = conn.execute("SELECT created_at FROM events WHERE kind='evaluation_failure' ORDER BY id DESC LIMIT 1").fetchone()
    reports = [json.loads(row[0]) for row in rows]
    latest = reports[0] if reports else None
    alerts = [] if latest else ["No evaluation has run yet. Run python -m app evaluate after ingestion."]
    seen = set()
    suites = []
    open_findings = 0
    count_known = True
    for report in reports:
        # A passing three-question canary must not clear an unresolved full-suite
        # failure, nor may an unrelated audit hide failures in the main suite.
        key = (report.get("dataset", "default"), report.get("suite", "held-out-full"))
        if key in seen:
            continue
        seen.add(key)
        alerts.extend(f"{key[0]} ({key[1]}): {alert}" for alert in report.get("alerts", []))
        total, passed = report.get("case_count"), report.get("passed")
        valid_counts = type(total) is int and type(passed) is int and 0 <= passed <= total
        failed = total - passed if valid_counts else None
        suites.append({"dataset": key[0], "suite": key[1], "created_at": report.get("created_at"),
                       "case_count": total if valid_counts else None, "passed": passed if valid_counts else None,
                       "failed_cases": failed, "alerts": report.get("alerts", []),
                       "model": report.get("model"), "review_model": report.get("review_model")})
        if failed is not None:
            open_findings += failed
        elif report.get("alerts"):
            count_known = False
    if failure and (not latest or failure[0] > latest["created_at"]):
        alerts.append("Scheduled evaluation failed. Check the evaluation dataset and run python -m app evaluate to diagnose it.")
    return {"latest": latest, "alerts": alerts, "suites": suites,
            "open_finding_count": open_findings if count_known else None}


async def evaluate(service, *, limit=None):
    path = service.settings.evaluation_path
    if not path.is_file():
        raise ValueError(f"Evaluation dataset not found: {path}")
    dataset_bytes = path.read_bytes()
    dataset = json.loads(dataset_bytes.decode("utf-8-sig"))
    if isinstance(dataset, dict):
        dataset = dataset.get("cases")
    if not isinstance(dataset, list) or not dataset:
        raise ValueError("Evaluation dataset must be a nonempty JSON list.")
    if limit is not None:
        dataset = dataset[:limit]
    suite = "daily-canary" if limit else "held-out-full"
    identity = evaluation_identity(service, dataset_bytes)
    dataset_sha256 = identity["dataset_sha256"]
    # Persist the attempt before paid requests. An interrupted full run must not
    # restart every minute, and a report for another dataset is not this run.
    store_event = {**identity, "suite": suite}
    service.store.event("evaluation_started", store_event)
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
            behavioral_failures = []
            if answer.status in {"answered", "partial"} and not answer.claims:
                behavioral_failures.append("Substantive answer has no claims.")
            if answer.status == "needs_routing" and answer.claims:
                behavioral_failures.append("Abstention contains substantive claims.")
            if case.get("expect_no_evidence") and answer.evidence:
                behavioral_failures.append("Unrelated question exposed irrelevant evidence.")
            if case.get("expect_no_routing") and answer.routing:
                behavioral_failures.append("Unrelated question suggested a recipient.")
            expected_people = set(case.get("expected_routing_any", []))
            if expected_people and not expected_people.intersection(route.recipient for route in answer.routing):
                behavioral_failures.append("Expected source-backed routing recipient is absent.")
            for route in answer.routing:
                if not route.evidence_ids or any(chunk_id not in evidence or route.recipient not in {evidence[chunk_id].author, *evidence[chunk_id].attendees} for chunk_id in route.evidence_ids):
                    behavioral_failures.append("Routing recipient is not attributed to every referenced source.")
            passed = status_match and not forbidden_found and not behavioral_failures and (recall is None or recall == 1) and (fact_coverage is None or fact_coverage == 1) and valid_citations == len(citations)
            records.append({"id": case["id"], "query_id": answer.query_id, "passed": passed, "status": answer.status,
                            "expected_status": case["expected_status"], "status_match": status_match,
                            "retrieval_recall": recall, "expected_fact_coverage": fact_coverage,
                            "citation_count": len(citations), "valid_citations": valid_citations,
                            "verified_claim_count": len(answer.claims), "forbidden_terms_found": forbidden_found,
                            "behavioral_failures": behavioral_failures})
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
              "model_options": identity["model_options"], "profile_sha256": identity["profile_sha256"],
              "case_count": len(records), "passed": sum(r["passed"] for r in records),
              "pass_rate": sum(r["passed"] for r in records) / len(records),
              "retrieval_recall": sum(recalls) / len(recalls) if recalls else None,
              "expected_fact_coverage": sum(coverage) / len(coverage) if coverage else None,
              "citation_validity": sum(r.get("valid_citations", 0) for r in records) / citation_count if citation_count else None,
              "abstention_accuracy": sum(r["status_match"] for r in expected_abstentions) / len(expected_abstentions) if expected_abstentions else None,
              "verified_claim_count": sum(r.get("verified_claim_count", 0) for r in records),
              "support_measurement": "Automated monitoring: exact references, status, expected-source recall and lexical assertions, plus the application's model support check. Semantic gold facts and scope guards require separate independent review; automatic passes are not semantic accuracy certification.",
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


def claim_daily_evaluation(service):
    """Claim a due full run atomically across local server instances."""
    identity = evaluation_identity(service, service.settings.evaluation_path.read_bytes())
    with service.store.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute(
            "SELECT created_at FROM events WHERE kind IN ('evaluation_started','evaluation_schedule_claim') "
            "AND json_extract(payload,'$.dataset_sha256')=? "
            "AND json_extract(payload,'$.suite')='held-out-full' "
            "AND json_extract(payload,'$.profile_sha256')=? ORDER BY id DESC LIMIT 1",
            (identity["dataset_sha256"], identity["profile_sha256"]),
        ).fetchone()
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(current[0])).total_seconds() if current else float("inf")
        if age < 86400:
            return False
        conn.execute("INSERT INTO events(kind,payload,created_at) VALUES(?,?,?)",
                     ("evaluation_schedule_claim", encode({**identity, "suite": "held-out-full"}), now()))
    return True


async def daily_evaluation_loop(service):
    while True:
        try:
            if service.settings.configured and service.store.counts()[0] and service.settings.evaluation_path.is_file():
                if claim_daily_evaluation(service):
                    await evaluate(service)
        except asyncio.CancelledError:
            raise
        except Exception:
            service.store.event("evaluation_failure", {"category": "scheduler_error"})
        await asyncio.sleep(60)
