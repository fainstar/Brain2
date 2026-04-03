import pytest

from app.services.conversation_store import ConversationStore


@pytest.mark.asyncio
async def test_conversation_store_crud(tmp_path):
    store = ConversationStore(str(tmp_path / "conversations.json"))

    row = await store.add(
        question="我該不該重構？",
        answer="先量測再重構",
        note_id="note-1",
        metadata={"used_note_ids": ["note-1"]},
    )
    assert row["id"].startswith("conv-")

    listed = await store.list(limit=10)
    assert len(listed) == 1
    assert listed[0]["question"] == "我該不該重構？"

    deleted = await store.delete(row["id"])
    assert deleted is True
    listed_after = await store.list(limit=10)
    assert listed_after == []


@pytest.mark.asyncio
async def test_conversation_store_clear_all(tmp_path):
    store = ConversationStore(str(tmp_path / "conversations.json"))

    await store.add("Q1", "A1", None, {})
    await store.add("Q2", "A2", None, {})

    removed = await store.clear()
    assert removed == 2
    assert await store.list(limit=10) == []
