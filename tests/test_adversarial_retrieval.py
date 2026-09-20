import pytest

from app.provider import ProviderError
from app.retrieval import cosine
from app.service import KnowledgeService


@pytest.mark.parametrize("magnitude", [1e-300, 1e308])
def test_cosine_preserves_similarity_at_extreme_finite_scales(magnitude):
    assert cosine([magnitude, magnitude, 0], [magnitude, magnitude, 0]) == pytest.approx(1)
    assert cosine([magnitude, 0, 0], [0, magnitude, 0]) == 0
    assert cosine([magnitude, 0, 0], [-magnitude, 0, 0]) == -1


@pytest.mark.parametrize("corrupted", ['null', '"100"', '[true, false, false]', '[NaN, 0, 1]', '[1e999,0,1]', '[0,0,0]', 'not-json'])
async def test_corrupt_stored_vector_is_operational_error_not_gap(corrupted, settings, store, provider, ingested):
    with store.connect() as conn:
        conn.execute("UPDATE chunks SET embedding=?", (corrupted,))
    with pytest.raises(ProviderError) as failure:
        await KnowledgeService(settings, store, provider).query("What approval does Atlas require?")
    assert failure.value.category == "invalid_embedding"
    assert store.reviews()["items"] == []
    assert store.metrics()["query_count"] == 0
