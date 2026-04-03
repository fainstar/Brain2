from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Entity(BaseModel):
    name: str
    type: str = "Concept"


class Relation(BaseModel):
    source: str
    target: str
    type: str = "RELATED_TO"
    evidence: Optional[str] = None


class IngestRequest(BaseModel):
    text: str = Field(min_length=1)
    source: str = "manual"


class IngestResponse(BaseModel):
    note_id: str
    intent: str
    tags: List[str]
    entity_count: int
    relation_count: int
    timestamp: datetime


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class QueryResponse(BaseModel):
    answer: str
    clarifying_questions: List[str]
    contradictions: List[str]
    used_note_ids: List[str]
    graph_facts: List[str]


class HealthResponse(BaseModel):
    ok: bool
    vector_store: str
    graph_store: str
    llm: str


class MemoryItem(BaseModel):
    note_id: str
    text: str
    metadata: dict


class MemoryListResponse(BaseModel):
    items: List[MemoryItem]


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class ConversationCreateRequest(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    note_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class ConversationRecord(BaseModel):
    id: str
    question: str
    answer: str
    note_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    timestamp: datetime


class ConversationListResponse(BaseModel):
    items: List[ConversationRecord]
