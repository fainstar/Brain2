# Second Brain System Spec v1.01 — Local MVP

這是一個完全本地運行的 Second Brain MVP，重點是資料不離開本機、可追溯記憶、可視化關聯圖譜。

- **LLM**: LM Studio（OpenAI 相容 API）
- **Backend**: Python + FastAPI
- **Vector DB**: ChromaDB
- **Graph DB**: Neo4j
- **UI**: Streamlit Dashboard（主要操作）+ Open WebUI（可選）

## 專案結構

- `docker-compose.yml`: 本地微服務啟動配置
- `.env.example`: 環境變數範本
- `.env`: 本地佔位配置（請修改密碼）
- `backend/`: 核心 ingestion/query API 與 GraphRAG pipeline
- `frontend/`: Streamlit Dashboard（聊天 / 記憶 / 思維圖）

## 服務與連線埠

- `backend`（FastAPI）: `http://localhost:8000`
- `dashboard`（Streamlit）: `http://localhost:8501`
- `open-webui`（可選）: `http://localhost:3000`
- `chromadb`（host 映射）: `http://localhost:8001`
- `neo4j` Browser: `http://localhost:7474`（Bolt `7687`）

## 核心流程

### Workflow 1 — Ingestion Pipeline

`POST /ingest`

1. Intent Classification（規則 + LLM 抽取）
2. Entity & Relation Extraction（JSON）
3. Graph Update（Neo4j）
4. Vectorization（LM Studio embeddings）+ Chroma 入庫

### Workflow 2 — Retrieval & Generation Pipeline

`POST /query`

1. Hybrid Retrieval（Chroma + Neo4j）
2. Context Construction（語意片段 + 圖譜關聯）
3. Socratic Prompting（輸出反問與矛盾點）

## 快速開始

1. 先確認 LM Studio 已啟動且 OpenAI API 可用（例：`http://localhost:1234/v1`）。
2. 複製並調整環境變數（尤其 Neo4j 密碼、LM Studio URL、模型名稱）。
3. 啟動服務。

```bash
cd /root/Brain
docker compose up -d --build
```

啟動後可用以下方式快速確認：

```bash
docker compose ps
curl -s http://localhost:8000/health
```

## API 範例

### Health

```bash
curl -s http://localhost:8000/health
```

### Ingest

```bash
curl -s -X POST http://localhost:8000/ingest \
  -H 'Content-Type: application/json' \
  -d '{"text":"最近覺得 API 架構很怪，想重構但怕拖垮效能","source":"manual"}'
```

### Query

```bash
curl -s -X POST http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"我該不該現在重構？","top_k":5}'
```

### Conversations（對話歷史）

```bash
# 取得最近 20 筆
curl -s 'http://localhost:8000/conversations?limit=20'

# 清空全部對話
curl -s -X DELETE http://localhost:8000/conversations
```

### Memory（記憶）

```bash
# 列出記憶
curl -s 'http://localhost:8000/memory?limit=20'

# 刪除指定記憶
curl -s -X DELETE http://localhost:8000/memory/<note_id>
```

## 本地測試（不依賴外部服務）

`backend` 內建 in-memory 測試替身：

```bash
cd /root/Brain/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -q
PYTHONPATH=. python scripts/demo_runner.py
```

## Open WebUI 使用建議

Open WebUI 容器啟動後，瀏覽 `http://localhost:3000`：

- 聊天模型指向 LM Studio。
- 若需要「第二大腦 API 工作流」，可將 `backend:8000` 設為工具端點（或後續加 MCP/Tool server）。

## Streamlit Dashboard（聊天 / 記憶 / 思維圖）

本專案另提供 Dashboard：`http://localhost:8501`

- **聊天決策頁**：對話式介面（chat style），送出問題時會「自動 ingest」你的輸入，確保記憶庫與思維圖同步更新。
  - 對話歷史會儲存在 backend（`data/backend/conversations.json`），重整頁面仍可看到。
  - 每則對話會顯示時間（由後端 `timestamp` 轉為可讀格式）。
  - 支援「🔁 重試這題」：以同一問題重新查詢，並建立新對話記錄。
  - 每則對話可直接按「刪除這則對話」。
  - 可一鍵「清除聊天紀錄」（需勾選確認）。
- **記憶查看頁**：可瀏覽/搜尋記憶，並可直接按鈕刪除（不用輸入 note_id）。
- **思維圖頁**：即時顯示 Neo4j 節點與關係邊。

刪除行為：

1. 對話刪除：直接刪除對話歷史記錄（不影響原始記憶）
2. 記憶刪除：直接刪除向量記憶，並同步清理圖譜關聯

## 注意事項

- Linux 下容器要訪問宿主機 LM Studio，使用 `host.docker.internal:host-gateway`（compose 已設定）。
- 若 LM Studio 的 embedding 模型名稱不同，請更新 `.env` 的 `LLM_EMBED_MODEL`。
- `CHROMA_PORT` 在 backend 容器內應設定為 `8000`（service 內網埠）；`8001` 是宿主機對外映射埠。
- 若你在 Neo4j 已初始化後才修改 `.env` 的 `NEO4J_PASSWORD`，需同步變更資料庫使用者密碼（或清除 `data/neo4j` volume 後重建）。
- 生產環境請改用強密碼並加上反向代理與憑證。

## 已知測試/執行備註

- 本機直接跑 `pytest` 可能因環境而找不到 `app` package；可在 `backend` 目錄加上 `PYTHONPATH=.`。
- 若你在容器內執行測試，請先確認 `tests/` 有被掛載或包含在映像中。
