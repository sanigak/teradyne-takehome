"""Validate and import locked independent benchmark reviews, without model calls.

By default this writes two review artifacts only. --persist additionally imports
them into local quality history; it never imports sources, answers, or feedback.
"""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from app.config import ROOT, ModelOptions, Settings
from app.evaluation import evaluation_identity
from app.ingestion import ENRICH_PROMPT
from app.models import Enrichment, Evidence, QueryResult
from app.service import ANSWER_PIPELINE_VERSION, ANSWER_PROMPT, CHECK_PROMPT, COVERAGE_PROMPT, normalized
from app.store import Store, encode


MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


def read_artifact(path):
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_ARTIFACT_BYTES + 1)
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("Review artifact exceeds the 64 MiB limit.")
    return json.loads(raw.decode("utf-8-sig")), raw, hashlib.sha256(raw).hexdigest()


def artifact_path(workspace, value):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("Referenced artifacts must use repository-relative paths.")
    path = (workspace / value).resolve()
    if not path.is_relative_to(workspace.resolve()):
        raise ValueError("Referenced artifact leaves the repository.")
    return path


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("Artifact requires a valid timestamp.") from None
    if parsed.utcoffset() is None:
        raise ValueError("Artifact timestamps must include a timezone.")
    return parsed


def cases_by_id(value, count):
    cases = value.get("cases") if isinstance(value, dict) else value
    if not isinstance(cases, list) or len(cases) != count:
        raise ValueError(f"Expected exactly {count} frozen cases.")
    result = {}
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get("id"), str)
                or not isinstance(case.get("question"), str) or not case["question"].strip()
                or case["id"] in result):
            raise ValueError("Frozen case IDs/questions must be present and unique.")
        result[case["id"]] = case
    if len({case["question"] for case in cases}) != count:
        raise ValueError("Frozen questions must be unique.")
    return result


