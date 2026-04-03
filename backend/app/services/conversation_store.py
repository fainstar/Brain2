from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4


class ConversationStore:
    def __init__(self, file_path: str) -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")
        self._lock = Lock()

    def _read_all(self) -> List[Dict]:
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _write_all(self, rows: List[Dict]) -> None:
        self.path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    async def add(self, question: str, answer: str, note_id: Optional[str], metadata: Dict) -> Dict:
        with self._lock:
            rows = self._read_all()
            row = {
                "id": f"conv-{uuid4().hex[:12]}",
                "question": question,
                "answer": answer,
                "note_id": note_id,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            rows.append(row)
            self._write_all(rows)
            return row

    async def list(self, limit: int = 100) -> List[Dict]:
        with self._lock:
            rows = self._read_all()
        rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
        return rows[:limit]

    async def delete(self, conversation_id: str) -> bool:
        with self._lock:
            rows = self._read_all()
            next_rows = [row for row in rows if row.get("id") != conversation_id]
            if len(next_rows) == len(rows):
                return False
            self._write_all(next_rows)
            return True

    async def clear(self) -> int:
        with self._lock:
            rows = self._read_all()
            removed = len(rows)
            self._write_all([])
            return removed
