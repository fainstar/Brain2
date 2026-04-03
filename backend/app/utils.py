import json
import re
from collections import Counter
from typing import Iterable, List


STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "is",
    "are",
    "of",
    "in",
    "on",
    "for",
    "with",
    "我",
    "你",
    "他",
    "她",
    "它",
    "最近",
    "覺得",
    "這個",
    "那個",
    "很",
    "有",
    "是",
    "要",
    "想",
}


def parse_json_block(text: str) -> dict:
    text = text.strip()
    if not text:
        return {}

    fenced = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    candidates = fenced + re.findall(r"(\{[\s\S]*\})", text)

    for block in candidates:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue
    return {}


def generate_tags(text: str, top_n: int = 5) -> List[str]:
    tokens = re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,}", text.lower())
    filtered = [t for t in tokens if t not in STOPWORDS]
    if not filtered:
        return ["general"]
    counts = Counter(filtered)
    return [token for token, _ in counts.most_common(top_n)]


def normalize_relation_type(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip().upper())
    return token or "RELATED_TO"


def dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
