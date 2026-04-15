# Data contract — Lab Day 10

> Canonical definition: `contracts/data_contract.yaml` — file này là phiên bản markdown có giải thích thêm.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|--------------------|----------------|
| **PostgreSQL DB export** (policy, HR) | Batch snapshot CSV mỗi 4h | Sync cron fail → stale; version conflict (policy_v3 vs v4) | `ingest_start_timestamp` age > SLA; `quarantine_records` > 0 with `stale_*` |
| **PDF/TXT tài liệu** (SOP, FAQ) | File hash + logical version check | Content hash thay đổi nhưng version field không đổi → embed nhầm | Hash diff alert; chunk boundary shift |
| **API CRM** (ticket metadata — tương lai) | REST pagination + checkpoint | Rate limit 429; partial page; schema drift | Retry-After monitor; `cleaned_records` drop >20% vs lần trước |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| `chunk_id` | string | **Có** | Hash ổn định: `{doc_id}_{seq}_{sha256[:16]}` — đảm bảo idempotency |
| `doc_id` | string | **Có** | Thuộc `ALLOWED_DOC_IDS` allowlist; phải khớp `canonical_sources` trong contract YAML |
| `chunk_text` | string | **Có** | Sau clean: không BOM, không control chars, ≥ 20 ký tự (R7, R9) |
| `effective_date` | date (YYYY-MM-DD) | **Có** | ISO 8601; parse từ nhiều format (R2); HR < 2026-01-01 bị quarantine |
| `exported_at` | datetime (ISO) | **Có** | Timestamp nguồn dùng cho freshness SLA (boundary ingest) |

---

## 3. Quy tắc quarantine vs drop

| Trường hợp | Hành động | Lý do |
|------------|-----------|-------|
| `doc_id` không thuộc allowlist | **Quarantine** | Kiểm tra catalog; có thể là doc mới cần approve |
| `effective_date` không parse được | **Quarantine** | Cần fix thủ công hoặc liên hệ nguồn |
| HR bản cũ (< 2026-01-01) | **Quarantine** | Version conflict; bản mới đã có |
| `chunk_text` < 20 ký tự | **Quarantine** | Không đủ nội dung nghiệp vụ; cần review |
| Duplicate nội dung | **Quarantine** (giữ bản đầu) | Tránh embedding trùng ảnh hưởng rank |
| `chunk_text` rỗng hoàn toàn | **Quarantine** | Placeholder / lỗi export |

**Ai approve merge lại?** Cleaning/Quality Owner review `artifacts/quarantine/*.csv` định kỳ; merge lại qua chỉnh sửa raw và rerun pipeline.

---

## 4. Phiên bản & canonical

| Document | Source of truth | Version hiện hành | Lưu ý |
|----------|----------------|-------------------|-------|
| Policy refund | `data/docs/policy_refund_v4.txt` | v4 (7 ngày làm việc) | v3 (14 ngày) là stale — bị filter bởi R6 |
| HR leave | `data/docs/hr_leave_policy.txt` | 2026 (12 ngày) | Bản 2025 (10 ngày) bị filter bởi R3 |
| SLA P1 | `data/docs/sla_p1_2026.txt` | 2026 | Ổn định |
| IT FAQ | `data/docs/it_helpdesk_faq.txt` | 2026 | Ổn định |
| Access SOP | `data/docs/access_sop.txt` | 2026 | Ổn định |
