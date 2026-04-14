# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Trần Văn Tuấn  
**Vai trò trong nhóm:** Supervisor Owner + MCP Owner + Worker (policy_tool)  
**Ngày nộp:** 14/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào?

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py` (Supervisor orchestrator), `mcp_server.py` (MCP tool server), `workers/policy_tool.py` (policy worker)
- Functions tôi implement:
  - `supervisor_node()` — phân luồng câu hỏi dựa trên keyword matching
  - `route_decision()` — trả về route cho graph
  - `human_review_node()` — HITL placeholder với auto-approve
  - `build_graph()` — xây dựng pipeline chạy supervisor → worker → synthesis
  - `dispatch_tool()`, `list_tools()` — MCP dispatch layer
  - `tool_search_kb()`, `tool_get_ticket_info()`, `tool_check_access_permission()`, `tool_create_ticket()` — 4 MCP tools

**Cách công việc của tôi kết nối với phần của thành viên khác:**

Supervisor (`graph.py`) là bộ não điều phối toàn bộ pipeline. Tôi định nghĩa schema `AgentState` (TypedDict) làm xương sống dữ liệu — Việt dùng schema này để đọc `task` và ghi `retrieved_chunks` (retrieval) cùng `final_answer` (synthesis). Thư dùng output từ `save_trace()` để phân tích tại `eval_trace.py`. MCP server của tôi cung cấp 4 tools mà `policy_tool_worker` tự gọi qua `dispatch_tool()` khi Supervisor đặt flag `needs_tool=True`.

**Bằng chứng:** File `graph.py` dòng 114-170 (supervisor_node), `mcp_server.py` dòng 282-327 (dispatch layer), `workers/policy_tool.py` (toàn bộ).

---

## 2. Tôi đã ra một quyết định kỹ thuật gì?

**Quyết định:** Sử dụng keyword-based routing trong `supervisor_node` thay vì gọi LLM để classify route.

**Lý do:**

Tôi cân nhắc 2 phương án: (1) Gọi GPT-4o-mini để phân loại câu hỏi thuộc nhóm nào (retrieval/policy/HITL), hoặc (2) dùng 3 danh sách keywords cứng (`POLICY_KEYWORDS`, `RETRIEVAL_KEYWORDS`, `RISK_KEYWORDS`) để match trực tiếp.

Tôi chọn keyword-based vì: tốc độ routing gần như tức thì (~1ms so với ~800ms nếu gọi LLM), tiết kiệm API calls (15 câu × 1 LLM call = 15 calls bớt đi), và trong phạm vi lab 5 categories (SLA, refund, access, helpdesk, multi-hop) — keyword matching đạt accuracy đủ cao mà không cần LLM.

**Trade-off đã chấp nhận:**

Keyword matching không linh hoạt bằng LLM classifier. Ví dụ: câu q09 "ERR-403-AUTH là lỗi gì?" — không match được keyword nào trong `RETRIEVAL_KEYWORDS` hay `POLICY_KEYWORDS`, bị rơi vào `human_review`. Nếu dùng LLM classifier, nó sẽ hiểu đây là câu hỏi IT helpdesk và route thẳng sang retrieval.

**Bằng chứng từ trace/code:**

```python
# graph.py — supervisor_node routing logic
POLICY_KEYWORDS = [
    "hoàn tiền", "refund", "flash sale", "license", "cấp quyền",
    "access", "level 2", "level 3", "admin access", "phê duyệt"
]

# Trace q13 — route_reason ghi rõ matched keywords
"route_reason": "multi-hop: policy + retrieval keywords → policy_tool_worker 
                 (will also call retrieval)"
