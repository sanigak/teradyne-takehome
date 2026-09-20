"""Prepare UTF-8 blind review packets; model mappings belong in ignored runtime data."""
import argparse
import json
from pathlib import Path
import random
import secrets

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def blind_reports(paths, output, mapping_path, record_type, parts=1, per_group=None, exclude_mappings=(), skip_credit_errors=False):
    if parts < 1 or parts > 3:
        raise ValueError("Use one to three balanced independent-review packets.")
    if per_group is not None and per_group < 1:
        raise ValueError("Per-group batch size must be positive.")
    outputs = [output] if parts == 1 else [output.with_stem(output.stem + f"-part{index + 1}") for index in range(parts)]
    if any(path.exists() for path in outputs) or mapping_path.exists():
        raise ValueError("Preserve existing review packets; choose a new packet name.")
    records, selected_counts, excluded = [], {}, set()
    for excluded_path in exclude_mappings:
        previous = json.loads(excluded_path.read_text(encoding="utf-8"))
        excluded.update((str(Path(value["source_report"]).resolve()), value["record_index"]) for value in previous.values())
    for path in paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        for index, record in enumerate(report["records"]):
            if record["record_type"] == record_type and ("answer" in record or "result" in record or "error_category" in record):
                if skip_credit_errors and record.get("error_category") in {"credits", "benchmark_upstream_pause", "temporary_capacity", "in_flight_budget", "capacity", "key_limit", "request_budget"}:
                    continue
                if (str(path.resolve()), index) in excluded:
                    continue
                group = (record["model"], record.get("review_model"))
                if per_group is not None and selected_counts.get(group, 0) >= per_group:
                    continue
                selected_counts[group] = selected_counts.get(group, 0) + 1
                records.append((path, index, record, report["gold_sha256"]))
    random.SystemRandom().shuffle(records)
    packets, mapping, group_counts = [[] for _ in range(parts)], {}, {}
    for path, index, record, digest in records:
        anonymous = "answer-" + secrets.token_hex(4)
        value = {"anonymous_id": anonymous, "gold": record["gold"], "gold_sha256": digest}
        if "error_category" in record:
            value.update(answer=None, operational_error={"category": record["error_category"], "message": record["error"]})
        elif record_type == "pipeline":
            value["answer"] = {key: content for key, content in record["answer"].items() if key not in {"query_id", "created_at"}}
        else:
            value.update(filename=record["filename"], source_text=record["source_text"], enrichment=record["result"],
                         attribution_stable=record.get("attribution_stable"), source_hash_stable=record.get("source_hash_stable"))
        identity = (record["model"], record.get("review_model"))
        counts = group_counts.setdefault(identity, [0] * parts)
        part = counts.index(min(counts))
        counts[part] += 1
        packets[part].append(value)
        mapping[anonymous] = {"source_report": str(path), "record_index": index, "model": record["model"],
                              "review_model": record.get("review_model"), "case_id": record.get("case_id"), "filename": record.get("filename"), "repeat": record.get("repeat")}
    for path, packet in zip(outputs, packets):
        write_json(path, {"instructions": "Grade frozen required facts, exact own-citation support, scope, completeness and routing independently. For enrichment, require explicit source decisions/actions and faithful domain/priority, not every background fact. Models, latency, costs and automatic verdicts are hidden.", "record_type": record_type, "records": packet})
    write_json(mapping_path, mapping)
    return sum(map(len, packets))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--record-type", choices=["pipeline", "enrichment"], default="pipeline")
    parser.add_argument("--parts", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--per-group", type=int, help="Freeze up to this many previously unassigned answers from each model/reviewer configuration.")
    parser.add_argument("--exclude-mapping", nargs="*", type=Path, default=[])
    parser.add_argument("--skip-credit-errors", action="store_true", help="For post-restoration adjudication, defer pre-completion credit failures to their explicit retry records; original reports remain unchanged.")
    args = parser.parse_args()
    if not args.mapping.resolve().is_relative_to(ROOT / ".runtime"):
        raise ValueError("Model mapping must stay in ignored .runtime data.")
    print(blind_reports(args.reports, args.output, args.mapping, args.record_type, args.parts, args.per_group, args.exclude_mapping, args.skip_credit_errors))
