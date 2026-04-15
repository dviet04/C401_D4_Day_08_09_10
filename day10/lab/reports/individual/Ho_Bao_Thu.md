# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Hồ Bảo Thư
**Vai trò:**   Quality Owner, Ingestion Owner, Docs Owner
**Ngày nộp:** 16/04/2026  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- `etl_pipeline.py`
- `quality/expectations.py`
- `transform/cleaning_rules.py`
- `quality/schema.py`
- `docs/data_contract.md`
- `docs/pipeline_architecture.md`
- `quality/schema.py`


**Kết nối với thành viên khác:**

Tôi phụ trách chính các module liên quan đến **ETL pipeline và data quality**, bao gồm `etl_pipeline.py`, `quality/expectations.py`, `quality/schema.py`, và phần tài liệu `docs/data_contract.md`, `docs/pipeline_architecture.md`. 

Ban đầu, Tuấn đã xây dựng pipeline và một số cleaning rules. Tôi tiếp tục chỉnh sửa lại `etl_pipeline.py` để đảm bảo luồng xử lý dữ liệu rõ ràng và dễ mở rộng hơn, đồng thời refactor `transform/cleaning_rules.py`, đặc biệt chuyển logic R3 sang dạng general hóa để tái sử dụng tốt hơn. 

Ngoài ra, tôi bổ sung **Pydantic model** trong `quality/schema.py` để chuẩn hóa cấu trúc dữ liệu và validate ngay từ đầu pipeline. Tôi cũng thêm xử lý cho trường hợp **raw data rỗng**, trong đó pipeline sẽ phát hiện sớm và dừng hoặc cảnh báo để tránh propagate dữ liệu lỗi sang các bước downstream.
_________________

**Bằng chứng (commit / comment trong code):**

- Commit `6508af5` — "Adding bonus pydantic"  
  → Thêm Pydantic model vào `quality/schema.py` để validate dữ liệu. :contentReference[oaicite:1]{index=1}  

- Commit `f19f646` — "Merge branch 'thu'"  
  → Merge toàn bộ thay đổi (ETL pipeline, cleaning rules, expectations) vào `main`. :contentReference[oaicite:2]{index=2}  

_________________

---


## 2. Một quyết định kỹ thuật (100–150 từ)

Một quyết định kỹ thuật quan trọng là thiết kế **cơ chế kiểm soát version và chất lượng dữ liệu theo hướng general thay vì hard-coded**. Thay vì chỉ xử lý riêng rule R3, tôi chuyển sang sử dụng `min_effective_date` để xác định tính hợp lệ của mọi document, giúp pipeline tự động loại bỏ các version lỗi thời một cách nhất quán.

Song song, tôi áp dụng chiến lược **halt vs warn**: pipeline sẽ “halt” khi gặp lỗi nghiêm trọng như schema không hợp lệ hoặc raw data rỗng, nhằm tránh lan truyền dữ liệu sai; trong khi các lỗi nhẹ hơn sẽ được “warn” và đưa vào quarantine để xử lý sau.

Kết hợp với **Pydantic schema validation**, cách tiếp cận này giúp pipeline chuyển từ rule-based sang schema-driven, tăng độ ổn định, khả năng mở rộng và kiểm soát chất lượng dữ liệu.

_________________

---


## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Một anomaly quan trọng là việc hệ thống chỉ xử lý logic versioning thông qua **rule R3 hard-coded**, khiến việc loại bỏ các policy lỗi thời không ổn định và khó mở rộng. Triệu chứng là một số truy vấn vẫn retrieve các document cũ (ví dụ policy hoàn tiền phiên bản trước), dù đã có version mới.

Vấn đề này được phát hiện qua metric `hits_forbidden=yes`, cho thấy retrieval vẫn bị nhiễu bởi dữ liệu lỗi thời. Nguyên nhân là do logic xử lý version chỉ áp dụng cho một số case cụ thể, không tổng quát.

Để khắc phục, tôi refactor R3 thành một cơ chế **generalized version control**, trong đó mỗi document có thể được gán `min_effective_date`, và pipeline sẽ tự động kiểm tra và loại bỏ các version không hợp lệ. Đồng thời, tôi bổ sung xử lý cho trường hợp **raw data rỗng**, trong đó pipeline sẽ cảnh báo hoặc dừng sớm để tránh propagate dữ liệu lỗi sang các bước downstream.

Cách tiếp cận này giúp hệ thống xử lý nhất quán cho mọi loại document, đồng thời tăng độ ổn định và khả năng mở rộng của pipeline.

_________________

---

## 4. Bằng chứng trước / sau (80–120 từ)

Trước khi làm sạch dữ liệu (run_id=inject-bad), truy vấn `q_refund_window` vẫn trả về câu trả lời đúng (`contains_expected=yes`), nhưng đồng thời xuất hiện nội dung lỗi thời (`hits_forbidden=yes`). Điều này cho thấy hệ thống retrieval bị nhiễu bởi các chunk policy cũ (ví dụ 14 ngày hoàn tiền) vẫn lọt vào top-k.

Sau khi chạy pipeline chuẩn (run_id=clean-run), cùng truy vấn cho kết quả `contains_expected=yes` và `hits_forbidden=no`, chứng tỏ các dữ liệu lỗi thời đã được loại bỏ hiệu quả. Các truy vấn khác giữ ổn định, và `q_leave_version` đạt `top1_doc_expected=yes`.

Kết quả cho thấy pipeline cải thiện đáng kể chất lượng retrieval, đồng thời duy trì độ chính xác của câu trả lời.
_________________

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm thời gian, tôi sẽ triển khai **version-aware retrieval**, trong đó mỗi document được gắn metadata version và ưu tiên các phiên bản mới nhất trong quá trình ranking. Điều này giúp giảm phụ thuộc vào cleaning rules thủ công và làm pipeline robust hơn khi dữ liệu liên tục được cập nhật.

_________________
