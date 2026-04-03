from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator, Dict, List, Tuple
from uuid import uuid4

from app.models import Entity, IngestRequest, IngestResponse, QueryRequest, QueryResponse, Relation
from app.services.graph_store import GraphStore
from app.services.llm_client import LLMClient
from app.services.vector_store import RetrievedChunk, VectorStore
from app.utils import dedupe_preserve_order, generate_tags, parse_json_block


SYSTEM_PROMPT = """你現在是我的私人決策輔助大腦。我的輸入通常是高度抽象的想法、情緒或片段的技術觀察。
你的任務不是急著解決問題，而是「釐清狀態」。

處理規則：
1. 若我的輸入包含模糊詞彙（如：怪怪的、不太好、有瓶頸），你必須反問我具體的指標或情境。
2. 從我的描述中，主動尋找與過去資訊的「矛盾點」或「潛在關聯」。
3. 輸出格式請保持條理，使用列點或決策樹。
4. 語氣保持冷靜、客觀的工程師視角。"""


class BrainPipeline:
    def __init__(self, llm: LLMClient, vector_store: VectorStore, graph_store: GraphStore) -> None:
        self.llm = llm
        self.vector_store = vector_store
        self.graph_store = graph_store

    async def _classify_intent(self, text: str) -> str:
        hint = text.lower()
        if any(k in hint for k in ["該不該", "should i", "要不要", "決策"]):
            return "decision_request"
        if any(k in hint for k in ["今天", "最近", "狀態", "心情", "卡住"]):
            return "status_log"
        return "general_reflection"

    async def _extract_entities_relations(self, text: str) -> Tuple[List[Entity], List[Relation]]:
        prompt = f"""
請從下面文字抽取實體與關係，回覆 JSON，不要有多餘文字。

文字：{text}

輸出格式：
{{
  "entities": [{{"name": "...", "type": "Concept|Project|Problem|Metric"}}],
  "relations": [{{"source": "...", "target": "...", "type": "AFFECTS|CAUSES|BLOCKS|RELATED_TO", "evidence": "..."}}]
}}
""".strip()

        try:
            raw = await self.llm.chat(
                "你是資訊抽取器。只能輸出 JSON。",
                prompt,
                temperature=0,
            )
            data = parse_json_block(raw)
            entities = [Entity(**item) for item in data.get("entities", []) if item.get("name")]
            relations = [
                Relation(**item)
                for item in data.get("relations", [])
                if item.get("source") and item.get("target")
            ]
            return entities[:20], relations[:30]
        except Exception:
            return [], []

    def _build_context(self, chunks: List[RetrievedChunk], graph_facts: List[str]) -> str:
        chunk_section = "\n".join(
            [f"- ({c.note_id}) score={c.score:.3f}: {c.text}" for c in chunks]
        ) or "- 無歷史語意片段"
        graph_section = "\n".join([f"- {fact}" for fact in graph_facts]) or "- 無圖譜關聯"
        return f"""[歷史語意片段]
{chunk_section}

[圖譜關聯]
{graph_section}
"""

    def _build_query_prompt(self, question: str, context: str) -> str:
        return f"""
使用下面 context 協助分析，不要直接給單一結論。

問題：{question}

{context}

請輸出 JSON：
{{
  "answer": "...",
  "clarifying_questions": ["...", "...", "..."],
  "contradictions": ["..."]
}}
""".strip()

    def _parse_query_response(
        self,
        raw: str,
        chunks: List[RetrievedChunk],
        graph_facts: List[str],
    ) -> QueryResponse:
        data = parse_json_block(raw)
        answer = data.get("answer") or raw
        clarifying = data.get("clarifying_questions") or []
        contradictions = data.get("contradictions") or []
        used_note_ids = dedupe_preserve_order([c.note_id for c in chunks])

        return QueryResponse(
            answer=answer,
            clarifying_questions=clarifying[:3],
            contradictions=contradictions[:5],
            used_note_ids=used_note_ids,
            graph_facts=graph_facts,
        )

    async def _prepare_query(self, req: QueryRequest) -> Tuple[List[RetrievedChunk], List[str], str]:
        query_embedding = await self.llm.embed(req.question)
        chunks = await self.vector_store.search(req.question, query_embedding, req.top_k)

        keyword = req.question.strip().split()[0] if req.question.strip().split() else req.question[:6]
        graph_facts = await self.graph_store.search_related(keyword=keyword, limit=10)
        context = self._build_context(chunks, graph_facts)
        prompt = self._build_query_prompt(req.question, context)
        return chunks, graph_facts, prompt

    async def ingest(self, req: IngestRequest) -> IngestResponse:
        now = datetime.now(timezone.utc)
        note_id = f"note-{uuid4().hex[:12]}"

        intent = await self._classify_intent(req.text)
        tags = generate_tags(req.text)
        entities, relations = await self._extract_entities_relations(req.text)
        embedding = await self.llm.embed(req.text)

        metadata = {
            "source": req.source,
            "intent": intent,
            "tags": ",".join(tags),
            "timestamp": now.isoformat(),
        }

        await self.vector_store.add_note(note_id, req.text, embedding, metadata)
        await self.graph_store.upsert_note_graph(note_id, req.text, intent, tags, entities, relations, now)

        return IngestResponse(
            note_id=note_id,
            intent=intent,
            tags=tags,
            entity_count=len(entities),
            relation_count=len(relations),
            timestamp=now,
        )

    async def query(self, req: QueryRequest) -> QueryResponse:
        chunks, graph_facts, prompt = await self._prepare_query(req)
        raw = await self.llm.chat(SYSTEM_PROMPT, prompt, temperature=0.2)
        return self._parse_query_response(raw, chunks, graph_facts)

    async def query_stream_events(self, req: QueryRequest) -> AsyncIterator[Dict]:
        chunks, graph_facts, prompt = await self._prepare_query(req)

        raw_parts: List[str] = []

        async for token in self.llm.chat_stream(SYSTEM_PROMPT, prompt, temperature=0.2):
            raw_parts.append(token)
            if token:
                yield {"type": "answer_delta", "delta": token}

        raw = "".join(raw_parts)
        result = self._parse_query_response(raw, chunks, graph_facts)

        if result.answer:
            yield {"type": "answer_replace", "answer": result.answer}

        yield {"type": "done", "result": result.model_dump(mode="json")}
