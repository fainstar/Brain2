import html
import json
import os
from datetime import datetime

import requests
import streamlit as st
import streamlit.components.v1 as components


BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")


def call_api(method: str, path: str, **kwargs):
    url = f"{BACKEND_URL}{path}"
    resp = requests.request(method, url, timeout=60, **kwargs)
    resp.raise_for_status()
    return resp.json()


def format_timestamp(value: str | None) -> str:
    if not value:
        return "未知時間"

    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return value


def render_graph(
        nodes,
        edges,
        node_font_size: int,
        edge_font_size: int,
        node_spacing: int,
        spring_length: int,
        show_edge_labels: bool,
        use_hierarchical: bool,
):
        safe_nodes = json.dumps(nodes, ensure_ascii=False)
        safe_edges = json.dumps(edges, ensure_ascii=False)
        safe_show_edge_labels = "true" if show_edge_labels else "false"
        safe_use_hierarchical = "true" if use_hierarchical else "false"

        html_payload = f"""
        <div id="mynetwork" style="height: 700px; border: 1px solid #ddd; border-radius: 10px;"></div>
        <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
        <script>
            const colorByKind = {{
                Note: '#0ea5e9',
                Entity: '#8b5cf6',
                Concept: '#6366f1',
                Metric: '#f59e0b',
                Project: '#10b981',
                Problem: '#ef4444',
                Node: '#64748b'
            }};

            const nodes = new vis.DataSet({safe_nodes}.map(n => ({{
                id: n.id,
                label: n.label,
                group: n.kind || 'Node',
                title: `${{n.kind || 'Node'}}: ${{n.label}}`,
                font: {{
                    size: {node_font_size},
                    color: '#111827',
                    strokeWidth: 4,
                    strokeColor: '#ffffff'
                }},
                color: {{
                    background: colorByKind[n.kind] || '#64748b',
                    border: '#1f2937'
                }},
                shape: 'dot',
                size: 18,
                margin: 12
            }})));

            const edges = new vis.DataSet({safe_edges}.map(e => ({{
                from: e.source,
                to: e.target,
                label: {safe_show_edge_labels} ? e.label : '',
                title: e.label,
                arrows: 'to',
                font: {{
                    size: {edge_font_size},
                    strokeWidth: 4,
                    strokeColor: '#ffffff',
                    align: 'horizontal'
                }}
            }})));

            const container = document.getElementById('mynetwork');
            const data = {{ nodes, edges }};
            const options = {{
                autoResize: true,
                layout: {safe_use_hierarchical}
                    ? {{ hierarchical: {{ enabled: true, direction: 'UD', levelSeparation: 220, nodeSpacing: {node_spacing} }} }}
                    : {{ improvedLayout: true }},
                physics: {safe_use_hierarchical}
                    ? false
                    : {{
                            enabled: true,
                            stabilization: {{ enabled: true, iterations: 1000 }},
                            barnesHut: {{
                                gravitationalConstant: -5000,
                                centralGravity: 0.25,
                                springLength: {spring_length},
                                springConstant: 0.03,
                                damping: 0.3,
                                avoidOverlap: 1
                            }}
                        }},
                interaction: {{
                    hover: true,
                    tooltipDelay: 100,
                    hideEdgesOnDrag: true,
                    hideEdgesOnZoom: true,
                    multiselect: true
                }},
                edges: {{
                    smooth: {{ type: 'dynamic', roundness: 0.35 }},
                    color: {{ color: '#9ca3af', highlight: '#374151' }},
                    width: 1.5,
                    selectionWidth: 2.5
                }}
            }};
            new vis.Network(container, data, options);
        </script>
        """
        components.html(html_payload, height=730)


st.set_page_config(page_title="Second Brain Dashboard", layout="wide")
st.title("🧠 Second Brain Dashboard")

with st.sidebar:
    st.caption("Backend")
    st.code(BACKEND_URL)
    if st.button("檢查健康狀態"):
        try:
            health = call_api("GET", "/health")
            st.success(f"狀態: {health}")
        except Exception as exc:
            st.error(f"健康檢查失敗: {exc}")

