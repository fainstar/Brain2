import asyncio

from app.models import IngestRequest, QueryRequest
from app.services.graph_store import InMemoryGraphStore
from app.services.pipeline import BrainPipeline
from app.services.vector_store import InMemoryVectorStore


class DemoLLM:
    async def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        if "資訊抽取器" in system_prompt:
            return """{"entities":[{"name":"API架構","type":"Concept"},{"name":"效能","type":"Metric"}],"relations":[{"source":"API架構","target":"效能","type":"AFFECTS"}]}"""
        return """{"answer":"建議先量測瓶頸後再分階段重構。","clarifying_questions":["目前瓶頸在哪一層？","有沒有壓測基準？","是否可先重構讀取路徑？"],"contradictions":["擔心效能但尚未定義指標"]}"""

    async def embed(self, text: str):
        seed = float((sum(ord(c) for c in text) % 50) + 1)
        return [seed, seed / 3, 0.5]

    async def ping(self) -> bool:
        return True


async def main() -> None:
    pipeline = BrainPipeline(DemoLLM(), InMemoryVectorStore(), InMemoryGraphStore())
    ingest_res = await pipeline.ingest(
        IngestRequest(text="最近覺得 API 架構很怪，想重構但怕拖垮效能", source="demo")
    )
    print("INGEST:", ingest_res.model_dump())

    query_res = await pipeline.query(QueryRequest(question="我該不該現在重構？"))
    print("QUERY:", query_res.model_dump())


if __name__ == "__main__":
    asyncio.run(main())
