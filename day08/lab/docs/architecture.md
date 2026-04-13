# Architecture — RAG Pipeline (Day 08 Lab)

> Template: Điền vào các mục này khi hoàn thành từng sprint.
> Deliverable của Documentation Owner.

## 1. Tổng quan kiến trúc

```
[Raw Docs]
    ↓
[index.py: Preprocess → Chunk → Embed → Store]
    ↓
[ChromaDB Vector Store]
    ↓
[rag_answer.py: Query → Retrieve → Rerank → Generate]
    ↓
[Grounded Answer + Citation]
```

**Mô tả ngắn gọn:**
> TODO: Mô tả hệ thống trong 2-3 câu. Nhóm xây gì? Cho ai dùng? Giải quyết vấn đề gì?
Hệ thống của nhóm là một ứng dụng truy xuất thông tin thông minh, hỗ trợ IT Helpdesk và người dùng nội bộ tra cứu nhanh các chính sách, quy trình và tài liệu liên quan. Hệ thống giúp giảm thời gian tìm kiếm thông tin, tăng hiệu quả hỗ trợ và đảm bảo cung cấp câu trả lời chính xác, nhất quán.

---

## 2. Indexing Pipeline (Sprint 1)

### Tài liệu được index
| File | Nguồn | Department | Số chunk |
|------|-------|-----------|---------|
| `policy_refund_v4.txt` | policy/refund-v4.pdf | CS | 6 |
| `sla_p1_2026.txt` | support/sla-p1-2026.pdf | IT | 5 |
| `access_control_sop.txt` | it/access-control-sop.md | IT Security | 7 |
| `it_helpdesk_faq.txt` | support/helpdesk-faq.md | IT | 6 |
| `hr_leave_policy.txt` | hr/leave-policy-2026.pdf | HR | 5 |

### Quyết định chunking
| Tham số | Giá trị | Lý do |
|---------|---------|-------|
| Chunk size | 450 tokens | Nằm trong range tối ưu (300–500 tokens) giúp cân bằng giữa ngữ cảnh đủ dài và retrieval chính xác; phù hợp với embedding model như text-embedding-3-small |
| Overlap | 80 tokens | Giúp giữ ngữ cảnh liên tục giữa các chunk, tránh mất thông tin ở ranh giới (đặc biệt với câu dài hoặc điều khoản pháp lý). 80 tokens ~ mức cao trong range (50–80) nên tăng recall |
| Chunking strategy | Heading-based / paragraph-based | Ưu tiên chia theo section/heading để giữ semantic structure, sau đó fallback sang paragraph/sentence splitting khi quá dài → đảm bảo chunk “tự nhiên” thay vì cắt cứng theo token. |
| Metadata fields | source, section, effective_date, department, access | Phục vụ filter, freshness, citation |

### Embedding model
- **Model**: OpenAI text-embedding-3-small 
- **Vector store**: ChromaDB (PersistentClient)
- **Similarity metric**: Cosine

---

## 3. Retrieval Pipeline (Sprint 2 + 3)

### Baseline (Sprint 2)
| Tham số | Giá trị |
|---------|---------|
| Strategy | Dense (embedding similarity) |
| Top-k search | 10 |
| Top-k select | 3 |
| Rerank | Không |

### Variant (Sprint 3)
| Tham số | Giá trị | Thay đổi so với baseline |
|---------|---------|------------------------|
| Strategy | TODO (hybrid / dense) | TODO |
| Top-k search | TODO | TODO |
| Top-k select | TODO | TODO |
| Rerank | TODO (cross-encoder / MMR) | TODO |
| Query transform | TODO (expansion / HyDE / decomposition) | TODO |

**Lý do chọn variant này:**
> TODO: Giải thích tại sao chọn biến này để tune.
> Ví dụ: "Chọn hybrid vì corpus có cả câu tự nhiên (policy) lẫn mã lỗi và tên chuyên ngành (SLA ticket P1, ERR-403)."

---

## 4. Generation (Sprint 2)

### Grounded Prompt Template
```
Answer only from the retrieved context below.
If the context is insufficient, say you do not know.
Cite the source field when possible.
Keep your answer short, clear, and factual.

Question: {query}

Context:
[1] {source} | {section} | score={score}
{chunk_text}

[2] ...

Answer:
```

### LLM Configuration
| Tham số | Giá trị |
|---------|---------|
| Model | gpt-4o-mini |
| Temperature | 0 (để output ổn định cho eval) |
| Max tokens | 512 |

---

## 5. Failure Mode Checklist

> Dùng khi debug — kiểm tra lần lượt: index → retrieval → generation

| Failure Mode | Triệu chứng | Cách kiểm tra |
|-------------|-------------|---------------|
| Index lỗi | Retrieve về docs cũ / sai version | `inspect_metadata_coverage()` trong index.py |
| Chunking tệ | Chunk cắt giữa điều khoản | `list_chunks()` và đọc text preview |
| Retrieval lỗi | Không tìm được expected source | `score_context_recall()` trong eval.py |
| Generation lỗi | Answer không grounded / bịa | `score_faithfulness()` trong eval.py |
| Token overload | Context quá dài → lost in the middle | Kiểm tra độ dài context_block |

---

## 6. Diagram (tùy chọn)

> TODO: Vẽ sơ đồ pipeline nếu có thời gian. Có thể dùng Mermaid hoặc drawio.

[Raw Documents]
        |
        v
[Preprocess Metadata]
        |
        v
[Chunking (450 tokens, overlap 80)]
        |
        v
[Embedding (text-embedding-3-small)]
        |
        v
[ChromaDB Vector Store]
        |
        v
======================
   RETRIEVAL
======================
        |
        v
[User Query] ----> [Query Alternatives]
        |                 |
        |-----------------|
        v
[Query Embedding]
        |
        v
[Dense Search (ChromaDB)]
        |
        v
[Top-10 Candidates]
        |
        v
[Rerank?]
   |        |
  No       Yes
   |        |
   v        v
[Top-3]   [Cross-Encoder]
   |__________|
        |
        v
======================
   GENERATION
======================
        |
        v
[Build Context Block]
        |
        v
[Grounded Prompt]
        |
        v
[LLM (gpt-4o-mini)]
        |
        v
[Answer + Citation]
        |
        v
======================
   EVALUATION
======================
        |
        v
[Baseline] ----\
               \
                --> [Score Metrics] --> [A/B Compare]
               /
[Variant] ----/
