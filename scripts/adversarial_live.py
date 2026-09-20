"""Explicit live audit in a SQLite backup: never mutates the normal workspace.

Run after corpus ingestion. Uses the same real OpenRouter pipeline as the app.
The report includes answer snapshots for manual semantic review, not just scores.
"""
import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

from app.config import ROOT, Settings
from app.evaluation import evaluate
from app.ingestion import ingest_file
from app.provider import OpenRouter
from app.retrieval import retrieve
from app.source_safety import source_instruction_warnings
from app.service import KnowledgeService
from app.store import Store


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/evaluation_adversarial.json")
    parser.add_argument("--output-dir", type=Path, required=True, help="New audit directory under .runtime")
    parser.add_argument("--injection-fixture", type=Path, help="Optional test-only source, ingested ONLY into the audit copy")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    runtime = (ROOT / ".runtime").resolve()
    if not output.is_relative_to(runtime) or output == runtime or output.exists():
        parser.error("Use a NEW subdirectory of .runtime; existing state is never overwritten.")
    settings = Settings()
    original = settings.data_dir / "workspace.sqlite3"
    if not original.is_file() or not settings.configured:
        parser.error("Ingest the corpus and configure backend OPENROUTER_API_KEY first.")
    output.mkdir(parents=True)
    with sqlite3.connect(original) as source, sqlite3.connect(output / "workspace.sqlite3") as destination:
        source.backup(destination)
        # Keep immutable document/version/cache data, but no old user history.
        for table in ("feedback", "review", "outbox", "queries", "events", "evaluations"):
            destination.execute(f"DELETE FROM {table}")
    settings = settings.model_copy(update={"data_dir": output, "daily_evaluation": False, "evaluation_path": args.dataset.resolve()})
    store = Store(output)
    provider = OpenRouter(settings, store)
    try:
        injection_outcome = None
        retrieval_candidates = {}
        screened = []
        if args.injection_fixture:
            source_path = output / "corpus" / args.injection_fixture.name
            source_path.parent.mkdir()
            source_path.write_bytes(args.injection_fixture.read_bytes())
            injection_outcome = await ingest_file(source_path, store=store, provider=provider, settings=settings)
            if injection_outcome["status"] != "ingested":
                raise RuntimeError("The injection source was not ingested; this test would be inconclusive.")
            screened = source_instruction_warnings(source_path.read_text(encoding="utf-8"))
            for case in json.loads(args.dataset.read_text(encoding="utf-8")):
                candidates = await retrieve(case["question"], store=store, provider=provider, settings=settings)
                retrieval_candidates[case["id"]] = [item.filename for item in candidates]
                if source_path.name not in retrieval_candidates[case["id"]] and not screened:
                    raise RuntimeError(f"Injection source was not retrieved for {case['id']}; test is inconclusive.")
                if screened and source_path.name in retrieval_candidates[case["id"]]:
                    raise RuntimeError("Flagged injection source reached retrieval candidates.")
        result = await evaluate(KnowledgeService(settings, store, provider))
        report = {"evaluation": result, "answers": {case["id"]: store.get_query(case["query_id"]) for case in result["cases"] if case.get("query_id")}}
        if injection_outcome:
            report.update(injection_ingestion=injection_outcome, retrieval_candidates=retrieval_candidates, instruction_screening=screened)
        (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"passed": result["passed"], "cases": result["case_count"], "alerts": result["alerts"], "report": str(output / "report.json")}, indent=2))
        if result["passed"] != result["case_count"]:
            raise SystemExit(1)
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
