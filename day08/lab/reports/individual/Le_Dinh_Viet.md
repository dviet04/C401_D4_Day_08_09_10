# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Lê Đình Việt
**Vai trò trong nhóm:**  Retrieval Owner / Documentation Owner  
**Ngày nộp:** 13/04/2026 
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

> Mô tả cụ thể phần bạn đóng góp vào pipeline: Tôi chủ yếu làm spint 1, 2, và 3
> - Cụ thể tôi đã implement: Dense retrieval, ChromaDB, Embedding (OpenAI), Citation, Context building, RAG pipeline, Similarity threshold, LLM generation, Query transformation, Expansion, Multi-query retrieval
> - Công việc của bạn kết nối với phần của người khác như thế nào: Chúng tôi thảo luận với nhau và phân công nghiệm vụ hoặc làm song song để so sánh kết quả và chọn code của người có kết quả cao hơn. Ví dụ phần 1, 2, 3 là chúng tôi làm đồng thời để chọn người có kết quả cao hơn

_________________

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

> Chọn 1-2 concept từ bài học mà bạn thực sự hiểu rõ hơn sau khi làm lab.
> Ví dụ: chunking, hybrid retrieval, grounded prompt, evaluation loop.
> Giải thích bằng ngôn ngữ của bạn — không copy từ slide.
### 1. Query Transformation
- Vấn đề: query khác wording trong docs → dễ miss
- Giải pháp: viết lại query (expansion / decomposition / HyDE)
- Giúp retrieval tốt bằng cách hỏi đúng cách trước khi search
### 2. LLM-as-judge
- Vấn đề: khó đánh giá output bằng rule cứng
- Giải pháp: dùng LLM để chấm (đúng/sai, có bịa không)
- Dùng LLM như “người chấm bài thông minh” giúp đánh giá hệ thống tốt hơn
_________________

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

> Điều gì xảy ra không đúng kỳ vọng?
- Điều xảy ra không đúng ký vọng của tôi là tôi code LLM-as-judge không đạt yêu cầu và tốn nhiều thời gian chỉnh hơn tôi nghĩ
> Lỗi nào mất nhiều thời gian debug nhất?
- Sử dụng LLM để đánh giá đúng Faithfulness của những câu truy vấn mà không có trong database
> Giả thuyết ban đầu của bạn là gì và thực tế ra sao?
- Ban đầu tôi nghĩ Faithfulness sẽ dễ dàng đánh giá nhưng thực tế tôi mất nhiều thời gian để chỉnh sửa phần này và kết quả cuối cùng vẫn chưa khả quan

_________________

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

> Chọn 1 câu hỏi trong test_questions.json mà nhóm bạn thấy thú vị.
> Phân tích:
> - Baseline trả lời đúng hay sai? Điểm như thế nào?
> - Lỗi nằm ở đâu: indexing / retrieval / generation?
> - Variant có cải thiện không? Tại sao có/không?

**Câu hỏi:** gq08 — Nhân viên phải báo trước bao nhiêu ngày để xin nghỉ phép năm? Con số này có giống với số ngày cần giấy tờ khi nghỉ ốm không?

**Phân tích:**

Ở baseline, câu trả lời chưa hoàn toàn faithful (2/5) dù relevance và recall đều cao. Điều này cho thấy hệ thống đã retrieve đúng context, nhưng generation chưa tổng hợp đầy đủ thông tin, dẫn đến câu trả lời thiếu chính xác hoặc chưa rõ ràng phần so sánh giữa hai chính sách.

Lỗi chính nằm ở generation, không phải retrieval hay indexing, vì context_recall = 5 cho thấy dữ liệu cần thiết đã có trong các chunk được lấy ra.

Ở variant (dense + expansion), kết quả được cải thiện rõ rệt faithfulness tăng từ 2 → 4, completeness từ 4 → 5. Query transformation giúp tạo thêm các cách diễn đạt khác, từ đó retrieve được chunk đầy đủ hơn hoặc rõ nghĩa hơn, giúp model tổng hợp thông tin tốt hơn khi generate.

Điều này cho thấy query transformation có thể gián tiếp cải thiện generation thông qua việc nâng chất lượng context đầu vào.

_________________

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

> 1-2 cải tiến cụ thể bạn muốn thử.
> Không phải "làm tốt hơn chung chung" mà phải là:
> "Tôi sẽ thử X vì kết quả eval cho thấy Y."
Nếu có thêm thời gian, tôi sẽ thử kết hợp rerank bằng cross-encoder hoặc hybrid search vì kết quả hiện tại cho thấy một số chunk top-k vẫn chưa thực sự relevant dù score cao.

Ngoài ra, tôi sẽ cải thiện query transformation (HyDE + filtering) vì đôi khi expansion tạo ra query nhiễu, làm giảm precision. Mục tiêu là tăng recall nhưng vẫn giữ được độ chính xác của kết quả retrieval.

_________________

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*
*Ví dụ: `reports/individual/nguyen_van_a.md`*
