"""Join already locked blind reviews to immutable benchmark answers; no inference."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def join_reviews(review_paths, mapping_paths, output, expected_per_configuration):
    mapping = {}
    for path in mapping_paths:
        for anonymous_id, item in read(path).items():
            if anonymous_id in mapping:
                raise ValueError("Duplicate anonymous ID in mappings")
            mapping[anonymous_id] = item
    records, seen = [], set()
    for path in review_paths:
        review = read(path)
        for grade in review.get("answers", review.get("records", [])):
            anonymous_id = grade["anonymous_id"]
            original = mapping[anonymous_id]
            source = Path(original["source_report"].replace("\\", "/"))
            source = source if source.is_absolute() else ROOT / source
            raw = read(source)["records"][original["record_index"]]
            key = (original["model"], original.get("review_model"), original.get("case_id") or original["filename"], raw.get("repeat"))
            if key in seen:
                raise ValueError("Duplicate model/case or model/source adjudication")
            seen.add(key)
            if (raw["model"] != original["model"] or raw.get("case_id") != original.get("case_id")
                    or raw.get("filename") != original.get("filename")
                    or raw.get("review_model") != original.get("review_model")
                    or grade.get("case_id", original.get("case_id")) != original.get("case_id")
                    or grade.get("filename", original.get("filename")) != original.get("filename")):
                raise ValueError("Mapping no longer matches original record")
            passed = grade.get("pass", grade.get("passed"))
            if not isinstance(passed, bool):
                raise ValueError("Every independent verdict must be explicitly boolean")
            records.append({**original, "repeat": raw.get("repeat"), "source_report": source.relative_to(ROOT).as_posix(),
                            "source_report_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                            "anonymous_id": anonymous_id,
                            "review_report": path.resolve().relative_to(ROOT).as_posix(),
                            "reviewer": review["reviewer"], "passed": passed,
                            "failure_kind": "operational" if "error_category" in raw else (None if passed else "semantic"),
                            "original_review": grade})
    groups = defaultdict(list)
    for row in records:
        groups[(row["model"], row.get("review_model"))].append(row)
    summaries = []
    for (model, review_model), rows in sorted(groups.items()):
        if len(rows) > expected_per_configuration:
            raise ValueError("More adjudications than expected cases")
        summaries.append({"model": model, "review_model": review_model, "reviewed": len(rows),
                          "expected": expected_per_configuration, "pending": expected_per_configuration - len(rows),
                          "passed": sum(row["passed"] for row in rows),
                          "semantic_failures": sum(row["failure_kind"] == "semantic" for row in rows),
                          "operational_failures": sum(row["failure_kind"] == "operational" for row in rows)})
    result = {"created_at": datetime.now(timezone.utc).isoformat(),
              "method": "Mechanical join of locked independent Codex-agent blind grades, not a new judge or human review. Original answer records and verdicts remain unchanged.",
              "complete": all(row["pending"] == 0 for row in summaries), "configurations": summaries, "records": records}
    if output.exists():
        raise ValueError("Refusing to overwrite an adjudication artifact")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, nargs="+", required=True)
    parser.add_argument("--mappings", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-per-configuration", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(join_reviews(args.reviews, args.mappings, args.output, args.expected_per_configuration)["configurations"]))
