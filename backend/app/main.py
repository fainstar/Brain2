from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.dependencies import build_pipeline
from app.models import (
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationRecord,
    GraphResponse,
    HealthResponse,
    IngestRequest,
    MemoryListResponse,
    QueryRequest,
)
from app.services.conversation_store import ConversationStore

app = FastAPI(title="Second Brain Backend", version="1.0.0")
pipeline = build_pipeline()
conversation_store = ConversationStore(file_path=f"{settings.backend_data_dir}/conversations.json")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    llm_ok = await pipeline.llm.ping()
    vector_ok = await pipeline.vector_store.ping()
    graph_ok = await pipeline.graph_store.ping()
    return HealthResponse(
        ok=llm_ok and vector_ok and graph_ok,
        llm="ok" if llm_ok else "down",
        vector_store="ok" if vector_ok else "down",
        graph_store="ok" if graph_ok else "down",
    )


@app.post("/ingest")
async def ingest(payload: IngestRequest):
    result = await pipeline.ingest(payload)
    return JSONResponse(content=result.model_dump(mode="json"))


@app.post("/query")
async def query(payload: QueryRequest):
    result = await pipeline.query(payload)
    return JSONResponse(content=result.model_dump(mode="json"))


@app.get("/memory", response_model=MemoryListResponse)
async def memory(limit: int = 50):
    notes = await pipeline.vector_store.list_notes(limit=limit)
    return MemoryListResponse(
        items=[
            {
                "note_id": n.note_id,
                "text": n.text,
                "metadata": n.metadata,
            }
            for n in notes
        ]
    )


@app.get("/memory/{note_id}")
async def memory_get(note_id: str):
    note = await pipeline.vector_store.get_note(note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="note not found")
    return {
        "note_id": note.note_id,
        "text": note.text,
        "metadata": note.metadata,
    }


@app.delete("/memory/{note_id}")
async def memory_delete(note_id: str, confirm: str | None = None):
    if confirm is not None and confirm != note_id:
        raise HTTPException(status_code=400, detail="confirm must equal note_id")

    deleted_vector = await pipeline.vector_store.delete_note(note_id)
    deleted_graph = await pipeline.graph_store.delete_note(note_id)

    if not deleted_vector and not deleted_graph:
        raise HTTPException(status_code=404, detail="note not found")

    return {
        "deleted": True,
        "note_id": note_id,
        "vector_deleted": deleted_vector,
        "graph_deleted": deleted_graph,
    }


@app.get("/memory/search", response_model=MemoryListResponse)
async def memory_search(q: str, top_k: int = 10):
    embedding = await pipeline.llm.embed(q)
    notes = await pipeline.vector_store.search(q, embedding, top_k=top_k)
    return MemoryListResponse(
        items=[
            {
                "note_id": n.note_id,
                "text": n.text,
                "metadata": n.metadata,
            }
            for n in notes
        ]
    )


@app.get("/graph", response_model=GraphResponse)
async def graph(limit: int = 200):
    data = await pipeline.graph_store.graph_snapshot(limit=limit)
    return GraphResponse(nodes=data.get("nodes", []), edges=data.get("edges", []))


@app.post("/conversations", response_model=ConversationRecord)
async def conversation_create(payload: ConversationCreateRequest):
    row = await conversation_store.add(
        question=payload.question,
        answer=payload.answer,
        note_id=payload.note_id,
        metadata=payload.metadata,
    )
    return ConversationRecord(**row)


@app.get("/conversations", response_model=ConversationListResponse)
async def conversation_list(limit: int = 100):
    rows = await conversation_store.list(limit=limit)
    return ConversationListResponse(items=[ConversationRecord(**r) for r in rows])


@app.delete("/conversations/{conversation_id}")
async def conversation_delete(conversation_id: str):
    deleted = await conversation_store.delete(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"deleted": True, "conversation_id": conversation_id}


@app.delete("/conversations")
async def conversation_clear_all():
    removed = await conversation_store.clear()
    return {"deleted": True, "removed": removed}