def effective_options(settings):
    return {model: ModelOptions.model_validate(settings.openrouter_model_options.get(
        model, ModelOptions(temperature=0))).model_dump()
        for model in sorted({settings.openrouter_model, settings.openrouter_review_model})}


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def validate_corpus_snapshot(report, settings, gold_value):
    """Bind every future answer to one complete immutable release corpus."""
    snapshots, digests = report.get("corpus_snapshots"), report.get("corpus_snapshot_sha256")
    snapshot = snapshots.get(settings.openrouter_model) if isinstance(snapshots, dict) else None
    digest = digests.get(settings.openrouter_model) if isinstance(digests, dict) else None
    if (not isinstance(report.get("corpus_label"), str) or not report["corpus_label"].strip()
            or not isinstance(snapshot, list) or len(snapshot) != 24
            or any(not isinstance(item, dict) for item in snapshot)
            or canonical_digest(snapshot) != digest):
        raise ValueError("A SHA-pinned, labeled release corpus of exactly 24 sources is required.")
    frozen = gold_value.get("enrichment_gold") if isinstance(gold_value, dict) else None
    if (not isinstance(frozen, list) or len(frozen) != 24
            or any(not isinstance(item, dict) or not isinstance(item.get("filename"), str) for item in frozen)):
        raise ValueError("The frozen dataset must identify exactly 24 canonical source files.")
    gold_sources = {item["filename"]: item for item in frozen}
    if len(gold_sources) != 24:
        raise ValueError("Frozen canonical source filenames must be unique.")
    options = effective_options(settings)[settings.openrouter_model]
    # This is the actual ingestion identity, including extractor/packer version;
    # changes to that format must be explicitly supported by this importer.
    expected_ingestion_profile = hashlib.sha256((ENRICH_PROMPT + settings.openrouter_model
        + json.dumps(options, sort_keys=True) + settings.openrouter_embedding_model
        + str(settings.openrouter_embedding_dimensions) + "extract-pack-v3").encode()).hexdigest()
    document_ids, filenames, evidence = set(), set(), {}
    for item in snapshot:
        doc_id, filename = item.get("document_id"), item.get("filename")
        if (not isinstance(doc_id, str) or not doc_id or doc_id in document_ids
                or not isinstance(filename, str) or filename in filenames or filename not in gold_sources):
            raise ValueError("Release corpus source IDs and canonical filenames must be unique.")
        document_ids.add(doc_id)
        filenames.add(filename)
        source_gold, metadata, chunks = gold_sources[filename], item.get("metadata"), item.get("chunks")
        if item.get("source_sha256") != source_gold.get("sha256") or not source_gold.get("sha256"):
            raise ValueError("Release corpus original source hash differs from frozen gold.")
        if not isinstance(metadata, dict) or canonical_digest(metadata) != item.get("metadata_sha256"):
            raise ValueError("Release corpus metadata digest is missing or invalid.")
        if any(metadata.get(key) != source_gold.get(key) for key in ("author", "attendees", "date", "priority")):
            raise ValueError("Release corpus deterministic source attribution/priority differs from frozen gold.")
        Enrichment.model_validate({key: metadata.get(key) for key in ("domain", "priority", "decisions", "action_items")})
        if (metadata.get("enrichment_model") != settings.openrouter_model
                or metadata.get("enrichment_options") != options
                or metadata.get("embedding_model") != settings.openrouter_embedding_model
                or type(metadata.get("embedding_dimensions")) is not int
                or metadata["embedding_dimensions"] != settings.openrouter_embedding_dimensions
                or metadata.get("ingestion_profile") != expected_ingestion_profile):
            raise ValueError("Release corpus was not enriched with the current effective source profile.")
        if not isinstance(chunks, list) or not chunks or any(not isinstance(chunk, dict) for chunk in chunks):
            raise ValueError("Every release source must have immutable chunk snapshots.")
        for chunk in chunks:
            cid, text = chunk.get("chunk_id"), chunk.get("text")
            if (not isinstance(cid, str) or not cid or cid in evidence or not isinstance(text, str)
                    or hashlib.sha256(text.encode("utf-8")).hexdigest() != chunk.get("text_sha256")
                    or chunk.get("embedding_model") != settings.openrouter_embedding_model):
                raise ValueError("Release corpus chunk identity, text digest or embedding profile is invalid.")
            evidence[cid] = Evidence.model_validate({"chunk_id": cid, "document_id": doc_id,
                "filename": filename, "text": text, "locator": chunk.get("locator"),
                **{key: metadata.get(key) for key in ("title", "author", "attendees", "date", "domain", "priority")}}).model_dump()
    return digest, evidence


def validate_profile(report, settings, gold_digest):
    if not isinstance(report, dict):
        raise ValueError("Raw benchmark report must be a JSON object.")
    if report.get("gold_sha256") != gold_digest:
        raise ValueError("Raw benchmark gold digest does not match the frozen dataset.")
    if report.get("answer_pipeline_version") != ANSWER_PIPELINE_VERSION:
        raise ValueError("Raw benchmark answer pipeline version is missing or stale.")
    if (report.get("embedding_model") != settings.openrouter_embedding_model
            or type(report.get("embedding_dimensions")) is not int
            or report["embedding_dimensions"] != settings.openrouter_embedding_dimensions):
        raise ValueError("Raw benchmark embedding configuration is missing or mismatched.")
    expected = {"enrichment": ENRICH_PROMPT, "coverage": COVERAGE_PROMPT,
                "answer": ANSWER_PROMPT, "support": CHECK_PROMPT}
    if report.get("prompts") != expected:
        raise ValueError("Raw benchmark prompts do not match the current application.")
    digests = {name: hashlib.sha256(value.encode()).hexdigest() for name, value in expected.items()}
    if report.get("prompt_sha256") != digests:
        raise ValueError("Raw benchmark prompt digests are missing or mismatched.")
    all_options = report.get("model_options")
    options = all_options.get(settings.openrouter_model) if isinstance(all_options, dict) else None
    if not isinstance(options, dict) or set(options) != set(effective_options(settings)):
        raise ValueError("Raw benchmark model options do not identify the selected model pair.")
    if {model: ModelOptions.model_validate(value).model_dump() for model, value in options.items()} != effective_options(settings):
        raise ValueError("Raw benchmark effective model options differ from current Settings.")
    timestamp(report.get("completed_at"))


