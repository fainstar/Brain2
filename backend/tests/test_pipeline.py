import pytest

from app.models import IngestRequest, QueryRequest
from app.services.graph_store import InMemoryGraphStore
from app.services.pipeline import BrainPipeline
from app.services.vector_store import InMemoryVectorStore


class FakeLLM:
    async def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        if "資訊抽取器" in system_prompt:
            return """{"entities":[{"name":"API架構","type":"Concept"},{"name":"效能","type":"Metric"}],"relations":[{"source":"API架構","target":"效能","type":"AFFECTS","evidence":"想重構但怕拖垮效能"}]}"""
        return """{"answer":"先定義效能指標再決定是否重構。","clarifying_questions":["目前 p95 latency 是多少？","近期錯誤率變化？","重構範圍是否可分階段？"],"contradictions":["想重構但又擔心效能下滑"]}"""

    async def embed(self, text: str):
        base = float((sum(ord(c) for c in text) % 100) + 1)
        return [base, base / 2, 1.0]

    async def ping(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_ingest_then_query():
    pipeline = BrainPipeline(
        llm=FakeLLM(),
        vector_store=InMemoryVectorStore(),
        graph_store=InMemoryGraphStore(),
    )

    ingest_res = await pipeline.ingest(
        IngestRequest(text="最近覺得 API 架構很怪，想重構但怕拖垮效能", source="manual")
    )
    assert ingest_res.entity_count >= 1
    assert ingest_res.relation_count >= 1

    query_res = await pipeline.query(QueryRequest(question="我該不該現在重構？", top_k=3))
    assert "效能" in query_res.answer or "重構" in query_res.answer
    assert len(query_res.clarifying_questions) == 3
