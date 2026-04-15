# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Lê Đình Việt 
**Vai trò:** Inject corruption + so sánh eval + quality report 
**Ngày nộp:** 15/04/2026  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:** eval_retrieval.py
- Tôi phụ trách xây dựng pipeline đánh giá retrieval trước/sau khi làm sạch dữ liệu. Cụ thể, tôi implement logic query ChromaDB, kiểm tra contains_expected, hits_forbidden, và top1_doc_expected từ file CSV kết quả. Ví dụ, ở run_id=inject-bad, dòng CSV cho q_refund_window có hits_forbidden=yes, trong khi sau khi chạy lại pipeline (run_id=clean-run) chuyển thành hits_forbidden=no. Tôi cũng tính toán metric tổng hợp để phục vụ quality report.

**Kết nối với thành viên khác:**
Tôi sử dụng dữ liệu cleaned từ Tuấn (Sprint 1–2) và phục vụ báo cáo monitoring/quality cho Thư (Sprint 4).
_________________

**Bằng chứng (commit / comment trong code):**
commit edd8b96066c5d146bbf611066c2e606699bbcaa0
Author: dviet04 <ledinhviet2507@gmail.com>
Date:   Wed Apr 15 15:39:58 2026 +0700

    update eval_retrieval
_________________

---

## 2. Một quyết định kỹ thuật (100–150 từ)

> VD: chọn halt vs warn, chiến lược idempotency, cách đo freshness, format quarantine.
Trong eval_retrieval.py, tôi quyết định đánh giá retrieval dựa trên toàn bộ top-k thay vì chỉ top-1, đặc biệt với metric hits_forbidden. Lý do là theo yêu cầu trong README, lỗi dữ liệu thường không nằm ở câu trả lời chính mà nằm ở các chunk phụ (context nhiễu). Ví dụ ở run_id=inject-bad, mặc dù top1_doc_id=policy_refund_v4 là đúng, nhưng hits_forbidden=yes cho thấy trong top-3 vẫn tồn tại chunk sai (refund 14 ngày). Nếu chỉ kiểm tra top-1 thì sẽ bỏ sót lỗi này. Sau khi áp dụng clean pipeline (run_id=clean-run), hits_forbidden giảm từ 0.25 xuống 0.0. Quyết định này giúp phản ánh đúng chất lượng dữ liệu và phù hợp với tiêu chí observability của bài lab
_________________

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

> Mô tả triệu chứng → metric/check nào phát hiện → fix.
Một anomaly tôi phát hiện là retrieval trả về kết quả đúng nhưng vẫn chứa dữ liệu lỗi thời. Cụ thể, trong file before_after_eval.csv, với run_id=inject-bad, dòng q_refund_window có contains_expected=yes nhưng hits_forbidden=yes. Điều này cho thấy hệ thống vẫn retrieve chunk policy cũ (14 ngày hoàn tiền) dù đã có chunk mới (7 ngày). Tôi phát hiện vấn đề này thông qua metric hits_forbidden trong eval_retrieval.py. Nguyên nhân là pipeline chưa loại bỏ hoàn toàn dữ liệu stale trước khi embed. Sau khi chạy lại pipeline chuẩn (run_id=clean-run), kết quả chuyển thành hits_forbidden=no, chứng tỏ dữ liệu lỗi thời đã được loại bỏ. Điều này xác nhận cleaning rules và embed pruning hoạt động đúng.
_________________

---

## 4. Bằng chứng trước / sau (80–120 từ)

> Dán ngắn 2 dòng từ `before_after_eval.csv` hoặc tương đương; ghi rõ `run_id`.
Trước khi làm sạch dữ liệu (run_id=inject-bad), truy vấn q_refund_window trả về kết quả đúng (contains_expected=yes) nhưng vẫn chứa nội dung sai hoặc lỗi thời (hits_forbidden=yes). Điều này cho thấy hệ thống retrieval bị “nhiễu”, khi các chunk policy cũ (ví dụ 14 ngày hoàn tiền) vẫn xuất hiện trong top-k.

Sau khi chạy pipeline chuẩn (run_id=clean-run), cùng truy vấn này cho kết quả contains_expected=yes, hits_forbidden=no, chứng tỏ các chunk lỗi thời đã được loại bỏ. Các truy vấn khác giữ ổn định, và q_leave_version đạt top1_doc_expected=yes.

Kết quả cho thấy pipeline đã cải thiện chất lượng retrieval mà không làm giảm độ chính xác.
_________________

---

## 5. Cải tiến tiếp theo (40–80 từ)

> Nếu có thêm 2 giờ — một việc cụ thể (không chung chung).
Nếu có thêm 2 giờ, tôi sẽ tích hợp schema validation bằng Pydantic cho dữ liệu cleaned, đảm bảo các trường như doc_id, effective_date, chunk_id luôn đúng định dạng trước khi embed. Đồng thời, tôi sẽ log chi tiết các lỗi schema vào quarantine để dễ truy vết. Việc này giúp phát hiện lỗi sớm hơn và nâng cao độ tin cậy của pipeline.
_________________