def validate_answer(raw, case, passed, corpus_evidence):
    error = raw.get("error_category")
    answer = raw.get("answer")
    if error is not None:
        if not isinstance(error, str) or not error or answer is not None or passed:
            raise ValueError("An operational failure cannot be an independent pass or completed answer.")
        return None
    answer = QueryResult.model_validate(answer).model_dump()
    if answer["question"] != case["question"]:
        raise ValueError("Raw answer question does not match frozen gold.")
    timestamp(answer["created_at"])
    evidence = {item["chunk_id"]: item for item in answer["evidence"]}
    if len(evidence) != len(answer["evidence"]):
        raise ValueError("Raw answer has duplicate evidence IDs.")
    if any(corpus_evidence.get(item["chunk_id"]) != item for item in answer["evidence"]):
        raise ValueError("Answer evidence does not match its immutable release corpus source/chunk/provenance.")
    for claim in answer["claims"]:
        for citation in claim["citations"]:
            source = evidence.get(citation["chunk_id"])
            if source is None or normalized(citation["quote"]) not in normalized(source["text"]):
                raise ValueError("Citation ID or exact quotation is not valid in its immutable evidence snapshot.")
    for route in answer["routing"]:
        if not route["evidence_ids"] or any(
                source_id not in evidence or route["recipient"] not in
                {evidence[source_id]["author"], *evidence[source_id]["attendees"]}
                for source_id in route["evidence_ids"]):
            raise ValueError("Routing is not attributed to every selected source snapshot.")
    if passed and (answer["status"] != case["expected_status"]
                   or (answer["status"] == "needs_routing") == bool(answer["claims"])
                   or (case.get("expect_no_evidence") and answer["evidence"])
                   or (case.get("expect_no_routing") and answer["routing"])):
        raise ValueError("Independent pass conflicts with the frozen answer/status boundary.")
    return answer


