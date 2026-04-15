# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** Nhóm AI20K  
**Ngày:** 14/04/2026

---

## 1. Metrics Comparison

| Metric | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta | Ghi chú |
|--------|----------------------|---------------------|-------|---------|
| Avg confidence | ~0.55 | 0.772 | +0.22 (+40%) | Day 09 có weighted scoring + LLM boost |
| Avg latency (ms) | ~3500 | 8417 | +4917 (+140%) | Multi-hop gọi nhiều worker chain |
| Abstain rate (%) | ~13% | 6.7% (1/15) | -6.3% | Chỉ q09 abstain do missing data |
| Multi-hop accuracy | ~40% | ~85% | +45% | policy_tool_worker tự gọi retrieval trước |
| Routing visibility | ✗ Không có | ✓ Có route_reason | N/A | Mỗi trace ghi rõ lý do routing |
| Debug time (estimate) | ~15 phút | ~3 phút | -12 phút | Test worker độc lập thay vì đọc toàn pipeline |
| MCP tool calls | N/A | 13% (4/30 traces) | N/A | get_ticket_info, check_access_permission |

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Cao (~90%) | Cao (~90%) |
| Latency | ~3s | ~5-6s |
| Observation | Trả lời nhanh, đủ chính xác | Thêm routing overhead (~1s) nhưng kết quả tương đương |

**Kết luận:** Multi-agent **không cải thiện đáng kể** cho câu đơn giản. Thêm overhead routing + worker chain mà accuracy không tăng. Single agent phù hợp hơn cho use case này.

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Accuracy | Thấp (~40%) | Cao (~85%) |
| Routing visible? | ✗ | ✓ |
| Observation | Không phân biệt được câu cần check policy vs chỉ cần retrieval | Supervisor route đúng sang policy_tool_worker, worker tự gọi retrieval trước |

**Kết luận:** Multi-agent **cải thiện vượt trội** cho multi-hop. VD: q13 (Contractor + Level 3 + P1) — Day 08 chỉ trả lời được 1 phần, Day 09 gọi chuỗi retrieval → policy → MCP `get_ticket_info` → synthesis, trả lời đủ cả 2 khía cạnh (SLA escalation + access control).

### 2.3 Câu hỏi cần abstain

| Nhận xét | Day 08 | Day 09 |
|---------|--------|--------|
| Abstain rate | ~13% (2/15) | 6.7% (1/15) |
| Hallucination cases | 0 | 0 |
| Observation | Abstain chung chung | Abstain kèm confidence=0.25, có route_reason giải thích |

**Kết luận:** Cả hai đều không hallucinate (đúng thiết kế). Day 09 cải thiện ở chỗ: trace ghi rõ TẠI SAO abstain (VD: HITL triggered, unknown error code) — giúp debug nhanh hơn.

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
```
Khi answer sai → phải đọc toàn bộ RAG pipeline code → tìm lỗi ở indexing/retrieval/generation
Không có trace → không biết bắt đầu từ đâu
Thời gian ước tính: ~15 phút
```

### Day 09 — Debug workflow
```
Khi answer sai → đọc trace → xem supervisor_route + route_reason
  → Nếu route sai → sửa supervisor routing logic (POLICY_KEYWORDS)
  → Nếu retrieval sai → test retrieval_worker độc lập: python workers/retrieval.py
  → Nếu synthesis sai → test synthesis_worker độc lập: python workers/synthesis.py
Thời gian ước tính: ~3 phút
```

**Câu cụ thể nhóm đã debug:**

Câu q09 (ERR-403-AUTH): Pipeline trả về confidence 0.25 — thấp nhất. Nhờ trace ghi `route_reason: "unknown error code (ERR-xxx) without clear context → human review"`, nhóm xác định ngay vấn đề: Supervisor trigger HITL vì không match keyword. Sửa: Có thể thêm `err-` vào RETRIEVAL_KEYWORDS hoặc dùng LLM fallback classification.

---

## 4. Extensibility Analysis

| Scenario | Day 08 | Day 09 |
|---------|--------|--------|
| Thêm 1 tool/API mới | Phải sửa toàn prompt | Thêm 1 hàm MCP tool + đăng ký vào TOOL_REGISTRY |
| Thêm 1 domain mới | Phải retrain/re-prompt | Thêm 1 worker mới + routing rule |
| Thay đổi retrieval strategy | Sửa trực tiếp trong pipeline | Sửa retrieval_worker độc lập |
| A/B test một phần | Khó — phải clone toàn pipeline | Dễ — swap worker, giữ nguyên graph |

**Nhận xét:** Day 09 dễ mở rộng hơn đáng kể. VD: Thêm tool `check_access_permission` chỉ cần 1 hàm trong `mcp_server.py` + 1 rule dispatch trong `policy_tool.py`, không ảnh hưởng retrieval hay synthesis. Day 08 phải sửa toàn bộ prompt template.

---

## 5. Cost & Latency Trade-off

| Scenario | Day 08 calls | Day 09 calls |
|---------|-------------|-------------|
| Simple query | 1 LLM call | 1 LLM call (synthesis) |
| Complex query | 1 LLM call | 1-2 LLM calls (synthesis + optional LLM-as-Judge) |
| MCP tool call | N/A | 0-1 MCP calls per query |

**Nhận xét về cost-benefit:**

Day 09 tốn tương đương Day 08 về LLM calls (vì chỉ synthesis gọi LLM). Latency tăng chủ yếu do: (1) load SentenceTransformer model mỗi lần (~2s), (2) multi-hop queries đi qua 3 workers chain. Cost không tăng đáng kể nhưng latency tăng ~2x — trade-off chấp nhận được vì accuracy cải thiện +40%.

---

## 6. Kết luận

> **Multi-agent tốt hơn single agent ở điểm nào?**

1. **Multi-hop accuracy:** Tăng từ ~40% → ~85% nhờ routing chuyên biệt (policy vs retrieval)
2. **Debuggability:** Thời gian debug giảm từ ~15 phút → ~3 phút nhờ trace có route_reason

> **Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. **Latency:** Tăng ~2x (3.5s → 8.4s) do worker chain overhead — câu đơn giản không cần thiết

> **Khi nào KHÔNG nên dùng multi-agent?**

Khi hệ thống chỉ xử lý câu hỏi đơn giản (single-document, 1 domain), single agent nhanh hơn mà accuracy tương đương. Multi-agent có giá trị khi domain phức tạp, nhiều ngoại lệ cross-document.

> **Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

Thêm LLM fallback classifier cho Supervisor (xử lý câu không match keyword), cache SentenceTransformer model (giảm latency ~2s), và implement MCP server thật qua HTTP (bonus +2 điểm).
