import json
import math
import re

from .config import Settings
from .ingestion import cached_embeddings
from .models import Evidence
from .provider import ProviderError
from .store import Store

STOPWORDS = set("a an and are as at be by can could did do does for from had has have how i in is it of on or our that the their this to was we were what when where which who why will with would you your tell me about please".split())


def cosine(a, b):
    if len(a) != len(b):
        raise ProviderError("Embedding dimensions changed. Re-ingest the corpus with the configured embedding model.", category="embedding_mismatch", status_code=503)
    denominator = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / denominator if denominator else 0


def evidence_from_row(row) -> Evidence:
    metadata = json.loads(row["metadata"])
    return Evidence(chunk_id=row["id"], document_id=row["document_id"], filename=row["filename"],
                    title=metadata["title"], author=metadata["author"], attendees=metadata["attendees"],
                    date=metadata["date"], domain=metadata["domain"], priority=metadata["priority"],
                    locator=row["locator"], text=row["text"])


async def retrieve(question: str, *, store: Store, provider, settings: Settings) -> list[Evidence]:
    with store.connect() as conn:
        rows = conn.execute("SELECT c.*,d.filename,d.metadata FROM chunks c JOIN documents d ON c.document_id=d.id WHERE d.active=1").fetchall()
        if not rows:
            raise ProviderError("The knowledge corpus is empty. Run python -m app ingest before asking questions.", category="empty_corpus", status_code=503)
        if any(row["embedding_model"] != settings.openrouter_embedding_model for row in rows):
            raise ProviderError("The embedding model changed. Re-ingest the corpus before querying.", category="embedding_mismatch", status_code=503)
        if any(len(json.loads(row["embedding"])) != settings.openrouter_embedding_dimensions for row in rows):
            raise ProviderError("Embedding dimensions changed. Re-ingest the corpus before querying.", category="embedding_mismatch", status_code=503)
        terms = list(dict.fromkeys(term for term in re.findall(r"[\w]+", question.lower()) if len(term) > 2 and term not in STOPWORDS))[:24]
        match = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
        lexical = conn.execute("SELECT f.chunk_id,bm25(chunks_fts) AS score FROM chunks_fts f JOIN chunks c ON c.id=f.chunk_id JOIN documents d ON d.id=c.document_id WHERE chunks_fts MATCH ? AND d.active=1 ORDER BY score LIMIT 30", (match,)).fetchall() if match else []
    query_vector = (await cached_embeddings(store, provider, settings, [question]))[0]
    semantic = sorted(((row["id"], cosine(query_vector, json.loads(row["embedding"]))) for row in rows), key=lambda item: item[1], reverse=True)
    # Reciprocal-rank fusion uses independent text and semantic ranks. The LLM
    # performs a separate relevance gate before any answer or named routing.
    scores = {}
    for rank, row in enumerate(lexical):
        scores[row["chunk_id"]] = scores.get(row["chunk_id"], 0) + 1 / (60 + rank + 1)
    for rank, (chunk_id, similarity) in enumerate(semantic):
        if similarity >= settings.semantic_min_similarity:
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (60 + rank + 1)
    selected = sorted(scores, key=scores.get, reverse=True)[:settings.retrieval_limit]
    by_id = {row["id"]: row for row in rows}
    return [evidence_from_row(by_id[chunk_id]) for chunk_id in selected]
