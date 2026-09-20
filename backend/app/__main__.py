import argparse
import asyncio
import json
import sys
from pathlib import Path

from .config import Settings
from .evaluation import evaluate
from .ingestion import ingest_directory
from .models import Enrichment
from .provider import OpenRouter, ProviderError
from .service import KnowledgeService
from .store import Store


async def run(args):
    settings = Settings()
    store = Store(settings.data_dir)
    provider = OpenRouter(settings, store)
    try:
        if args.command == "ingest":
            result = await ingest_directory(Path(args.path) if args.path else settings.corpus_dir, store=store, provider=provider, settings=settings, force=args.force)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 1 if result["failed"] else 0
        if args.command == "evaluate":
            result = await evaluate(KnowledgeService(settings, store, provider), limit=args.limit)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result["passed"] == result["case_count"] else 1
        if args.command == "smoke":
            async with asyncio.timeout(settings.operation_timeout_seconds):
                await provider.structured(Enrichment, "Extract only explicit metadata from this text. Use domain='smoke test', priority=null, empty decisions and action_items.", {"text": "Connectivity smoke test."})
                vectors = await provider.embeddings(["Connectivity smoke test."])
            print(json.dumps({"status": "ok", "model": settings.openrouter_model, "embedding_model": settings.openrouter_embedding_model, "embedding_dimensions": len(vectors[0])}, indent=2))
            return 0
    except (ProviderError, ValueError, TimeoutError) as exc:
        print(json.dumps({"error": str(exc) or "Operation timed out."}), file=sys.stderr)
        return 1
    finally:
        await provider.close()


def main():
    parser = argparse.ArgumentParser(description="Knowledge workspace ingestion, evaluation, and live provider verification.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    ingest = subcommands.add_parser("ingest", help="Extract, enrich, embed, and version corpus documents using OpenRouter.")
    ingest.add_argument("path", nargs="?", help="Corpus directory (default: data/corpus).")
    ingest.add_argument("--force", action="store_true", help="Create fresh document versions and rerun enrichment even when content is unchanged.")
    evaluation = subcommands.add_parser("evaluate", help="Run the held-out evaluation and persist quality results.")
    evaluation.add_argument("--limit", type=int, help="Run only the first N cases.")
    subcommands.add_parser("smoke", help="Explicit live OpenRouter structured-output and embeddings smoke test (uses credits).")
    args = parser.parse_args()
    if getattr(args, "limit", None) is not None and args.limit < 1:
        parser.error("--limit must be positive")
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
