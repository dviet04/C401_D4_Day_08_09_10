# Báo Cáo Cá Nhân — Lab Day 10

**Tên sinh viên:** Trần Văn Tuấn
**Email:** trantuan6304@gmail.com
**Vai trò:** Ingestion / Raw Owner, Cleaning & Quality Owner (Phụ trách Sprint 1, 2)

---

## 1. Chi tiết phần đóng góp (100–150 từ)

Trong phần này, tôi đảm nhận việc nạp dữ liệu thô (Ingestion) và thiết lập các kịch bản làm sạch cốt lõi (Cleaning & Quality). Cụ thể, tôi đã viết các luật `cleaning_rules.py` để loại bỏ các bản ghi không đạt chuẩn nghiệp vụ trước khi đưa vào cơ sở dữ liệu véc-tơ. 

Tôi đã trực tiếp triển khai luật R7 (`_strip_bom_and_control_chars`) để loại bỏ BOM và ký tự điều khiển, R8 (`_normalize_ordinal_day_format`) để chuẩn hóa ngày viết bằng chữ ("bảy ngày" thành "7 ngày") và R9 (`_is_chunk_too_short`) để loại bỏ các chunk bé hơn 20 ký tự. Ngoài ra, tôi hỗ trợ tích hợp 2 Expectation quan trọng là E7 (HALT nếu hệ thống còn sót lỗi BOM U+FEFF sau khi qua rule R7) và E8 (WARN nếu vô tình cách ly nhầm mất toàn bộ policy hoàn tiền) bên trong file `expectations.py`.

## 2. Định hướng kỹ thuật (80–120 từ)

Quyết định kỹ thuật quan trọng nhất mà tôi theo đuổi là thiết kế tư duy phòng thủ (Defense-in-depth) bằng cách cấu hình **Severity** khác nhau trong Data Guardrails. 

Ví dụ: Nếu Expectation E7 phát hiện ký tự BOM lọt qua lưới lọc, tôi dùng lệnh `halt` để ép toàn bộ hệ thống phải dừng (exit = 2) vì ký tự lạ này sẽ phá vỡ toàn bộ cấu trúc index của Embedding (Lỗi kỹ thuật nghiêm trọng). Ngược lại, nếu dữ liệu hoàn tiền bị rút cạn (E8), tôi chỉ thiết lập mức `warn` vì nó cảnh báo rủi ro về độ bao phủ dữ liệu (business log) nhưng luồng pipeline kỹ thuật vẫn có thể vận hành bình thường mà không gây crash nền tảng DB. 

## 3. Phân tích sự cố và giải pháp (100–150 từ)

- **Triệu chứng:** Khi mô phỏng quá trình load file CSV thô vào hệ thống, các query retrieval thỉnh thoảng thất bại một cách vô hình, chunk text trông hoàn toàn bình thường khi print log nhưng lại không match được bất kỳ luật rule string nào.
- **Nguyên nhân:** Export của tệp `policy_export_dirty.csv` từ Windows bị vướng mã ẩn ký tự BOM (`\ufeff`) và các control chars. Chúng phá vỡ thuật toán dedupe khi hash và làm cho LLM hiểu sai từ khóa.
- **Giải pháp:** Tôi đã xây dựng luật R7 dùng regex `_CONTROL_CHARS.sub` kết hợp với `text.replace("\ufeff", "")` ở ngay vòng lặp for đầu tiên của bước biến đổi dữ liệu.
- **Chứng cứ:** Trong log pipeline hiển thị rõ sự thay đổi: từ việc expectation `no_bom_in_chunk_text` bị báo `FAIL (halt)` khi inject BOM, nay đã trả về `PASS` thành công ở các lần Clean Run.

## 4. Bằng chứng trước / sau (80–120 từ)

Chứng minh bộ lọc Clean của tôi đã chặn thành công tài liệu hoàn tiền cũ (14 ngày).

**Trước khi sửa (Lỗi bị Inject - Từ tệp after_inject_bad.csv):**
```csv
question_id, question, top1_doc_id, top1_preview, contains_expected, hits_forbidden
q_refund_window, "Khách hàng có bao nhiêu ngày...", policy_refund_v4, "Yêu cầu... 7 ngày...", yes, yes
```
*(hits_forbidden=yes nghĩa là Hệ thống vô tình trích xuất nhầm cửa sổ 14 ngày đã cũ và cấm LLM)*

**Sau khi sửa (Pipeline Clean đã chạy - Từ tệp after_clean_run.csv):**
```csv
question_id, question, top1_doc_id, top1_preview, contains_expected, hits_forbidden
q_refund_window, "Khách hàng có bao nhiêu ngày...", policy_refund_v4, "Yêu cầu... 7 ngày...", yes, no
```
*(hits_forbidden=no nghĩa là Câu trả lời sạch sẽ, chính sách 14 ngày cũ bị loại bỏ hoàn toàn)*

*(run_id tương ứng lấy từ manifest log là `inject-bad` và `clean-run`)*

## 5. Kế hoạch cải tiến (30–50 từ)

Tôi dự định sẽ tách các ngưỡng tham số cứng như `MIN_CHUNK_CHARS=20` vào `.env` thay vì hardcode bên trong `cleaning_rules.py` để tiện thay đổi linh hoạt các rule sau này, đồng thời tích hợp Great Expectations framework thực thụ.
