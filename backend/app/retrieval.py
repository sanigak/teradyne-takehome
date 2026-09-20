import json
import math
import re

from .config import Settings
from .ingestion import cached_embeddings
from .models import Evidence
from .provider import ProviderError
from .source_safety import source_instruction_warnings
from .store import Store

STOPWORDS = set("a an and are as at be by can could did do does for from had has have how i in is it of on or our that the their this to was we were what when where which who why will with would you your tell me about please".split())


def cosine(a, b):
    try:
        if any(not isinstance(vector, list) or not vector or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector) for vector in (a, b)):
            raise ValueError
        scales = (max(abs(x) for x in a), max(abs(x) for x in b))
        if not all(scales):
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ProviderError("Stored embeddings are invalid. Re-ingest the corpus to rebuild them.", category="invalid_embedding", status_code=503) from None
    if len(a) != len(b):
        raise ProviderError("Embedding dimensions changed. Re-ingest the corpus with the configured embedding model.", category="embedding_mismatch", status_code=503)
    # Scaling avoids overflow/underflow even for finite upstream vectors with
    # extreme magnitudes. Invalid vectors are operational errors, never gaps.
    left, right = [x / scales[0] for x in a], [x / scales[1] for x in b]
    denominator = math.hypot(*left) * math.hypot(*right)
    return max(-1.0, min(1.0, math.fsum(x * y for x, y in zip(left, right)) / denominator))


def evidence_from_row(row) -> Evidence:
    metadata = json.loads(row["metadata"])
    return Evidence(chunk_id=row["id"], document_id=row["document_id"], filename=row["filename"],
                    title=metadata["title"], author=metadata["author"], attendees=metadata["attendees"],
                    date=metadata["date"], domain=metadata["domain"], priority=metadata["priority"],
                    locator=row["locator"], text=row["text"])


def quarantined_documents(rows):
    """Scan every active chunk, not only selected matches of a flagged file."""
    documents = {}
    for row in rows:
        documents.setdefault(row["document_id"], []).append(row["text"])
    return {doc_id: warnings for doc_id, parts in documents.items()
            if (warnings := source_instruction_warnings("\n\n".join(parts)))}


async def retrieve(question: str, *, store: Store, provider, settings: Settings) -> list[Evidence]:
    with store.connect() as conn:
        rows = conn.execute("SELECT c.*,d.filename,d.metadata FROM chunks c JOIN documents d ON c.document_id=d.id WHERE d.active=1").fetchall()
        if not rows:
            raise ProviderError("The knowledge corpus is empty. Run python -m app ingest before asking questions.", category="empty_corpus", status_code=503)
        quarantined = quarantined_documents(rows)
        if quarantined:
            store.event("source_quarantine", {"documents": quarantined})
            rows = [row for row in rows if row["document_id"] not in quarantined]
        if not rows:
            raise ProviderError("All available sources contain instructions aimed at the AI system and are excluded from answers. Review the source files and re-ingest corrected documents.", category="untrusted_sources", status_code=503)
        if any(row["embedding_model"] != settings.openrouter_embedding_model for row in rows):
            raise ProviderError("The embedding model changed. Re-ingest the corpus before querying.", category="embedding_mismatch", status_code=503)
        try:
            vectors = {row["id"]: json.loads(row["embedding"]) for row in rows}
        except (ValueError, TypeError, RecursionError):
            raise ProviderError("Stored embeddings are invalid. Re-ingest the corpus to rebuild them.", category="invalid_embedding", status_code=503) from None
        if any(not isinstance(vector, list) for vector in vectors.values()):
            raise ProviderError("Stored embeddings are invalid. Re-ingest the corpus to rebuild them.", category="invalid_embedding", status_code=503)
        if any(len(vector) != settings.openrouter_embedding_dimensions for vector in vectors.values()):
            raise ProviderError("Embedding dimensions changed. Re-ingest the corpus before querying.", category="embedding_mismatch", status_code=503)
        terms = list(dict.fromkeys(term for term in re.findall(r"[\w]+", question.lower()) if len(term) > 2 and term not in STOPWORDS))[:24]
        match = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
        lexical = conn.execute("SELECT f.chunk_id,bm25(chunks_fts) AS score FROM chunks_fts f JOIN chunks c ON c.id=f.chunk_id JOIN documents d ON d.id=c.document_id WHERE chunks_fts MATCH ? AND d.active=1 ORDER BY score LIMIT 30", (match,)).fetchall() if match else []
    query_vector = (await cached_embeddings(store, provider, settings, [question]))[0]
    semantic = sorted(((row["id"], cosine(query_vector, vectors[row["id"]])) for row in rows), key=lambda item: item[1], reverse=True)
    # Reciprocal-rank fusion uses independent text and semantic ranks. The LLM
    # performs a separate relevance gate before any answer or named routing.
    scores = {}
    eligible = {row["id"] for row in rows}
    for rank, row in enumerate(lexical):
        if row["chunk_id"] not in eligible:
            continue
        scores[row["chunk_id"]] = scores.get(row["chunk_id"], 0) + 1 / (60 + rank + 1)
    for rank, (chunk_id, similarity) in enumerate(semantic):
        if similarity >= settings.semantic_min_similarity:
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (60 + rank + 1)
    selected = sorted(scores, key=scores.get, reverse=True)[:settings.retrieval_limit]
    by_id = {row["id"]: row for row in rows}
    return [evidence_from_row(by_id[chunk_id]) for chunk_id in selected]