def build_reports(joined_path, gold_path, adversarial_path, settings, *, workspace=ROOT):
    """Pure validation/report construction: no Store creation or database writes."""
    joined, _, joined_digest = read_artifact(joined_path)
    gold_value, gold_bytes, gold_digest = read_artifact(gold_path)
    subset_value, subset_bytes, subset_digest = read_artifact(adversarial_path)
    gold, subset = cases_by_id(gold_value, 45), cases_by_id(subset_value, 15)
    for key, case in subset.items():
        if key not in gold or gold[key]["question"] != case["question"]:
            raise ValueError("The adversarial subset must match original case IDs and questions exactly.")
    if (not isinstance(joined, dict) or joined.get("complete") is not True
            or not isinstance(joined.get("records"), list)
            or any(not isinstance(row, dict) for row in joined["records"])):
        raise ValueError("Expected finalized, complete independent adjudication.")
    reviewed_at = timestamp(joined.get("created_at"))
    selected = [row for row in joined["records"] if row.get("model") == settings.openrouter_model
                and row.get("review_model") == settings.openrouter_review_model]
    if len(selected) != 45 or {row.get("case_id") for row in selected} != set(gold):
        raise ValueError("Selected configuration must have exactly 45 unique frozen case IDs.")
    if (any(not isinstance(row.get("anonymous_id"), str) or not row["anonymous_id"] for row in selected)
            or len({row["anonymous_id"] for row in selected}) != 45):
        raise ValueError("Selected independent answer IDs must be unique.")
    cache, corpus_cache, reviewed, proof, completion_times = {}, {}, {}, [], []
    for row in selected:
        raw_path = artifact_path(workspace, row.get("source_report"))
        review_path = artifact_path(workspace, row.get("review_report"))
        for path in (raw_path, review_path):
            if path not in cache:
                cache[path] = read_artifact(path)
        raw_report, _, raw_digest = cache[raw_path]
        review, _, review_digest = cache[review_path]
        if row.get("source_report_sha256") != raw_digest:
            raise ValueError("Raw benchmark report digest changed after independent adjudication.")
        validate_profile(raw_report, settings, gold_digest)
        if raw_path not in corpus_cache:
            corpus_cache[raw_path] = validate_corpus_snapshot(raw_report, settings, gold_value)
        corpus_digest, corpus_evidence = corpus_cache[raw_path]
        if len({value[0] for value in corpus_cache.values()}) != 1:
            raise ValueError("The selected 45 answers must use one identical release corpus snapshot.")
        completed = timestamp(raw_report["completed_at"])
        if completed > reviewed_at:
            raise ValueError("Independent adjudication predates the completed raw report.")
        completion_times.append(completed)
        index = row.get("record_index")
        if (not isinstance(raw_report.get("records"), list) or type(index) is not int
                or index < 0 or index >= len(raw_report["records"])):
            raise ValueError("Invalid raw benchmark record index.")
        raw = raw_report["records"][index]
        case = gold[row["case_id"]]
        if (not isinstance(raw, dict) or raw.get("record_type") != "pipeline" or raw.get("model") != settings.openrouter_model
                or raw.get("review_model") != settings.openrouter_review_model
                or raw.get("case_id") != case["id"] or raw.get("gold") != case):
            raise ValueError("Joined record does not match its raw model/case/frozen gold.")
        if not isinstance(review, dict):
            raise ValueError("Independent review must be a JSON object.")
        grades = review.get("records", review.get("answers", []))
        if not isinstance(grades, list) or any(not isinstance(grade, dict) for grade in grades):
            raise ValueError("Independent review must contain explicit verdict records.")
        matches = [grade for grade in grades if grade.get("anonymous_id") == row.get("anonymous_id")]
        if len(matches) != 1 or matches[0] != row.get("original_review"):
            raise ValueError("Joined verdict no longer matches its locked independent review.")
        grade = matches[0]
        passed = grade.get("pass", grade.get("passed"))
        if (type(passed) is not bool or type(row.get("passed")) is not bool or passed != row["passed"]
                or ("pass" in grade and "passed" in grade and grade["pass"] is not grade["passed"])
                or not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
                or review["reviewer"] != row.get("reviewer")
                or grade.get("case_id", case["id"]) != case["id"]):
            raise ValueError("Every verdict must be an explicit, source-bound independent boolean.")
        answer = validate_answer(raw, case, passed, corpus_evidence)
        failure_kind = "operational" if answer is None else (None if passed else "semantic")
        if row.get("failure_kind") != failure_kind:
            raise ValueError("Joined failure classification does not match the raw answer/verdict.")
        proof.append({"case_id": case["id"], "raw_report": row["source_report"], "raw_sha256": raw_digest,
                      "record_index": index, "review_report": row["review_report"], "review_sha256": review_digest,
                      "corpus_snapshot_sha256": corpus_digest})
        reviewed[case["id"]] = {"id": case["id"], "question": case["question"], "passed": passed,
            "query_id": answer["query_id"] if answer else None, "status": answer["status"] if answer else None,
            "expected_status": case["expected_status"], "failure_kind": failure_kind,
            "anonymous_id": row["anonymous_id"], "reviewer": review["reviewer"], "independent_review": grade}
    query_ids = [case["query_id"] for case in reviewed.values() if case["query_id"] is not None]
    if len(query_ids) != len(set(query_ids)):
        raise ValueError("Completed case answers must have distinct original query IDs.")
    reports = []
    for path, dataset_bytes, digest, cases in ((gold_path, gold_bytes, gold_digest, gold),
                                              (adversarial_path, subset_bytes, subset_digest, subset)):
        identity = evaluation_identity(SimpleNamespace(settings=settings), dataset_bytes)
        records = [reviewed[case_id] for case_id in cases]
        passed = sum(record["passed"] for record in records)
        report_id = hashlib.sha256(("independent-release-review\0" + joined_digest + digest + identity["profile_sha256"]).encode()).hexdigest()
        alerts = [] if passed == len(records) else [f"{len(records) - passed} of {len(records)} independently reviewed cases failed; inspect their retained verdicts before release."]
        if any(record["failure_kind"] == "operational" for record in records):
            alerts.append("Operational failures were retained separately; they are not successful knowledge-gap answers.")
        reports.append({"id": report_id, "created_at": joined["created_at"], "suite": "manual-semantic-review",
            "dataset": Path(path).name, **identity, "embedding_model": settings.openrouter_embedding_model,
            "embedding_dimensions": settings.openrouter_embedding_dimensions,
            "answer_pipeline_version": ANSWER_PIPELINE_VERSION,
            "origin": "imported-independent-benchmark-review", "adjudication_sha256": joined_digest,
            "corpus_snapshot_sha256": corpus_digest,
            "review_method": "Imported locked independent Codex benchmark reviews. No app CLI evaluation or model inference was run by this import. Final selected-configuration regression review is independent, not a new blinded comparative selection or human ground truth.",
            "evidence_validation": "Exact answer IDs, text, locators and source attribution match the SHA-pinned 24-source corpus snapshot with frozen source hashes and current enrichment profile. Quotes and routing identities are checked within those immutable records. Sources and query history are not imported into the runtime database.",
            "case_count": len(records), "passed": passed, "pass_rate": passed / len(records),
            "cases": records, "provenance": [item for item in proof if item["case_id"] in cases], "alerts": alerts})
    daily = None
    if all(row["passed"] and row["query_id"] for row in reviewed.values()):
        daily = {**evaluation_identity(SimpleNamespace(settings=settings), gold_bytes), "suite": "held-out-full",
                 "imported_review_id": reports[0]["id"], "origin": "imported-independent-benchmark-review",
                 "completed_at": max(completion_times).isoformat()}
    return reports, daily