tab_chat, tab_memory, tab_graph = st.tabs(["💬 聊天決策", "🗂️ 記憶查看", "🕸️ 思維圖"])


with tab_chat:
    st.subheader("聊天決策輔助")
    try:
        conv_data = call_api("GET", "/conversations", params={"limit": 100})
        conversations = list(reversed(conv_data.get("items", [])))
    except Exception as exc:
        st.error(f"讀取對話歷史失敗: {exc}")
        conversations = []

    retry_target = None

    control_left, control_right = st.columns([3, 2])
    with control_left:
        top_k = st.slider("檢索記憶數量 top_k", min_value=1, max_value=20, value=5)
        if conversations:
            last_question = conversations[-1].get("question", "")
            if st.button("🔁 人工重試上一題", type="primary"):
                retry_target = conversations[-1]
                st.info(f"正在人工重試：{last_question[:60]}{'...' if len(last_question) > 60 else ''}")
    with control_right:
        confirm_clear_chat = st.checkbox("我確定要清除全部聊天紀錄", value=False)
        if st.button("🧹 清除聊天紀錄", type="secondary"):
            if not confirm_clear_chat:
                st.warning("請先勾選確認，再清除聊天紀錄。")
            else:
                try:
                    result = call_api("DELETE", "/conversations")
                    st.success(f"已清除聊天紀錄，共移除 {result.get('removed', 0)} 筆。")
                    st.rerun()
                except Exception as exc:
                    st.error(f"清除失敗: {exc}")

    if not conversations:
        st.info("目前尚無對話歷史，輸入第一個問題開始。")

    for conv in conversations:
        conv_id = conv.get("id", "")
        question = conv.get("question", "")
        answer = conv.get("answer", "")
        timestamp = conv.get("timestamp")
        display_time = format_timestamp(timestamp)
        metadata = conv.get("metadata", {}) or {}

        with st.chat_message("user"):
            st.write(question)
            st.caption(f"🕒 {display_time}")

        with st.chat_message("assistant"):
            st.write(answer)
            st.caption(f"🕒 {display_time}")
            clarifying = metadata.get("clarifying_questions", [])
            contradictions = metadata.get("contradictions", [])

            if clarifying:
                st.markdown("**釐清問題**")
                for item in clarifying:
                    st.markdown(f"- {item}")
            if contradictions:
                st.markdown("**矛盾點**")
                for item in contradictions:
                    st.markdown(f"- {item}")

            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if st.button("🔁 人工重試", key=f"retry_conv_{conv_id}"):
                    retry_target = conv
            with action_col2:
                if st.button("刪除這則對話", key=f"del_conv_{conv_id}"):
                    try:
                        call_api("DELETE", f"/conversations/{conv_id}")
                        st.success("已刪除對話紀錄")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"刪除失敗: {exc}")

            with st.expander("細節"):
                st.json(
                    {
                        "conversation_id": conv_id,
                        "note_id": conv.get("note_id"),
                        "used_note_ids": metadata.get("used_note_ids", []),
                        "graph_facts": metadata.get("graph_facts", []),
                        "timestamp": conv.get("timestamp"),
                    }
                )

    if retry_target:
        try:
            retry_question = (retry_target.get("question") or "").strip()
            if not retry_question:
                st.warning("找不到可重試的問題內容。")
            else:
                query_payload = {"question": retry_question, "top_k": top_k}
                query_result = call_api("POST", "/query", json=query_payload)

                call_api(
                    "POST",
                    "/conversations",
                    json={
                        "question": retry_question,
                        "answer": query_result.get("answer", ""),
                        "note_id": retry_target.get("note_id"),
                        "metadata": {
                            "manual_retry": True,
                            "retry_of": retry_target.get("id"),
                            "clarifying_questions": query_result.get("clarifying_questions", []),
                            "contradictions": query_result.get("contradictions", []),
                            "used_note_ids": query_result.get("used_note_ids", []),
                            "graph_facts": query_result.get("graph_facts", []),
                        },
                    },
                )

                st.success("人工重試完成，已新增一筆新回覆。")
                st.rerun()
        except Exception as exc:
            st.error(f"人工重試失敗: {exc}")

    user_prompt = st.chat_input("輸入你的問題（會自動更新記憶與思維圖）")
    if user_prompt and user_prompt.strip():
        try:
            prompt = user_prompt.strip()
            ingest_payload = {"text": prompt, "source": "streamlit-chat"}
            ingest_result = call_api("POST", "/ingest", json=ingest_payload)

            query_payload = {"question": prompt, "top_k": top_k}
            query_result = call_api("POST", "/query", json=query_payload)

            call_api(
                "POST",
                "/conversations",
                json={
                    "question": prompt,
                    "answer": query_result.get("answer", ""),
                    "note_id": ingest_result.get("note_id"),
                    "metadata": {
                        "clarifying_questions": query_result.get("clarifying_questions", []),
                        "contradictions": query_result.get("contradictions", []),
                        "used_note_ids": query_result.get("used_note_ids", []),
                        "graph_facts": query_result.get("graph_facts", []),
                    },
                },
            )

            st.rerun()
        except Exception as exc:
            st.error(f"查詢失敗: {exc}")


