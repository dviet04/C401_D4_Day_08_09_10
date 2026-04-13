# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Hồ Bảo Thư
**Vai trò trong nhóm:**  Retrieval Owner, Eval Owner, Documentation Owner  
**Ngày nộp:** 13/04/2026
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong lab này, em chủ yếu tham gia vào Sprint 3 và Sprint 4 với vai trò triển khai và đánh giá pipeline. Cụ thể, em đã implement phương pháp **rerank variant** nhằm cải thiện chất lượng chọn lọc các chunks sau bước retrieval. Bên cạnh đó, em là người viết toàn bộ file evaluation (`eval.py`) để chấm điểm pipeline theo 4 metrics: Faithfulness, Relevance, Context Recall và Completeness.  

Sau khi hoàn thành phần eval, em tiến hành chạy test trên tập câu hỏi, so sánh kết quả giữa baseline và các variant, từ đó tạo scorecard và phân tích A/B. Công việc của em kết nối trực tiếp với retrieval (đầu vào chunks) và generation (đầu ra câu trả lời), đóng vai trò cầu nối để đánh giá hiệu quả toàn pipeline.

_________________

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này, em hiểu rõ hơn sự khác biệt giữa các phương pháp retrieval, đặc biệt là **dense retrieval, hybrid retrieval và reranking**. Dense retrieval giúp tìm các đoạn văn có semantic similarity cao nhưng đôi khi thiếu chính xác về keyword. Hybrid retrieval kết hợp keyword và semantic nên cải thiện độ recall, nhưng vẫn có thể trả về nhiều noise.  

Điểm quan trọng em nhận ra là **reranking không giúp tìm thêm thông tin mới**, mà chỉ giúp sắp xếp lại các kết quả đã retrieve. Vì vậy, nếu retrieval ban đầu sai (không lấy đúng chunk), rerank cũng không thể sửa lỗi. Điều này giúp em hiểu rõ pipeline cần tối ưu từ bước retrieval trước khi tối ưu rerank hay generation.

_________________

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Khó khăn lớn nhất của em là viết hệ thống evaluation, đặc biệt trong trường hợp **pipeline không tìm được dữ liệu phù hợp**. Ban đầu, em giả định rằng nếu không có câu trả lời thì tất cả metrics sẽ thấp, nhưng thực tế không phải vậy. Nếu model “abstain” đúng (trả lời không có dữ liệu), thì Faithfulness và Relevance vẫn có thể cao.  

Ngoài ra, việc thiết kế prompt cho LLM để đánh giá cũng khá phức tạp. Nếu prompt không rõ ràng, model sẽ chấm điểm không nhất quán. Em cũng phải chỉnh sửa prompt để model không chỉ trả lời “không có dữ liệu” mà còn giải thích rõ hơn cho người dùng. Điều này mất khá nhiều thời gian debug vì lỗi không nằm ở code mà ở hành vi của LLM.


_________________

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:**  
Contractor từ bên ngoài công ty có thể được cấp quyền Admin Access không? Nếu có, cần bao nhiêu ngày và có yêu cầu đặc biệt gì?  

**Phân tích:**  

Ở câu hỏi này, cả baseline và variant đều không trả lời đúng mà fallback về “không tìm thấy dữ liệu”. Điều này dẫn đến điểm Faithfulness cao (vì không hallucinate), nhưng Relevance, Recall và Completeness đều thấp.  

Nguyên nhân chính nằm ở **retrieval**, không phải generation. Thông tin của câu hỏi nằm ở **hai section khác nhau** (scope + Level 4 details), yêu cầu multi-chunk reasoning. Tuy nhiên, hệ thống retrieval không lấy được đủ cả hai phần, dẫn đến thiếu context. Khi không có đủ chunks, model buộc phải abstain.  

Variant (có query transform) cũng không cải thiện được vì vấn đề không nằm ở cách diễn đạt query, mà ở việc **indexing hoặc chunking chưa tối ưu**, khiến các thông tin liên quan bị tách rời. Điều này cho thấy pipeline hiện tại chưa xử lý tốt các câu hỏi yêu cầu tổng hợp nhiều nguồn thông tin, và rerank hoặc transform không thể bù đắp cho lỗi retrieval ban đầu.

_________________

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)
Nếu có thêm thời gian, em sẽ cải thiện **chunking strategy**, đặc biệt là giữ các section liên quan gần nhau để hỗ trợ multi-hop retrieval. Ngoài ra, em muốn thử **hybrid retrieval + rerank kết hợp**, vì eval cho thấy retrieval hiện tại bỏ sót nhiều thông tin quan trọng. Cuối cùng, em sẽ refine prompt để model không chỉ abstain mà còn gợi ý hướng tìm thông tin rõ ràng hơn.

_________________

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*
*Ví dụ: `reports/individual/nguyen_van_a.md`*
