from app.config import settings
from app.services.graph_store import InMemoryGraphStore, Neo4jGraphStore
from app.services.llm_client import LLMClient
from app.services.pipeline import BrainPipeline
from app.services.vector_store import ChromaVectorStore, InMemoryVectorStore


def build_pipeline() -> BrainPipeline:
    llm = LLMClient()

    if settings.use_in_memory:
        vector_store = InMemoryVectorStore()
        graph_store = InMemoryGraphStore()
    else:
        vector_store = ChromaVectorStore()
        graph_store = Neo4jGraphStore()

    return BrainPipeline(llm=llm, vector_store=vector_store, graph_store=graph_store)