with tab_memory:
    st.subheader("記憶查看")
    col1, col2 = st.columns([2, 1])
    with col1:
        keyword = st.text_input("搜尋關鍵字（語意）", value="")
    with col2:
        limit = st.number_input("顯示筆數", min_value=1, max_value=200, value=50)

    try:
        if keyword.strip():
            data = call_api("GET", "/memory/search", params={"q": keyword.strip(), "top_k": limit})
        else:
            data = call_api("GET", "/memory", params={"limit": limit})
        items = data.get("items", [])
        st.caption(f"共 {len(items)} 筆")

        if not items:
            st.info("目前沒有記憶資料。")

        for item in items:
            note_id = item.get("note_id", "")
            timestamp = item.get("metadata", {}).get("timestamp", "")
            text = item.get("text", "")

            with st.container(border=True):
                info_col, action_col = st.columns([5, 1])

                with info_col:
                    st.markdown(f"**{note_id}**")
                    if timestamp:
                        st.caption(timestamp)
                    st.write(text[:180] + ("..." if len(text) > 180 else ""))
                    with st.expander("查看完整內容與 metadata"):
                        st.write(text)
                        st.json(item.get("metadata", {}))

                with action_col:
                    if note_id and st.button("🗑️ 刪除", key=f"del_mem_{note_id}"):
                        try:
                            result = call_api("DELETE", f"/memory/{note_id}")
                            st.success(f"已刪除：{result.get('note_id')}")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"刪除失敗: {exc}")

        st.markdown("---")
        st.caption("在記憶卡片上按「🗑️ 刪除」即可直接刪除，會同步影響思維圖。")
    except Exception as exc:
        st.error(f"無法讀取記憶: {exc}")


with tab_graph:
    st.subheader("思維圖（Neo4j）")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        graph_limit = st.slider("圖譜邊數上限", min_value=20, max_value=500, value=200, step=10)
        show_edge_labels = st.toggle("顯示關係文字", value=False)
    with col_b:
        node_font_size = st.slider("節點字體", min_value=12, max_value=28, value=16)
        edge_font_size = st.slider("關係字體", min_value=10, max_value=22, value=12)
    with col_c:
        node_spacing = st.slider("節點間距", min_value=80, max_value=420, value=220, step=20)
        spring_length = st.slider("連線長度", min_value=80, max_value=420, value=220, step=20)
        use_hierarchical = st.toggle("階層式布局", value=False)

    try:
        data = call_api("GET", "/graph", params={"limit": graph_limit})
        nodes = data.get("nodes", [])
        edges = data.get("edges", [])
        st.caption(f"Nodes: {len(nodes)} | Edges: {len(edges)}")
        if not nodes:
            st.info("目前尚無圖譜資料，先到「聊天決策」頁送出一個問題。")
        else:
            render_graph(
                nodes,
                edges,
                node_font_size=node_font_size,
                edge_font_size=edge_font_size,
                node_spacing=node_spacing,
                spring_length=spring_length,
                show_edge_labels=show_edge_labels,
                use_hierarchical=use_hierarchical,
            )
            with st.expander("原始資料 JSON"):
                st.json(data)
    except Exception as exc:
        st.error(f"無法讀取思維圖: {exc}")
