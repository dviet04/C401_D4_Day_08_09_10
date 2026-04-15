# Runbook — Lab Day 10: Freshness Breach Incident

**Tình huống tham chiếu:** Agent trả lời "14 ngày" thay vì "7 ngày" cho câu hỏi về cửa sổ hoàn tiền.

---

## Symptom (Triệu chứng)

- User / agent trả lời `hoàn tiền trong 14 ngày làm việc` — sai với policy_refund_v4 hiện hành (7 ngày).
- Eval retrieval: `hits_forbidden=yes` cho câu `q_refund_window`.
- Hoặc: agent dùng policy HR cũ (10 ngày phép) thay vì 12 ngày (2026).

---

## Detection (Phát hiện)

| Metric | Giá trị báo động | Kiểm tra bằng |
|--------|-----------------|---------------|
| `freshness_check` (ingest boundary) | `FAIL` (age_hours > 24) | `python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<run-id>.json` |
| `freshness_check` (publish boundary) | `FAIL` (age_hours > 23) | Cùng lệnh — xem `boundaries[1].status` |
| `expectation[refund_no_stale_14d_window]` | `FAIL` | Log `artifacts/logs/run_<run-id>.log` |
| `expectation[hr_leave_no_stale_10d_annual]` | `FAIL` | Cùng log |
| `eval hits_forbidden=yes` | Bất kỳ câu nào | `python eval_retrieval.py && cat artifacts/eval/before_after_eval.csv` |
| `embed_upsert count` | Giảm đột biến so với run trước | Log line `embed_upsert count=N` |

---

## Diagnosis (Chẩn đoán)

**Thứ tự debug: Freshness → Volume → Schema → Lineage → Model/Prompt**

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|----------------|
| 1 | Kiểm tra `artifacts/manifests/manifest_<run-id>.json` trường `ingest_start_timestamp` | Xác nhận khi nào ingest chạy lần cuối |
| 2 | Xem `embed_publish_timestamp` trong manifest | So sánh với `ingest_start_timestamp` — nếu cách nhau >1h: embed bị trễ |
| 3 | Mở `artifacts/quarantine/*.csv` | Đếm `reason=stale_*` — nhiều → nguồn gốc stale |
| 4 | Chạy `python eval_retrieval.py` | Xem `hits_forbidden=yes` → vector cũ còn trong index |
| 5 | Kiểm tra `embed_prune_removed` trong log | Nếu = 0 sau inject: tức là prune không chạy → run_id lỗi |
| 6 | So sánh `cleaned_records` vs `embed_upsert count` | Phải bằng nhau; chênh → embed bị dừng giữa chừng |

---

## Mitigation (Xử lý tức thời)

**Trong P1: Rollback trước, tìm root cause sau.**

```bash
# Option A: Rerun pipeline chuẩn (nếu data gốc đã đúng)
python etl_pipeline.py run --run-id recovery-$(date +%Y%m%dT%H%M)

# Xác nhận mitigation thành công:
python eval_retrieval.py --out artifacts/eval/post_recovery_eval.csv
# Kiểm tra: hits_forbidden=no cho q_refund_window
```

**Option B:** Nếu không rerun được ngay → thêm banner "Dữ liệu đang bảo trì" trong agent system prompt (guardrail tạm thời).

---

## Prevention (Phòng ngừa)

| # | Hành động | Owner | Deadline |
|---|-----------|-------|----------|
| 1 | Thêm expectation `refund_no_stale_14d_window` — đã có; kiểm tra severity=halt | Quality Owner | Done ✅ |
| 2 | Auto-alert khi `freshness_check=FAIL` (Slack / email) | Monitoring Owner | Sprint 4 |
| 3 | Cron rerun pipeline mỗi 4h đồng bộ SLA | DevOps | Tuần tới |
| 4 | Golden eval trong CI — chạy `eval_retrieval.py` sau mỗi commit | Embed Owner | Sprint 4 |
| 5 | Tách collection staging/production (blue/green) | Embed Owner | Cải tiến Q3 |

**Freshness SLA giải thích:**
- `FRESHNESS_SLA_HOURS=24` — ingest boundary: pipeline chạy tối thiểu 1 lần/ngày.
- Publish boundary SLA = 23h (chặt hơn 1h) — embed phải xong trong 1h sau ingest.
- Data mẫu `exported_at=2026-04-10T08:00:00` → `FAIL` (cũ ~5 ngày) — đây là hành vi **cố ý** của mẫu để sinh viên thực hành triage.

---

*Post-mortem: Điền sau mỗi incident thực tế — không blame người, focus action item pipeline.*
