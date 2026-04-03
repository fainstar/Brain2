# Frontend Notes

本專案首版採用 `Open WebUI` 容器（見根目錄 `docker-compose.yml`）。

建議在 Open WebUI 內新增兩個模型入口：

1. **LM Studio（聊天）**
   - Base URL: `http://host.docker.internal:1234/v1`
   - 用於一般對話與模型測試。

2. **Second Brain Backend（流程代理）**
   - 透過 Open WebUI 的工具/外掛機制，呼叫：
     - `POST http://backend:8000/ingest`
     - `POST http://backend:8000/query`

若你想做極簡客製前端，可再加一個 Streamlit app，專門提供「輸入碎碎念」按鈕。