"latency_ms": 7576  # Nhanh hơn nhiều so với LLM-based routing
```

```json
// Trace q07 — chính xác route sang policy_tool_worker
"route_reason": "task contains policy/access keyword: ['hoàn tiền', 'license', 'license key']"
"needs_tool": true
"confidence": 0.86
```

---

## 3. Tôi đã sửa một lỗi gì?

**Lỗi:** `ChromaDB query failed: Collection expecting embedding with dimension of 1536, got 384`

**Symptom (pipeline làm gì sai?):**

Khi chạy `python eval_trace.py`, retrieval_worker trả về 0 chunks cho mọi câu hỏi. Log hiện cảnh báo: `ChromaDB query failed: Collection expecting embedding with dimension of 1536, got 384`. Confidence bị kéo xuống 0.10-0.15 vì synthesis không có context.

**Root cause (lỗi nằm ở đâu?):**

Lỗi nằm ở thứ tự ưu tiên trong `_get_embedding_fn()` của `workers/retrieval.py`. Code mặc định ưu tiên SentenceTransformer (tạo vector 384 chiều), nhưng collection `rag_lab` từ Day 08 được index bằng OpenAI `text-embedding-3-small` (1536 chiều). Hai embedding dimensions không khớp nhau → ChromaDB từ chối query.

**Cách sửa:**

Tôi đảo thứ tự ưu tiên trong `_get_embedding_fn()`: OpenAI embeddings (Option A, 1536 dim) được gọi trước, SentenceTransformer (Option B, 384 dim) chỉ làm fallback. Đồng thời cập nhật `_get_collection()` để trỏ path sang `day08/lab/chroma_db` thay vì `./chroma_db`.

**Bằng chứng trước/sau:**

Trước sửa:
```
⚠️ ChromaDB query failed: Collection expecting embedding with dimension of 1536, got 384
Retrieved: 0 chunks
Sources: []
```

Sau sửa:
```
> Query: SLA ticket P1 là bao lâu?
  Retrieved: 3 chunks
    [0.589] support/sla-p1-2026.pdf: Ticket P1: Phản hồi ban đầu 15 phút...
  Sources: ['support/sla-p1-2026.pdf']
```

---

## 4. Tôi tự đánh giá đóng góp của mình

**Tôi làm tốt nhất ở điểm nào?**

Thiết kế routing logic rõ ràng, dễ debug. Mỗi trace đều ghi lại `route_reason` giải thích tại sao câu hỏi đi vào worker nào — giúp cả nhóm nhanh chóng phát hiện routing sai. MCP server triển khai đủ 4 tools với dispatch layer chuẩn protocol, cho phép policy_tool_worker gọi tool linh hoạt mà không hard-code.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Quản lý Git chưa tốt. Khi git pull upstream, toàn bộ code tùy chỉnh (encoding utf-8, boost confidence, đường dẫn ChromaDB Day 08) bị overwrite vì tôi làm trực tiếp trên branch `main` mà không tạo branch riêng. Phải dùng `git stash` để khôi phục — mất thời gian và gây hoang mang cho cả nhóm.

**Nhóm phụ thuộc vào tôi ở đâu?**

Supervisor là entry point duy nhất của pipeline. Nếu `graph.py` hoặc `AgentState` schema bị lỗi, toàn bộ hệ thống sẽ không chạy — cả Việt (workers) lẫn Thư (eval) đều bị block.

**Phần tôi phụ thuộc vào thành viên khác:**

Tôi cần `retrieval_worker` của Việt hoàn thiện trước thì `policy_tool_worker` mới có chunks để phân tích. Tôi cũng cần `eval_trace.py` của Thư để kiểm tra routing distribution có cân bằng không.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì?

Tôi sẽ thêm **LLM fallback classification** vào `supervisor_node` cho các câu hỏi không match keyword nào. Hiện tại câu q09 ("ERR-403-AUTH là lỗi gì?") bị route sai vào `human_review` vì không chứa keyword rõ ràng — confidence chỉ 0.25 (thấp nhất trong 15 câu). Nếu thêm 1 lần gọi LLM (~800ms) chỉ cho trường hợp "default route", tôi có thể nâng confidence của nhóm câu này lên 0.6+ mà không ảnh hưởng latency của 14 câu còn lại.

---

*Lưu file này với tên: `reports/individual/Trần Văn Tuấn.md`*
