# Routing Decisions Log — Lab Day 09

**Nhóm:** C401_D4_Day09  
**Ngày:** 14/04/2026

---

## Routing Decision #1 — Retrieval đơn giản (SLA query)

**Task đầu vào:**
> "SLA xử lý ticket P1 là bao lâu?"

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains retrieval keyword: ['p1', 'sla', 'ticket']`  
**MCP tools được gọi:** Không  
**Workers called sequence:** `retrieval_worker → synthesis_worker`

**Kết quả thực tế:**
- final_answer: Ticket P1 có SLA phản hồi ban đầu 15 phút, xử lý và khắc phục trong 4 giờ.
- confidence: 0.72
- Correct routing? **Yes** — câu hỏi SLA thuần túy, chỉ cần retrieval.

**Nhận xét:** Routing chính xác. Keyword `p1`, `sla`, `ticket` match rõ ràng RETRIEVAL_KEYWORDS. Không cần policy check vì câu hỏi không liên quan đến exception hay quyền truy cập.

---

## Routing Decision #2 — Policy với MCP tool (License key refund)

**Task đầu vào:**
> "Sản phẩm kỹ thuật số (license key) có được hoàn tiền không?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains policy/access keyword: ['hoàn tiền', 'license', 'license key']`  
**MCP tools được gọi:** Không (rule-based check đủ)  
**Workers called sequence:** `retrieval_worker → policy_tool_worker → synthesis_worker`

**Kết quả thực tế:**
- final_answer: Sản phẩm kỹ thuật số (license key, subscription) thuộc danh mục ngoại lệ không được hoàn tiền theo Điều 3 chính sách v4.
- confidence: 0.86
- Correct routing? **Yes** — câu hỏi về policy exception, cần check refund rules.

**Nhận xét:** Policy_tool_worker phát hiện đúng ngoại lệ `digital_product_exception`. Retrieval trả về chunk từ `policy/refund-v4.pdf` với score 0.58, đủ context để synthesis trả lời chính xác.

---

## Routing Decision #3 — Multi-hop (P1 + Access Level 3)

**Task đầu vào:**
> "Contractor cần Admin Access (Level 3) để khắc phục sự cố P1 đang active. Quy trình cấp quyền tạm thời như thế nào?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `multi-hop: policy + retrieval keywords → policy_tool_worker (will also call retrieval)`  
**MCP tools được gọi:** `get_ticket_info("P1-LATEST")` → trả về ticket IT-9847  
**Workers called sequence:** `retrieval_worker → policy_tool_worker → synthesis_worker`

**Kết quả thực tế:**
- final_answer: On-call IT Admin cấp quyền tạm thời (max 24h) sau khi Tech Lead phê duyệt. Sau 24h phải có ticket chính thức.
- confidence: 0.85
- Correct routing? **Yes** — câu multi-hop cần cả retrieval (SLA P1) lẫn policy (access control).

**Nhận xét:** Đây là routing phức tạp nhất. Supervisor phát hiện cả `cấp quyền`, `access`, `level 3` (POLICY) lẫn `p1`, `sự cố` (RETRIEVAL) → route sang policy_tool_worker, worker tự gọi retrieval trước để lấy context. MCP tool `get_ticket_info` cung cấp thêm thông tin ticket P1 đang active.

---

## Routing Decision #4 — HITL trigger (Unknown error code)

**Task đầu vào:**
> "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Worker được chọn:** `human_review` → auto-approve → `retrieval_worker`  
**Route reason:** `unknown error code (ERR-xxx) without clear context → human review | risk_high=True (emergency/unknown context)`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab.**

Task chứa pattern `ERR-` match `UNKNOWN_ERROR_PATTERNS` nhưng không match keyword nào rõ ràng trong RETRIEVAL_KEYWORDS hay POLICY_KEYWORDS → Supervisor route sang `human_review`. Trong lab mode, HITL auto-approve và re-route sang retrieval. Tuy nhiên, retrieval trả về chunks không liên quan (confidence chỉ 0.25). Nếu dùng LLM classifier thay vì keyword matching, câu này sẽ được route thẳng sang retrieval với kết quả tốt hơn.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 8/15 | 53% |
| policy_tool_worker | 7/15 | 46% |
| human_review | 1/15 | 6% |

### Routing Accuracy

- Câu route đúng: **14 / 15**
- Câu route sai (q09): Không hẳn sai — HITL trigger đúng logic (unknown error code), nhưng retrieval không có data cho ERR-403-AUTH.
- Câu trigger HITL: **1** (q09)

### Lesson Learned về Routing

1. **Keyword matching nhanh nhưng không linh hoạt:** ~1ms routing nhưng miss các câu hỏi không chứa keyword rõ ràng (VD: error codes).
2. **Multi-hop detection cần ưu tiên policy:** Khi câu hỏi match cả retrieval lẫn policy keywords, ưu tiên policy_tool_worker vì worker đó tự gọi retrieval trước — tránh mất context.

### Route Reason Quality

Route reason hiện tại đủ thông tin để debug: ghi rõ matched keywords, có flag `risk_high` và `needs_tool`. Cải tiến: thêm `matched_keyword_count` và `fallback_reason` nếu không match keyword nào, để phân biệt "default route" vs "intentional retrieval route".
