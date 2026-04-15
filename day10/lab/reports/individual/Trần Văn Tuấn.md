# Báo cáo cá nhân — Lab Day 10

**Họ và tên:** Trần Văn Tuấn  
**Email:** trantuan6304@gmail.com  
**Vai trò:** Ingestion / Raw Owner, Cleaning & Quality Owner (Sprint 1, 2)  
**Độ dài:** ~450 từ  

---

## 1. Phụ trách (Trách nhiệm chi tiết trong dự án)

Trong dự án ETL Day 10, tôi đảm nhận hoàn chỉnh trọng trách tại Sprint 1 và Sprint 2: Thiết lập Ingestion (nạp liệu thô từ CSV) và quản lý trọn vẹn lớp khiên bảo vệ làm sạch Dữ liệu (Cleaning & Quality Owner). 

Cụ thể, tôi đã quản trị và vận hành toàn bộ 9 Luật Làm sạch (Cleaning Rules) trong `transform/cleaning_rules.py`, bao trùm mọi rủi ro biến dạng dữ liệu:
- **R1 - R5 (Luật Core Baseline)**: Xóa sổ các `doc_id` ngoại lai (danh sách đen lạ); Ép kiểu (Parse) và loại bỏ ngày tháng sai định dạng; Cô lập các bản Document chính sách HR đã quá hạn sử dụng; Đào thải dòng trống rỗng và Khử trùng lặp độ chính xác tuyệt đối (Dedupe).
- **R6 (Auto-Fix Stale Policy)**: Phát hiện và chủ động sửa văn bản chính sách hoàn tiền cũ mốc từ "14 ngày làm việc" về đúng "7 ngày làm việc" theo phiên bản 2026.
- **R7 (`_strip_bom_and_control_chars`)**: Dọn dẹp mã BOM (`\ufeff`) và ký tự điều khiển tàng hình (Luật tôi code bổ sung).
- **R8 (`_normalize_ordinal_day_format`)**: Đồng bộ hóa mọi cách viết ngày thành định dạng số (Ví dụ: đồng hóa chuỗi "bảy ngày" thành "7 ngày").
- **R9 (`_is_chunk_too_short`)**: Thiết lập cơ chế tự động cách ly các câu từ quá ngắn (dưới 20 ký tự) vì vô giá trị với LLM.

Đồng thời, tôi cập nhật 2 luật kiểm định chạy sau quy trình dọn dẹp tại `quality/expectations.py` gồm Expectation **E7** và **E8**. Kết quả đầu ra của tôi sinh ra metadata về số lượng `cleaned_records` cũng như file log CSV đã làm sạch để bàn giao cho Embed Owner đẩy lên DB phục vụ cho hệ thống RAG đa tác vụ.

---

## 2. Quyết định kỹ thuật

**Thiết lập Severity (Halt vs Warn) cho Guardrails:** 
Trong quá trình rà soát dữ liệu, tôi quyết định không áp dụng mức phạt `halt` (dừng khẩn cấp toàn bộ hệ thống) cho tất cả các lỗi. Đây là một nguyên tắc thiết kế phòng thủ nhiều lớp (Defense-in-depth).

Đối với lỗi như ký tự BOM lọt thủng qua rây lọc (phát hiện bằng kỳ vọng E7), tôi cài cấu hình bắt buộc **halt** và ép hệ thống thoát (exit code = 2). Nguyên nhân là vì BOM sẽ đánh lừa hàm băm hash sinh ID khi dedupe, phá vỡ môi trường Vector ChromaDB triệt để; thả lỏng là toàn bộ Database sẽ lỗi index. 

Trái lại, với Expectation E8 (không còn dư lại chunk hoàn tiền nào), tôi thiết lập **warn**. Khác với lỗi định dạng cấu trúc, việc thiếu tài liệu là bài toán độ bao phủ dữ liệu (Data Coverage). Pipeline vận hành về mặt kỹ thuật vẫn trơn tru, ta chỉ cần phát cảnh báo log ra để chuyên viên Dữ liệu (Data Steward) xem xét kiểm tra nguồn thay vì để hệ thống bị "treo" oan uổng gây ảnh hưởng down-time đến cả dự án máy chủ.

---

## 3. Phân tích Sự cố / Anomaly

Trong Sprint thử nghiệm ban đầu, tôi chạm trán một sự cố dị thường: 
Dù `chunk_text` in ra màn hình Terminal bằng Python hoàn toàn bình thường, không thấy lỗi khoảng trắng dư thừa nào, nhưng luật khử trùng lặp (Rule 5 - Dedupe) và cả câu hỏi kiểm chứng RAG liên tục bắt trượt.

**Quá trình chẩn đoán:** Tôi quyết định phân tích byte nguyên thủy của chuỗi chuỗi ký tự và tìm ra thủ phạm là ký tự biến dị xuất hiện khi export nguồn từ file CSV bị nhiễm mã BOM từ hệ điều hành Windows (`\ufeff`) xen lẫn vài ký tự non-printable (Control Chars). Các mã ẩn này bẻ cong vector nhúng khiến LLM không thể match với keyword mong muốn.

**Khắc phục:** Tôi đã lập tức vá lỗi này thông qua hàm Rule 7: Sử dụng regex `_CONTROL_CHARS.sub("", text)` quét sạch rác đi kèm với `text.replace("\ufeff", "")`. Kết quả log expectation `E7 (no_bom_in_chunk_text)` ngay lập tức xác nhận trạng thái chuyển từ `FAIL (halt)` (khi test inject) sang `PASS` xanh mượt (khi clean-run).

---

## 4. Bằng chứng trước / sau (Before/After)

Minh chứng chỉ ra luật thay đổi chính sách từ 14 ngày (bản cũ) sang 7 ngày làm việc (bản mới) đã loại trừ hoàn toàn tình trạng trích xuất lỗi của mô hình RAG.

**Trước khi sửa (Lỗi bị Inject - Trích xuất từ tệp `after_inject_bad.csv`):**
```csv
question_id, question, top1_doc_id, top1_preview, contains_expected, hits_forbidden
q_refund_window, "Khách hàng có bao nhiêu ngày...", policy_refund_v4, "Yêu cầu... 7 ngày...", yes, yes
```
*(run_id tương ứng: `inject-bad`. Nhận xét: Cờ `hits_forbidden=yes` tố cáo hệ thống RAG không qua làm sạch đã lỡ lụm nhầm policy cũ 14 ngày vào prompt cho LLM)*

**Sau khi vòng lặp Clean hoàn thành (Trích xuất từ tệp `after_clean_run.csv`):**
```csv
question_id, question, top1_doc_id, top1_preview, contains_expected, hits_forbidden
q_refund_window, "Khách hàng có bao nhiêu ngày...", policy_refund_v4, "Yêu cầu... 7 ngày...", yes, no
```
*(run_id tương ứng: `clean-run`. Nhận xét: Chunk chứa 14 ngày đã được prune thành công. Cờ trở thành `hits_forbidden=no`, cam kết cho câu trả lời chuẩn xác nhất).*

---

## 5. Kế hoạch cải tiến thêm (nếu có thêm 2 giờ)

- Thay vì giới hạn chiều dài Chunk bằng số fix cứng `MIN_CHUNK_CHARS=20` trong code python, tôi sẽ nhúng nó vào `.env` hoặc yaml configuration của `data_contract` để dễ chỉnh sửa khi quy mô của dự án mở rộng, đáp ứng tiêu chí hạng Distinction.
- Chuyển cấu trúc Validator Expectation thủ công sang bộ thư viện Great Expectations hoặc Pydantic Data Contract.
