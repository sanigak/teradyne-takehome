"""Only complete, independently bound current-profile reviews may enter quality history."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from app.evaluation import quality
from app.store import Store, encode
from scripts import import_release_review as importer


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture
def artifacts(tmp_path, settings):
    completed = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    reviewed = datetime.now(timezone.utc).isoformat()
    gold = [{"id": f"case-{i}", "question": f"What is the approved policy for case {i}?", "expected_status": "answered"} for i in range(45)]
    options = importer.effective_options(settings)[settings.openrouter_model]
    profile = hashlib.sha256((importer.ENRICH_PROMPT + settings.openrouter_model + json.dumps(options, sort_keys=True)
                              + settings.openrouter_embedding_model + str(settings.openrouter_embedding_dimensions)
                              + "extract-pack-v3").encode()).hexdigest()
    source_gold = [{"filename": f"source-{i}.md", "sha256": hashlib.sha256(f"source-{i}".encode()).hexdigest(),
                    "author": "Fictional Reviewer", "attendees": [], "date": "2026-09-20", "priority": None}
                   for i in range(24)]
    snapshots = []
    for i, entry in enumerate(source_gold):
        metadata = {"title": "Source policy", "author": entry["author"], "attendees": [], "date": entry["date"],
                    "domain": "Policy", "priority": None, "decisions": ["The policy requires approval."], "action_items": [],
                    "enrichment_model": settings.openrouter_model, "enrichment_options": options,
                    "embedding_model": settings.openrouter_embedding_model,
                    "embedding_dimensions": settings.openrouter_embedding_dimensions, "ingestion_profile": profile}
        snapshots.append({"document_id": f"source-doc-{i}", "filename": entry["filename"],
                          "source_sha256": entry["sha256"], "metadata": metadata,
                          "metadata_sha256": importer.canonical_digest(metadata), "chunks": []})
    gold_path, subset_path = tmp_path / "model_evaluation_gold.json", tmp_path / "evaluation_adversarial.json"
    write(gold_path, {"cases": gold, "enrichment_gold": source_gold})
    write(subset_path, gold[:15])
    prompts = {"enrichment": importer.ENRICH_PROMPT, "coverage": importer.COVERAGE_PROMPT,
               "answer": importer.ANSWER_PROMPT, "support": importer.CHECK_PROMPT}
    raw = {"gold_sha256": hashlib.sha256(gold_path.read_bytes()).hexdigest(),
           "answer_pipeline_version": importer.ANSWER_PIPELINE_VERSION,
           "embedding_model": settings.openrouter_embedding_model,
           "embedding_dimensions": settings.openrouter_embedding_dimensions,
           "prompts": prompts, "prompt_sha256": {k: hashlib.sha256(v.encode()).hexdigest() for k, v in prompts.items()},
           "model_options": {settings.openrouter_model: importer.effective_options(settings)},
           "corpus_label": "release-v3-main", "corpus_snapshots": {settings.openrouter_model: snapshots},
           "completed_at": completed, "records": []}
    review = {"reviewer": "Independent fixture reviewer", "records": []}
    for i, case in enumerate(gold):
        evidence = {"chunk_id": f"chunk-{i}", "document_id": f"source-doc-{i % 24}", "filename": f"source-{i % 24}.md",
                    "title": "Source policy", "author": "Fictional Reviewer", "attendees": [], "date": "2026-09-20",
                    "domain": "Policy", "priority": None, "locator": "Paragraph 1", "text": "The policy requires approval."}
        snapshots[i % 24]["chunks"].append({"chunk_id": evidence["chunk_id"], "locator": evidence["locator"],
            "text": evidence["text"], "text_sha256": hashlib.sha256(evidence["text"].encode()).hexdigest(),
            "embedding_model": settings.openrouter_embedding_model})
        answer = {"query_id": f"query-{i}", "question": case["question"], "status": "answered",
                  "claims": [{"text": evidence["text"], "citations": [{"chunk_id": evidence["chunk_id"], "quote": evidence["text"]}]}],
                  "evidence": [evidence], "routing": [], "message": "Supported.", "created_at": completed}
        raw["records"].append({"record_type": "pipeline", "model": settings.openrouter_model,
            "review_model": settings.openrouter_review_model, "case_id": case["id"], "gold": case, "answer": answer})
        review["records"].append({"anonymous_id": f"anonymous-{i}", "case_id": case["id"], "pass": True, "reasons": ["Independently checked."]})
    raw_path, review_path, joined_path = tmp_path / "raw.json", tmp_path / "review.json", tmp_path / "joined.json"
    raw["corpus_snapshot_sha256"] = {settings.openrouter_model: importer.canonical_digest(snapshots)}
    write(raw_path, raw)
    write(review_path, review)
    joined = {"complete": True, "created_at": reviewed, "records": [{
        "source_report": raw_path.name, "source_report_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "record_index": i, "model": settings.openrouter_model, "review_model": settings.openrouter_review_model,
        "case_id": row["case_id"], "anonymous_id": row["anonymous_id"], "review_report": review_path.name,
        "reviewer": review["reviewer"], "passed": True, "failure_kind": None, "original_review": deepcopy(row)}
        for i, row in enumerate(review["records"])]}
    write(joined_path, joined)
    return {"root": tmp_path, "gold": gold_path, "subset": subset_path, "raw": raw_path,
            "review": review_path, "joined": joined_path, "settings": settings}


def build(a):
    return importer.build_reports(a["joined"], a["gold"], a["subset"], a["settings"], workspace=a["root"])


def modify_raw(a, change):
    raw = json.loads(a["raw"].read_text(encoding="utf-8"))
    change(raw)
    write(a["raw"], raw)
    joined = json.loads(a["joined"].read_text(encoding="utf-8"))
    for row in joined["records"]:
        row["source_report_sha256"] = hashlib.sha256(a["raw"].read_bytes()).hexdigest()
    write(a["joined"], joined)


def set_failure(a, index, *, operational=False):
    review = json.loads(a["review"].read_text(encoding="utf-8"))
    review["records"][index]["pass"] = False
    review["records"][index]["reasons"] = ["A real retained finding."]
    write(a["review"], review)
    joined = json.loads(a["joined"].read_text(encoding="utf-8"))
    joined["records"][index].update(passed=False, failure_kind="operational" if operational else "semantic",
                                    original_review=review["records"][index])
    write(a["joined"], joined)
    if operational:
        def change(raw):
            raw["records"][index].pop("answer")
            raw["records"][index]["error_category"] = "timeout"
        modify_raw(a, change)


def test_default_report_construction_is_read_only_and_binds_exact_subsets(artifacts):
    reports, daily = build(artifacts)
    assert not artifacts["settings"].data_dir.exists()
    assert [(r["case_count"], r["passed"]) for r in reports] == [(45, 45), (15, 15)]
    assert {r["dataset"] for r in reports} == {"model_evaluation_gold.json", "evaluation_adversarial.json"}
    assert daily["suite"] == "held-out-full"
    assert daily["profile_sha256"] == reports[0]["profile_sha256"]
    assert daily["completed_at"] != reports[0]["created_at"]
    assert build(artifacts) == (reports, daily)
    assert all(r["origin"] == "imported-independent-benchmark-review" for r in reports)


@pytest.mark.parametrize("change", [
    lambda p: p.pop("answer_pipeline_version"),
    lambda p: p.update(answer_pipeline_version="old-pipeline"),
    lambda p: p.pop("embedding_model"),
    lambda p: p.update(embedding_dimensions=999),
    lambda p: p["prompts"].update(enrichment="Old enrichment rules."),
    lambda p: p["prompt_sha256"].update(answer="0" * 64),
    lambda p: p.update(gold_sha256="0" * 64),
    lambda p: p["model_options"].clear(),
    lambda p: p["records"][0]["answer"].update(question="A substituted question?"),
    lambda p: p["records"][0]["answer"].update(query_id="query-1"),
    lambda p: p["records"][0]["gold"].update(question="A changed gold question?"),
    lambda p: p["records"][0]["answer"]["claims"][0]["citations"][0].update(chunk_id="invented"),
    lambda p: p["records"][0]["answer"]["claims"][0]["citations"][0].update(quote="An invented quotation."),
    lambda p: p["records"][0]["answer"].update(routing=[{"recipient": "Invented Expert", "reason": "Test", "draft_question": "Clarify?", "evidence_ids": ["chunk-0"]}]),
])
def test_current_profile_gold_and_citation_integrity_cannot_be_bypassed(artifacts, change):
    modify_raw(artifacts, change)
    with pytest.raises(ValueError):
        build(artifacts)


def test_effective_options_change_invalidates_prior_reviews(artifacts):
    artifacts["settings"].openrouter_model_options[artifacts["settings"].openrouter_model].max_output_tokens += 1
    with pytest.raises(ValueError, match="effective model options"):
        build(artifacts)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "wrong-model", "bool-string", "changed-review", "escaped-path", "wrong-index"])
def test_incomplete_or_unbound_independent_adjudication_rejected(artifacts, mutation):
    value = json.loads(artifacts["joined"].read_text(encoding="utf-8"))
    if mutation == "missing": value["records"].pop()
    if mutation == "duplicate": value["records"][-1] = deepcopy(value["records"][0])
    if mutation == "wrong-model": value["records"][0]["model"] = "other/model"
    if mutation == "bool-string": value["records"][0]["passed"] = "true"
    if mutation == "changed-review": value["records"][0]["original_review"]["pass"] = False
    if mutation == "escaped-path": value["records"][0]["source_report"] = "../raw.json"
    if mutation == "wrong-index": value["records"][0]["record_index"] = True
    write(artifacts["joined"], value)
    with pytest.raises(ValueError): build(artifacts)


def test_raw_digest_and_original_adversarial_questions_are_not_optional(artifacts):
    artifacts["raw"].write_text(artifacts["raw"].read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="digest changed"): build(artifacts)
    modify_raw(artifacts, lambda _: None)
    subset = json.loads(artifacts["subset"].read_text(encoding="utf-8"))
    subset[0]["question"] = "A rewritten historical question?"
    write(artifacts["subset"], subset)
    with pytest.raises(ValueError, match="subset must match"): build(artifacts)


@pytest.mark.parametrize("bad", [None, [], {"complete": True, "records": [None]}])
def test_malformed_adjudication_reports_are_actionable(artifacts, bad):
    write(artifacts["joined"], bad)
    with pytest.raises(ValueError, match="finalized, complete"):
        build(artifacts)


def test_conflicting_verdict_fields_cannot_be_cherry_picked(artifacts):
    review = json.loads(artifacts["review"].read_text(encoding="utf-8"))
    review["records"][0]["passed"] = False
    write(artifacts["review"], review)
    joined = json.loads(artifacts["joined"].read_text(encoding="utf-8"))
    joined["records"][0]["original_review"] = review["records"][0]
    write(artifacts["joined"], joined)
    with pytest.raises(ValueError, match="explicit, source-bound"):
        build(artifacts)


@pytest.mark.parametrize("operational", [False, True])
def test_failed_verdicts_remain_alerts_and_never_suppress_paid_daily_run(artifacts, operational):
    set_failure(artifacts, 3, operational=operational)
    reports, daily = build(artifacts)
    assert [r["passed"] for r in reports] == [44, 14]
    assert all(r["alerts"] for r in reports)
    assert daily is None
    assert reports[0]["cases"][3]["failure_kind"] == ("operational" if operational else "semantic")


def test_persist_appends_history_idempotently_and_replaces_only_current_suite_findings(artifacts):
    reports, daily = build(artifacts)
    store = Store(artifacts["settings"].data_dir)
    old = {"id": "old-review", "created_at": "2020-01-01T00:00:00+00:00", "suite": "manual-semantic-review",
           "dataset": "evaluation_adversarial.json", "case_count": 15, "passed": 12, "alerts": ["Three old findings."]}
    with store.connect() as db: db.execute("INSERT INTO evaluations VALUES(?,?,?)", (old["id"], encode(old), old["created_at"]))
    importer.persist_reports(store, reports, daily)
    importer.persist_reports(store, reports, daily)
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM evaluations").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM events WHERE kind='evaluation_started'").fetchone()[0] == 1
        assert json.loads(db.execute("SELECT payload FROM evaluations WHERE id='old-review'").fetchone()[0]) == old
        assert db.execute("SELECT count(*) FROM queries").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM documents").fetchone()[0] == 0
    assert quality(store)["alerts"] == []
    assert quality(store)["open_finding_count"] == 0


def test_conflicting_existing_payload_rolls_back_entire_import(artifacts):
    reports, daily = build(artifacts)
    store = Store(artifacts["settings"].data_dir)
    conflict = {**reports[1], "alerts": ["Different review under same ID."]}
    with store.connect() as db:
        db.execute("INSERT INTO evaluations VALUES(?,?,?)", (conflict["id"], encode(conflict), conflict["created_at"]))
    with pytest.raises(ValueError, match="different payload"):
        importer.persist_reports(store, reports, daily)
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM evaluations").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM events").fetchone()[0] == 0


def test_cli_default_writes_artifacts_without_opening_store(artifacts, monkeypatch, capsys):
    actual_builder = importer.build_reports
    monkeypatch.setattr(importer, "build_reports", lambda *args: actual_builder(*args, workspace=artifacts["root"]))
    monkeypatch.setattr(importer, "Settings", lambda: artifacts["settings"])
    monkeypatch.setattr(importer, "Store", lambda _: pytest.fail("Dry run opened a runtime Store"))
    output = artifacts["root"] / "outputs"
    monkeypatch.setattr("sys.argv", ["import_release_review.py", str(artifacts["joined"]), "--gold", str(artifacts["gold"]),
                                     "--adversarial", str(artifacts["subset"]), "--output-dir", str(output)])
    importer.main()
    assert len(list(output.glob("*.json"))) == 2
    assert "runtime quality history was not changed" in capsys.readouterr().out


def snapshot(raw):
    return next(iter(raw["corpus_snapshots"].values()))


def reseal_snapshot(raw):
    raw["corpus_snapshot_sha256"] = {model: importer.canonical_digest(value)
                                     for model, value in raw["corpus_snapshots"].items()}


@pytest.mark.parametrize("field,value", [
    ("document_id", "another-version"), ("chunk_id", "another-chunk"),
    ("filename", "other.md"), ("title", "Approved instead of draft"),
    ("author", "Another Person"), ("attendees", ["Invented Expert"]),
    ("date", "2027-01-01"), ("domain", "Another client"), ("priority", "Critical"),
    ("locator", "Paragraph 99"), ("text", "A forged but internally self-consistent policy."),
])
def test_answer_evidence_must_match_release_corpus_even_when_own_quotes_are_self_consistent(artifacts, field, value):
    def mutate(raw):
        answer = raw["records"][0]["answer"]
        answer["evidence"][0][field] = value
        if field == "chunk_id": answer["claims"][0]["citations"][0]["chunk_id"] = value
        if field == "text": answer["claims"][0]["citations"][0]["quote"] = value
    modify_raw(artifacts, mutate)
    with pytest.raises(ValueError, match="does not match its immutable release corpus"):
        build(artifacts)


@pytest.mark.parametrize("change", [
    lambda raw: raw.pop("corpus_snapshots"),
    lambda raw: raw.pop("corpus_snapshot_sha256"),
    lambda raw: raw.pop("corpus_label"),
    lambda raw: snapshot(raw).pop(),
    lambda raw: snapshot(raw)[0].update(metadata_sha256="0" * 64),
    lambda raw: snapshot(raw)[0]["chunks"][0].update(text_sha256="0" * 64),
])
def test_corpus_proof_is_required_and_outer_digest_detects_mutations(artifacts, change):
    modify_raw(artifacts, change)
    with pytest.raises(ValueError, match="release corpus"):
        build(artifacts)


@pytest.mark.parametrize("change,message", [
    (lambda docs: docs[0].update(source_sha256="0" * 64), "source hash differs"),
    (lambda docs: docs[1].update(document_id=docs[0]["document_id"]), "source IDs"),
    (lambda docs: docs[1].update(filename=docs[0]["filename"]), "source IDs"),
    (lambda docs: docs[0].update(metadata_sha256="0" * 64), "metadata digest"),
    (lambda docs: docs[0]["chunks"][0].update(text="An altered source."), "text digest"),
    (lambda docs: docs[1]["chunks"][0].update(chunk_id=docs[0]["chunks"][0]["chunk_id"]), "chunk identity"),
    (lambda docs: docs[0]["chunks"][0].update(embedding_model="other/embedding"), "embedding profile"),
    (lambda docs: docs[0].update(chunks=[]), "chunk snapshots"),
])
def test_resealing_outer_snapshot_does_not_bypass_nested_source_proof(artifacts, change, message):
    def mutate(raw):
        change(snapshot(raw))
        reseal_snapshot(raw)
    modify_raw(artifacts, mutate)
    with pytest.raises(ValueError, match=message):
        build(artifacts)


@pytest.mark.parametrize("field,value,message", [
    ("author", "Invented Author", "deterministic source attribution"),
    ("priority", "Critical", "deterministic source attribution"),
    ("enrichment_model", "old/model", "current effective source profile"),
    ("enrichment_options", {}, "current effective source profile"),
    ("embedding_dimensions", 1537, "current effective source profile"),
    ("ingestion_profile", "0" * 64, "current effective source profile"),
])
def test_fully_rehashed_metadata_must_still_match_gold_and_current_ingestion_profile(artifacts, field, value, message):
    def mutate(raw):
        item = snapshot(raw)[0]
        item["metadata"][field] = value
        item["metadata_sha256"] = importer.canonical_digest(item["metadata"])
        reseal_snapshot(raw)
    modify_raw(artifacts, mutate)
    with pytest.raises(ValueError, match=message):
        build(artifacts)


def test_joined_answers_cannot_mix_two_otherwise_valid_stochastic_corpus_versions(artifacts):
    alternate = json.loads(artifacts["raw"].read_text(encoding="utf-8"))
    item = snapshot(alternate)[0]
    item["metadata"]["decisions"].append("Another source-faithful phrasing from a separate enrichment run.")
    item["metadata_sha256"] = importer.canonical_digest(item["metadata"])
    reseal_snapshot(alternate)
    alternate_path = artifacts["root"] / "alternate-raw.json"
    write(alternate_path, alternate)
    joined = json.loads(artifacts["joined"].read_text(encoding="utf-8"))
    joined["records"][0].update(source_report=alternate_path.name,
                               source_report_sha256=hashlib.sha256(alternate_path.read_bytes()).hexdigest())
    write(artifacts["joined"], joined)
    with pytest.raises(ValueError, match="one identical release corpus snapshot"):
        build(artifacts)


def test_quality_artifacts_retain_corpus_proof_for_every_case(artifacts):
    reports, _ = build(artifacts)
    raw = json.loads(artifacts["raw"].read_text(encoding="utf-8"))
    digest = next(iter(raw["corpus_snapshot_sha256"].values()))
    for report in reports:
        assert report["corpus_snapshot_sha256"] == digest
        assert {item["corpus_snapshot_sha256"] for item in report["provenance"]} == {digest}
