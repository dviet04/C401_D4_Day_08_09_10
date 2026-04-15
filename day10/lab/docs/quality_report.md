# Quality Report — Lab Day 10

**run_id:** `clean-run` (xem `artifacts/logs/run_clean-run.log`)  
**Ngày:** 2026-04-15  
**Nhóm:** AI in Action — C401 D4

---

## 1. Tóm tắt số liệu

| Chỉ số | Inject Bad (before) | Clean Run (after) | Ghi chú |
|--------|--------------------|--------------------|---------|
| `raw_records` | 11 | 11 | Cùng file raw |
| `cleaned_records` | 5 | 6 | +1 do refund chunk được fix thay vì embed stale |
| `quarantine_records` | 5 | 5 | Dòng stale HR, empty, duplicate, unknown_doc_id |
| Expectation halt? | **YES** (`refund_no_stale_14d_window FAIL`) | NO (tất cả pass) | `--skip-validate` dùng cho inject |
| `embed_upsert count` | 5 (có chunk stale 14 ngày) | 6 (tất cả sạch, 7 ngày) | Prune xóa chunk cũ |
| `embed_prune_removed` | 0 (lần đầu) | 1 (xóa chunk stale từ inject) | Idempotency hoạt động |
| freshness_check (ingest) | FAIL (data cũ 5 ngày) | FAIL (data cũ 5 ngày) | CSV mẫu cố ý — xem FAQ SCORING |
| freshness_check (publish) | FAIL | FAIL | Cùng lý do |

> **Lưu ý freshness FAIL:** `exported_at=2026-04-10T08:00:00` trong data mẫu cách thời điểm thực hành ~5 ngày > SLA 24h. Đây là hành vi cố ý của lab để sinh viên thực hành triage. SLA áp cho "data snapshot" từ nguồn, không phải cho timestamp chạy pipeline.

---

## 2. Before / after retrieval (bắt buộc)

### Câu q_refund_window — cửa sổ hoàn tiền

**Trước (inject-bad run):**
```
question_id,question,top1_doc_id,contains_expected,hits_forbidden,top1_doc_expected
q_refund_window,Khách hàng có bao nhiêu ngày...,policy_refund_v4,yes,YES (14 ngày làm việc),
```
→ `hits_forbidden=yes` → Agent sẽ trả lời sai "14 ngày"

**Sau (clean-run):**
```
question_id,question,top1_doc_id,contains_expected,hits_forbidden,top1_doc_expected
q_refund_window,Khách hàng có bao nhiêu ngày...,policy_refund_v4,yes,no,
```
→ `hits_forbidden=no`, `contains_expected=yes` → Agent trả lời đúng "7 ngày" ✅

### Câu q_leave_version — nghỉ phép HR 2026 (Merit evidence)

**Trước (inject-bad run):**
- Pipeline không filter HR stale khi `--skip-validate` → chunk "10 ngày phép năm" có thể lọt vào index
- `hits_forbidden=yes` (10 ngày phép năm)

**Sau (clean-run):**
- R3 quarantine toàn bộ chunk HR `effective_date < 2026-01-01`
- `contains_expected=yes` (12 ngày), `hits_forbidden=no`, `top1_doc_expected=yes` ✅

---

## 3. Freshness & monitor

**Kết quả `freshness_check`:** FAIL (cả 2 boundary)  
**Lý do:** `exported_at` trong data mẫu là `2026-04-10T08:00:00` — age ≈ 5 ngày > SLA 24h.

**Giải thích SLA:**
- `FRESHNESS_SLA_HOURS=24` trong `.env` — pipeline dự kiến chạy ≥1 lần/ngày.
- Boundary 1 (ingest): khi `load_raw_csv` bắt đầu. Đo `ingest_start_timestamp`.
- Boundary 2 (publish): khi `col.upsert()` hoàn tất. Đo `embed_publish_timestamp`.
- Sự khác biệt 2 boundary = thời gian xử lý (clean + validate + embed). Lab nhỏ → cách nhau <1 giây, nhưng production lớn có thể vài giờ.

**Nếu muốn PASS trên data mẫu:** Đặt `FRESHNESS_SLA_HOURS=9999` trong `.env` hoặc cập nhật `exported_at` trong CSV (có chủ đích để demo).

---

## 4. Corruption inject (Sprint 3)

**Kịch bản inject:**
```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
```

**Những gì xảy ra:**
- `--no-refund-fix`: Chunk "14 ngày làm việc" **không** bị replace → embed vào Chroma với nội dung sai
- `--skip-validate`: Expectation `refund_no_stale_14d_window` FAIL nhưng pipeline tiếp tục embed
- Kết quả: `hits_forbidden=yes` trong eval → Agent có nguy cơ trả lời sai

**Phát hiện:** Log ghi `WARN: expectation failed but --skip-validate` + `expectation[refund_no_stale_14d_window] FAIL (halt)`

**Fix (clean run):**
```bash
python etl_pipeline.py run --run-id clean-run
```
→ `embed_prune_removed=1` xác nhận chunk stale bị xóa khỏi Chroma ✅

---

## 5. Hạn chế & việc chưa làm

- Freshness boundary 2 (publish) hiện đo bằng timestamp `now()` sau embed — chưa lấy từ Chroma collection metadata.
- Chưa có LLM-judge eval (keyword-based đủ cho lab, nhưng không phát hiện paraphrase).
- API CRM source (nguồn 3 trong source map) chỉ mô tả trong docs, chưa implement thật.
- Chưa có auto-alert tích hợp (Slack/email) — là action item Sprint 4 / Day 11.
