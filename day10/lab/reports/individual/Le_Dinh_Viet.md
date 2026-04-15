# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Lê Đình Việt 
**Vai trò:** Inject corruption + so sánh eval + quality report 
**Ngày nộp:** ___________  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- …

**Kết nối với thành viên khác:**

_________________

**Bằng chứng (commit / comment trong code):**

_________________

---

## 2. Một quyết định kỹ thuật (100–150 từ)

> VD: chọn halt vs warn, chiến lược idempotency, cách đo freshness, format quarantine.

_________________

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

> Mô tả triệu chứng → metric/check nào phát hiện → fix.

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

_________________
