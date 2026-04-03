from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Protocol

from neo4j import GraphDatabase

from app.config import settings
from app.models import Entity, Relation
from app.utils import normalize_relation_type


class GraphStore(Protocol):
    async def upsert_note_graph(
        self,
        note_id: str,
        text: str,
        intent: str,
        tags: List[str],
        entities: List[Entity],
        relations: List[Relation],
        timestamp: datetime,
    ) -> None: ...
    async def search_related(self, keyword: str, limit: int = 10) -> List[str]: ...
    async def graph_snapshot(self, limit: int = 200) -> Dict[str, List[Dict[str, str]]]: ...
    async def delete_note(self, note_id: str) -> bool: ...
    async def ping(self) -> bool: ...


class Neo4jGraphStore:
    def __init__(self) -> None:
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        self.database = settings.neo4j_database

    async def upsert_note_graph(
        self,
        note_id: str,
        text: str,
        intent: str,
        tags: List[str],
        entities: List[Entity],
        relations: List[Relation],
        timestamp: datetime,
    ) -> None:
        with self.driver.session(database=self.database) as session:
            session.run(
                """
                MERGE (n:Note {id: $note_id})
                SET n.text = $text, n.intent = $intent, n.tags = $tags, n.created_at = $created_at
                """,
                note_id=note_id,
                text=text,
                intent=intent,
                tags=tags,
                created_at=timestamp.isoformat(),
            )

            for ent in entities:
                session.run(
                    """
                    MERGE (e:Entity {name: $name})
                    SET e.type = $type
                    WITH e
                    MATCH (n:Note {id: $note_id})
                    MERGE (n)-[:MENTIONS]->(e)
                    """,
                    name=ent.name,
                    type=ent.type,
                    note_id=note_id,
                )

            for rel in relations:
                rel_type = normalize_relation_type(rel.type)
                session.run(
                    f"""
                    MERGE (a:Entity {{name: $source}})
                    MERGE (b:Entity {{name: $target}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r.evidence = $evidence
                    SET r.note_ids = CASE
                        WHEN r.note_ids IS NULL THEN [$note_id]
                        WHEN NOT $note_id IN r.note_ids THEN r.note_ids + $note_id
                        ELSE r.note_ids
                    END
                    """,
                    source=rel.source,
                    target=rel.target,
                    evidence=rel.evidence or "",
                    note_id=note_id,
                )

    async def search_related(self, keyword: str, limit: int = 10) -> List[str]:
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($keyword)
                OPTIONAL MATCH (e)-[r]-(other:Entity)
                RETURN e.name AS source, type(r) AS rel, other.name AS target
                LIMIT $limit
                """,
                keyword=keyword,
                limit=limit,
            )
            facts = []
            for rec in result:
                source = rec.get("source") or ""
                rel = rec.get("rel") or "RELATED_TO"
                target = rec.get("target") or ""
                if target:
                    facts.append(f"{source} -[{rel}]- {target}")
                else:
                    facts.append(source)
            return facts

    async def graph_snapshot(self, limit: int = 200) -> Dict[str, List[Dict[str, str]]]:
        with self.driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (a)-[r]->(b)
                RETURN
                  coalesce(a.id, a.name) AS source_id,
                  coalesce(a.name, a.id) AS source_label,
                  labels(a)[0] AS source_kind,
                  coalesce(b.id, b.name) AS target_id,
                  coalesce(b.name, b.id) AS target_label,
                  labels(b)[0] AS target_kind,
                  type(r) AS rel
                LIMIT $limit
                """,
                limit=limit,
            )

            nodes: Dict[str, Dict[str, str]] = {}
            edges: List[Dict[str, str]] = []

            for rec in result:
                source_id = rec["source_id"]
                source_label = rec["source_label"]
                source_kind = rec["source_kind"] or "Node"
                target_id = rec["target_id"]
                target_label = rec["target_label"]
                target_kind = rec["target_kind"] or "Node"
                rel = rec["rel"] or "RELATED_TO"

                nodes[source_id] = {"id": source_id, "label": source_label, "kind": source_kind}
                nodes[target_id] = {"id": target_id, "label": target_label, "kind": target_kind}
                edges.append({"source": source_id, "target": target_id, "label": rel})

            return {"nodes": list(nodes.values()), "edges": edges}

    async def delete_note(self, note_id: str) -> bool:
        with self.driver.session(database=self.database) as session:
            exists = session.run("MATCH (n:Note {id: $note_id}) RETURN n LIMIT 1", note_id=note_id).single()
            if not exists:
                return False

            session.run(
                """
                MATCH (n:Note {id: $note_id})-[m:MENTIONS]->(e)
                DELETE m
                WITH n
                DELETE n
                """,
                note_id=note_id,
            )

            session.run(
                """
                MATCH ()-[r]->()
                WHERE r.note_ids IS NOT NULL AND $note_id IN r.note_ids
                SET r.note_ids = [x IN r.note_ids WHERE x <> $note_id]
                """,
                note_id=note_id,
            )

            session.run(
                """
                MATCH ()-[r]->()
                WHERE r.note_ids IS NOT NULL AND size(r.note_ids) = 0
                DELETE r
                """
            )

            session.run(
                """
                MATCH (e:Entity)
                WHERE NOT EXISTS { MATCH (:Note)-[:MENTIONS]->(e) }
                DETACH DELETE e
                """
            )

            return True

    async def ping(self) -> bool:
        try:
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False


class InMemoryGraphStore:
    def __init__(self) -> None:
        self.notes: Dict[str, Dict] = {}
        self.facts: List[str] = []
        self.nodes: Dict[str, Dict[str, str]] = {}
        self.edges: List[Dict[str, str]] = []

    async def upsert_note_graph(
        self,
        note_id: str,
        text: str,
        intent: str,
        tags: List[str],
        entities: List[Entity],
        relations: List[Relation],
        timestamp: datetime,
    ) -> None:
        self.notes[note_id] = {
            "text": text,
            "intent": intent,
            "tags": tags,
            "timestamp": timestamp.isoformat(),
        }

        self.nodes[note_id] = {"id": note_id, "label": note_id, "kind": "Note"}

        for ent in entities:
            self.nodes[ent.name] = {"id": ent.name, "label": ent.name, "kind": ent.type}
            self.edges.append({"source": note_id, "target": ent.name, "label": "MENTIONS"})

        for relation in relations:
            self.facts.append(f"{relation.source} -[{relation.type}]- {relation.target}")
            self.edges.append({"source": relation.source, "target": relation.target, "label": relation.type})

    async def search_related(self, keyword: str, limit: int = 10) -> List[str]:
        keyword = keyword.lower().strip()
        return [fact for fact in self.facts if keyword in fact.lower()][:limit]

    async def graph_snapshot(self, limit: int = 200) -> Dict[str, List[Dict[str, str]]]:
        return {
            "nodes": list(self.nodes.values())[:limit],
            "edges": self.edges[:limit],
        }

    async def delete_note(self, note_id: str) -> bool:
        existed = note_id in self.notes
        self.notes.pop(note_id, None)
        self.nodes.pop(note_id, None)
        self.edges = [
            e for e in self.edges if e.get("source") != note_id and e.get("target") != note_id
        ]
        return existed

    async def ping(self) -> bool:
        return True