def persist_reports(store, reports, daily=None):
    """Atomic and idempotent history append; never replace earlier evaluations."""
    with store.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for report in reports:
            existing = connection.execute("SELECT payload FROM evaluations WHERE id=?", (report["id"],)).fetchone()
            if existing and json.loads(existing[0]) != report:
                raise ValueError("Review ID already exists with a different payload.")
            if not existing:
                connection.execute("INSERT INTO evaluations VALUES(?,?,?)", (report["id"], encode(report), report["created_at"]))
        if daily:
            existing = connection.execute("SELECT id FROM events WHERE kind='evaluation_started' AND json_extract(payload,'$.imported_review_id')=?", (daily["imported_review_id"],)).fetchone()
            if not existing:
                connection.execute("INSERT INTO events(kind,payload,created_at) VALUES(?,?,?)", ("evaluation_started", encode(daily), daily["completed_at"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adjudication", type=Path)
    parser.add_argument("--gold", type=Path, default=ROOT / "data/model_evaluation_gold.json")
    parser.add_argument("--adversarial", type=Path, default=ROOT / "data/evaluation_adversarial.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/evaluation-results/imported-release")
    parser.add_argument("--persist", action="store_true", help="Explicitly append validated reports to current DATA_DIR quality history.")
    args = parser.parse_args()
    settings = Settings()
    try:
        reports, daily = build_reports(args.adjudication, args.gold, args.adversarial, settings)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for report in reports:
            path = args.output_dir / f"{Path(report['dataset']).stem}-{report['id'][:16]}.json"
            if path.exists():
                if read_artifact(path)[0] != report:
                    raise ValueError("Output artifact exists with different contents.")
            else:
                with path.open("x", encoding="utf-8") as handle:
                    json.dump(report, handle, ensure_ascii=False, indent=2)
                    handle.write("\n")
            print(f"Wrote {path.name}: {report['passed']}/{report['case_count']} independent passes.")
        if args.persist:
            persist_reports(Store(settings.data_dir), reports, daily)
            print("Imported review history. No source records, answer snapshots, feedback, or model calls were created.")
        else:
            print("Dry run: artifacts only; runtime quality history was not changed.")
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(2, f"Import rejected: {error}\n")


if __name__ == "__main__":
    main()
