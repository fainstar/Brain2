import pytest
from datetime import datetime, timezone

from app.models import Entity, Relation
from app.services.graph_store import InMemoryGraphStore
from app.services.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_delete_memory_from_vector_and_graph():
    vector_store = InMemoryVectorStore()
    graph_store = InMemoryGraphStore()

    note_id = "note-test-delete-1"
    text = "API 架構要重構，但怕影響效能"
    metadata = {"timestamp": "2026-04-03T00:00:00+00:00", "source": "test"}

    await vector_store.add_note(note_id, text, [1.0, 2.0, 3.0], metadata)
    await graph_store.upsert_note_graph(
        note_id=note_id,
        text=text,
        intent="status_log",
        tags=["api", "效能"],
        entities=[Entity(name="API架構", type="Concept"), Entity(name="效能", type="Metric")],
        relations=[Relation(source="API架構", target="效能", type="AFFECTS")],
        timestamp=datetime.now(timezone.utc),
    )

    assert await vector_store.get_note(note_id) is not None
    assert await graph_store.delete_note(note_id) is True
    assert await vector_store.delete_note(note_id) is True
    assert await vector_store.get_note(note_id) is None
