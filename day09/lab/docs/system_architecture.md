# System Architecture — Lab Day 09

**Nhóm:** Nhóm AI20K  
**Ngày:** 14/04/2026  
**Version:** 1.0

---

## 1. Tổng quan kiến trúc

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):**

Day 08 dùng single-agent pipeline (monolith): retrieve → generate trong 1 hàm. Khi pipeline trả lời sai, không rõ lỗi nằm ở retrieval, policy check, hay generation. Supervisor-Worker tách rõ trách nhiệm từng node, cho phép test độc lập từng worker và debug nhanh qua trace.

---

## 2. Sơ đồ Pipeline

```
User Request
     │
     ▼
┌──────────────┐
│  Supervisor  │  ← route_reason, risk_high, needs_tool
└──────┬───────┘
       │
   [route_decision]
       │
  ┌────┴────────────────────┐──────────────┐
  │                         │              │
  ▼                         ▼              ▼
Retrieval Worker     Policy Tool Worker   Human Review
  (evidence)           (policy + MCP)      (HITL)
  │                    │    │              │
  │                    │    ▼              │
  │                    │  MCP Server       │
  │                    │  (4 tools)        │
  └────────┬───────────┘──────────────────-┘
           │
           ▼
    Synthesis Worker
    (LLM + confidence)
           │
           ▼
       Final Answer
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)
- **Chức năng:** Phân tích task bằng keyword matching, quyết định route sang worker phù hợp
- **Input:** `task` (câu hỏi từ user)
- **Output:** `supervisor_route`, `route_reason`, `risk_high`, `needs_tool`
- **Logic:** 3 danh sách keywords (POLICY_KEYWORDS, RETRIEVAL_KEYWORDS, RISK_KEYWORDS)

### Retrieval Worker (`workers/retrieval.py`)
- **Chức năng:** Truy xuất top-k chunks từ ChromaDB (Day 08 collection `rag_lab`)
- **Input:** `task`
- **Output:** `retrieved_chunks` (list), `retrieved_sources` (list)
- **Embedding:** OpenAI `text-embedding-3-small` (dim=1536) để khớp Day 08 index

### Policy Tool Worker (`workers/policy_tool.py`)
- **Chức năng:** Kiểm tra ngoại lệ policy (Flash Sale, digital product) + gọi MCP tools
- **Input:** `task`, `retrieved_chunks`, `needs_tool`
- **Output:** `policy_result`, `mcp_tools_used`
- **MCP tools:** `search_kb`, `get_ticket_info`, `check_access_permission`, `create_ticket`

### Synthesis Worker (`workers/synthesis.py`)
- **Chức năng:** Tổng hợp câu trả lời từ chunks + policy_result qua LLM (GPT-4o-mini)
- **Input:** `task`, `retrieved_chunks`, `policy_result`
- **Output:** `final_answer`, `sources`, `confidence`
- **Confidence:** Weighted average chunk scores + multi-source bonus + LLM reasoning boost

### Human Review Node (`graph.py`)
- **Chức năng:** HITL placeholder — auto-approve trong lab, ghi log `hitl_triggered=True`
- **Trigger:** Khi task chứa unknown error code (`ERR-xxx`) không match keyword nào

### MCP Server (`mcp_server.py`)
- **Chức năng:** Mock MCP server cung cấp 4 tools qua `dispatch_tool()` interface
- **Tools:** `search_kb`, `get_ticket_info`, `check_access_permission`, `create_ticket`

---

## 4. Data Flow

```
AgentState (TypedDict) — shared state xuyên suốt pipeline:

task ──→ supervisor_node() ──→ route_decision()
                                     │
                            ┌────────┴────────┐
                            ▼                 ▼
                    retrieval_run()    policy_tool_run()
                            │                 │
                            └────────┬────────┘
                                     ▼
                            synthesis_run()
                                     │
                                     ▼
                            final_answer + confidence
```

Mỗi worker đọc/ghi đúng field của mình theo `contracts/worker_contracts.yaml`.

---

## 5. Ranh giới Supervisor vs Workers

| Trách nhiệm | Supervisor | Workers |
|---|---|---|
| Quyết định route | ✓ | ✗ |
| Truy xuất dữ liệu | ✗ | ✓ (retrieval) |
| Kiểm tra policy | ✗ | ✓ (policy_tool) |
| Gọi LLM | ✗ | ✓ (synthesis) |
| Gọi MCP tools | ✗ | ✓ (policy_tool) |
| Ghi trace | ✓ (route_reason) | ✓ (worker_io_logs) |
