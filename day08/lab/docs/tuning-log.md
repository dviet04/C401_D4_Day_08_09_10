# Tuning Log — RAG Pipeline (Day 08 Lab)

> Template: Ghi lại mỗi thay đổi và kết quả quan sát được.
> A/B Rule: Chỉ đổi MỘT biến mỗi lần.

---

## Baseline (Sprint 2)

**Ngày:** 13/04/2026  
**Config:**
```
retrieval_mode = "dense"
chunk_size = 450 tokens
overlap = 80 tokens
top_k_search = 10
top_k_select = 3
use_rerank = False
llm_model = gpt-4o-mini
```

**Scorecard Baseline:**
| Metric | Average Score |
|--------|--------------|
| Faithfulness | 3.40/5 |
| Relevance | 4.10/5 |
| Context Recall | 5.00/5 |
| Completeness | 3.70/5 |

**Câu hỏi yếu nhất (điểm thấp):**
> TODO: Liệt kê 2-3 câu hỏi có điểm thấp nhất và lý do tại sao.
> Ví dụ: "q07 (Approval Matrix) - context recall = 1/5 vì dense bỏ lỡ alias."
gq05 (Admin Access contractor)  
  → Relevance = 1/5, Faithfulness = 2/5 vì system trả “Không đủ dữ liệu” dù có thể thiếu context hoặc retrieve chưa đúng

gq07 (SLA penalty)  
  → Relevance = 1/5, Faithfulness = 1/5 vì không retrieve được thông tin → trả lời abstain

**Giả thuyết nguyên nhân (Error Tree):**
- [ ] Indexing: Chunking cắt giữa điều khoản
- [ ] Indexing: Metadata thiếu effective_date
- [x] Retrieval: Dense bỏ lỡ exact keyword / alias
- [ ] Retrieval: Top-k quá ít → thiếu evidence
- [x] Generation: Prompt không đủ grounding
- [ ] Generation: Context quá dài → lost in the middle

---

## Variant 1 (Sprint 3)

**Ngày:** 13/04/2026  
**Biến thay đổi:** query_transform_strategy bằng expansion
**Lý do chọn biến này:** Baseline cho thấy một số câu có faithfulness thấp (gq02, gq08, gq09) dù recall = 5 → vấn đề không phải thiếu context mà là context chưa đủ rõ hoặc chưa match tốt với query. Vì vậy chọn query expansion để cải thiện cách diễn đạt query → tăng chất lượng context.
> TODO: Giải thích theo evidence từ baseline results.
> Ví dụ: "Chọn hybrid vì q07 (alias query) và q09 (mã lỗi ERR-403) đều thất bại với dense.
> Corpus có cả ngôn ngữ tự nhiên (policy) lẫn tên riêng/mã lỗi (ticket code, SLA label)."

**Config thay đổi:**
```
"query_transform_strategy": "expansion" 
# Các tham số còn lại giữ nguyên như baseline
```

**Scorecard Variant 1:**
| Metric | Baseline | Variant 1 | Delta |
|--------|----------|-----------|-------|
| Faithfulness | 3.40/5 | 3.70/5 | +0.30 |
| Answer Relevance | 4.10/5 | 4.60/5 | +0.50 |
| Context Recall | 5/5 | 5/5 | 0 |
| Completeness | 3.70/5 | 3.70/5 | 0 |

---

## Variant 2 (nếu có thời gian)

**Biến thay đổi:** Tăng `top_k_search` từ 10 → 15  
**Config:**
```
# TODO
```
```
"top_k_search": 15 
# Các tham số còn lại giữ nguyên như baseline
```

**Scorecard Variant 2:**
| Metric | Baseline | Variant 1 | Variant 2 | Best |
|--------|----------|-----------|-----------|------|
| Faithfulness | 3.60/5 | 3.70/5 | 3.50/5 | Variant 1 |
| Answer Relevance | 4.60/5 | 4.60/5 | 4.20/5 | Tie (Baseline/Var1) |
| Context Recall | 5/5 | 5/5 | 5/5 | All |
| Completeness | 3.70/5 | 3.70/5 | 3.50/5 | Tie (Baseline/Var1) |

---

## Tóm tắt học được

> TODO (Sprint 4): Điền sau khi hoàn thành evaluation.

1. **Lỗi phổ biến nhất trong pipeline này là gì?**
   > Generation chưa faithful dù retrieval đúng (model không tổng hợp hoặc diễn đạt đúng từ context)

2. **Biến nào có tác động lớn nhất tới chất lượng?**
   > Query transformation (cải thiện chất lượng context → ảnh hưởng trực tiếp đến answer)

3. **Nếu có thêm 1 giờ, nhóm sẽ thử gì tiếp theo?**
   > Thử rerank (cross-encoder) để lọc top-k chunk tốt hơn vì hiện tại vẫn có noise trong context
