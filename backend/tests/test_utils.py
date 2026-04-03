from app.utils import generate_tags, parse_json_block


def test_parse_json_block_from_fenced_text():
    raw = """
這是前言
```json
{"a": 1, "b": ["x"]}
```
結尾
"""
    assert parse_json_block(raw) == {"a": 1, "b": ["x"]}


def test_generate_tags_basic():
    text = "最近 API 架構 怪怪的 效能 有瓶頸 想重構 API"
    tags = generate_tags(text, top_n=3)
    assert "api" in tags
    assert len(tags) == 3
