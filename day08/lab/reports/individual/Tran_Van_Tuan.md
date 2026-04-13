# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Trần Văn Tuấn  
**Vai trò trong nhóm:** Tech Lead / Retrieval Owner / Eval Owner / Documentation Owner  
**Ngày nộp:** 13/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Trong dự án lab này, với vai trò là Tech Lead và Eval Owner, tôi tập trung mạnh vào **Sprint 2 (Hybrid Retrieval & Metadata)** và **Sprint 4 (Evaluation Metrics)**. 

Cụ thể, tôi đã thực hiện cải thiện đoạn script `index.py` để bổ sung metadata một cách nhất quán khi đẩy dữ liệu lên ChromaDB. Sau đó, tôi trực tiếp nâng cấp file `rag_answer.py` xử lý Hybrid Retrieval – kết hợp điểm mạnh của Dense Search (bắt nghĩa) và Sparse Search (bắt từ khóa), kết thúc bằng việc đẩy qua Cross-encoder Reranking để lấy ra những chunk thực sự sắc bén. 

Nhằm chứng minh hiệu quả của pipeline, tôi xây dựng bộ khung đánh giá LLM-as-a-judge trong `eval.py` để đo lường 4 tiêu chí khắt khe: Faithfulness, Relevance, Context Recall và Completeness. Việc tôi hoàn thiện bộ đo lường (Eval) đã giúp các thành viên khác trong nhóm có cơ sở rõ ràng để tinh chỉnh prompt cũng như chunk size, biến quá trình "thử - sai" cảm tính thành tối ưu bằng số liệu thực tế.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Hai concept mà tôi thực sự ngộ ra và thấu hiểu sau lab này chính là **Hybrid Retrieval** và **Evaluation Loop**.

Từng nghĩ RAG chỉ đơn giản là gọi vector database (Dense Search), nhưng qua bài tập này, tôi nhận thấy Dense Search rất hay "trượt" đối với các loại từ khóa chuyên ngành, mã lỗi cụ thể hoặc ID tài liệu (như `ERR-403-AUTH`). Việc áp dụng Hybrid Retrieval đã khắc phục hiệu quả điểm yếu này, giúp hệ thống không bỏ sót context quan trọng. 

Thứ hai, vòng lặp đánh giá (Evaluation loop). Ban đầu, tôi test RAG rất thủ công bằng cách hỏi vài câu và đọc bằng mắt. Giờ đây, khi thiết lập scorecard runner với các metrics rõ ràng, tôi hiểu rằng: để production có thể tồn tại, mọi thay đổi (dù là prompt hay chunk strategy) đều phải chạy tự động qua bộ test trên các tập baseline và variant. Nếu Context Recall tốt nhưng Faithfulness kém chứng tỏ lỗi nằm ở prompt bắt model nhái text, điều này giúp thu hẹp đáng kể phạm vi debug.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Khó khăn mất thời gian nhất của tôi đến từ vấn đề "Hallucination khi thiếu Context" trong quá trình debug ở các câu hỏi bẫy. 

Ban đầu, tôi đinh ninh với chỉ thị (Grounded prompt): *"Chỉ trả lời dựa trên context được cấp"*, hệ thống LLM sẽ mặc định nói *"Tôi không biết"* khi người dùng đưa ra các truy vấn không có trong tài liệu (như câu q09 về lỗi ERR-403-AUTH). Thực tế lại trái ngược: ở phiên bản baseline, LLM thi thoảng vẫn dùng common knowledge của mình cố sinh ra lời giải thích vòng vo, hoặc gợi ý hướng dẫn "liên hệ IT Helpdesk" bất chấp tài liệu không cung cấp.

Tôi đã mất khá nhiều công sức để điều chỉnh lại cấu trúc prompt, bắt buộc RAG phải kiểm soát mạnh tay việc abstain (từ chối trả lời). Điều này dạy tôi rằng không bao giờ được chủ quan tin 100% vào zero-shot prompt nếu không có metric Faithfulness giám sát.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** q07 - "Approval Matrix để cấp quyền hệ thống là tài liệu nào?" (Sử dụng alias/tên cũ tài liệu để kiểm tra Hybrid Retrieval).

**Phân tích:**
Đây là một query rất hay nhằm phân tích khả năng lọc nhiễu của Retrieval và Generation.
- **Baseline (Dense):** Đạt điểm Relevance cao và Context Recall tuyệt đối (5/5). Tuy nhiên, câu trả lời do model sinh ra đã *hallucinate* thêm thông tin sai lệch: tự động nhắc đến "Level 4 (Admin Access)" dù trong các chunk được cung cấp không hề mô tả chi tiết quyền này. Điều này làm điểm Faithfulness giảm xuống 4.
- **Lỗi nằm ở đâu:** Lỗi chính nằm ở bước Generation (sinh văn bản). LLM baseline có thể đã bị "nhiễu" bởi lượng text quá rộng được trả về từ chỉ Dense Search, khiến model tự thêm thắt tri thức bên ngoài vào để hoàn thiện câu trả lời.
- **Variant có cải thiện không?:** Có sự cải thiện rõ rệt. Trên cấu hình Variant (Hybrid + Rerank + Expand), hệ thống trả về đúng trọng tâm rằng Approval Matrix nay có tên là Access Control SOP. Mức độ trung thực (Faithfulness) đạt tối đa 5/5, chứng minh việc giới hạn kết quả bằng Reranker giúp LLM tập trung vào đúng nội dung, giảm thiểu hoàn toàn chứng "ảo giác".

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Nếu có thêm thời gian, tôi sẽ thử nghiệm thêm **Dynamic Chunking (Semantic Chunking)** kết hợp **Adaptive Threshold** trong Reranking.
Kết quả từ Eval cho thấy ở những câu dài hoặc nhiều điều kiện nhánh (như q08 về HR Policy Remote - "bắt buộc phải duyệt qua HR portal"), model thi thoảng vẫn bỏ sót ý (Completeness bị hụt điểm). Nguyên nhân do chunk cắt tĩnh có thể làm đứt đoạn logic câu. Bằng việc phân tách chunk theo ngữ nghĩa và thiết lập ngưỡng loại bỏ chunk không liên quan mạnh tay hơn, tôi tin điểm Completeness và Faithfulness sẽ còn tiệm cận mức hoàn hảo.

---

*Lưu file này với tên: `reports/individual/Tran_Van_Tuan.md`*
