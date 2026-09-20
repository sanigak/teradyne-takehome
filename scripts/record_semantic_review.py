"""Persist an explicitly authored semantic-review report in local quality history.

This imports review findings, not source truth or user feedback. No model calls.
"""
import argparse
import json
from pathlib import Path

from app.config import Settings
from app.store import Store, encode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = json.loads(args.report.read_text(encoding="utf-8"))
    if result.get("suite") != "manual-semantic-review" or not result.get("review_method") or not result.get("cases"):
        parser.error("Expected an explicitly authored manual-semantic-review report with case verdicts.")
    if result["case_count"] != len(result["cases"]) or result["passed"] != sum(case["passed"] for case in result["cases"]):
        parser.error("Review counts disagree with case verdicts.")
    store = Store(Settings().data_dir)
    with store.connect() as conn:
        existing = conn.execute("SELECT payload FROM evaluations WHERE id=?", (result["id"],)).fetchone()
        if existing:
            if json.loads(existing[0]) != result:
                parser.error("This review ID already exists with different findings; create a new report.")
            print("Review already recorded; no change.")
            return
        conn.execute("INSERT INTO evaluations VALUES(?,?,?)", (result["id"], encode(result), result["created_at"]))
    print(f"Recorded semantic review: {result['passed']}/{result['case_count']}; {len(result['alerts'])} quality alerts.")


if __name__ == "__main__":
    main()
