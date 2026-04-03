from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
import time
from typing import Dict, List, Protocol

import chromadb

from app.config import settings


@dataclass
class RetrievedChunk:
    note_id: str
    text: str
    score: float
    metadata: Dict[str, str]


class VectorStore(Protocol):
    async def add_note(self, note_id: str, text: str, embedding: List[float], metadata: Dict[str, str]) -> None: ...
    async def search(self, query: str, query_embedding: List[float], top_k: int) -> List[RetrievedChunk]: ...
    async def list_notes(self, limit: int = 50) -> List[RetrievedChunk]: ...
    async def get_note(self, note_id: str) -> RetrievedChunk | None: ...
    async def delete_note(self, note_id: str) -> bool: ...
    async def ping(self) -> bool: ...


class ChromaVectorStore:
    def __init__(self) -> None:
        last_error: Exception | None = None
        self.client = None
        self.collection = None

        for _ in range(30):
            try:
                self.client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
                self.collection = self.client.get_or_create_collection(name=settings.chroma_collection)
                return
            except Exception as exc:
                last_error = exc
                time.sleep(2)

        raise RuntimeError(f"Failed to connect to Chroma after retries: {last_error}")

    async def add_note(self, note_id: str, text: str, embedding: List[float], metadata: Dict[str, str]) -> None:
        self.collection.add(ids=[note_id], documents=[text], embeddings=[embedding], metadatas=[metadata])

    async def search(self, query: str, query_embedding: List[float], top_k: int) -> List[RetrievedChunk]:
        result = self.collection.query(query_embeddings=[query_embedding], n_results=top_k)
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        distances = result.get("distances", [[]])[0]
        metas = result.get("metadatas", [[]])[0]
        chunks = []
        for note_id, doc, dist, meta in zip(ids, docs, distances, metas):
            score = 1 / (1 + float(dist))
            chunks.append(RetrievedChunk(note_id=note_id, text=doc, score=score, metadata=meta or {}))
        return chunks

    async def list_notes(self, limit: int = 50) -> List[RetrievedChunk]:
        result = self.collection.get(limit=limit, include=["documents", "metadatas"])
        ids = result.get("ids", [])
        docs = result.get("documents", [])
        metas = result.get("metadatas", [])
        chunks = []
        for note_id, doc, meta in zip(ids, docs, metas):
            chunks.append(RetrievedChunk(note_id=note_id, text=doc, score=1.0, metadata=meta or {}))

        chunks.sort(key=lambda c: c.metadata.get("timestamp", ""), reverse=True)
        return chunks[:limit]

    async def get_note(self, note_id: str) -> RetrievedChunk | None:
        result = self.collection.get(ids=[note_id], include=["documents", "metadatas"])
        ids = result.get("ids", [])
        if not ids:
            return None
        docs = result.get("documents", [""])
        metas = result.get("metadatas", [{}])
        return RetrievedChunk(note_id=note_id, text=docs[0], score=1.0, metadata=metas[0] or {})

    async def delete_note(self, note_id: str) -> bool:
        existing = await self.get_note(note_id)
        if existing is None:
            return False
        self.collection.delete(ids=[note_id])
        return True

    async def ping(self) -> bool:
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._items: Dict[str, Dict] = {}

    async def add_note(self, note_id: str, text: str, embedding: List[float], metadata: Dict[str, str]) -> None:
        self._items[note_id] = {"text": text, "embedding": embedding, "metadata": metadata}

    def _cosine(self, a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sqrt(sum(x * x for x in a)) or 1.0
        nb = sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)

    async def search(self, query: str, query_embedding: List[float], top_k: int) -> List[RetrievedChunk]:
        scored = []
        for note_id, item in self._items.items():
            score = self._cosine(query_embedding, item["embedding"])
            scored.append(
                RetrievedChunk(
                    note_id=note_id,
                    text=item["text"],
                    score=score,
                    metadata=item["metadata"],
                )
            )
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    async def list_notes(self, limit: int = 50) -> List[RetrievedChunk]:
        items = []
        for note_id, item in self._items.items():
            items.append(
                RetrievedChunk(
                    note_id=note_id,
                    text=item["text"],
                    score=1.0,
                    metadata=item["metadata"],
                )
            )
        items.sort(key=lambda c: c.metadata.get("timestamp", ""), reverse=True)
        return items[:limit]

    async def get_note(self, note_id: str) -> RetrievedChunk | None:
        item = self._items.get(note_id)
        if not item:
            return None
        return RetrievedChunk(
            note_id=note_id,
            text=item["text"],
            score=1.0,
            metadata=item["metadata"],
        )

    async def delete_note(self, note_id: str) -> bool:
        return self._items.pop(note_id, None) is not None

    async def ping(self) -> bool:
        return True
