"""
Kiểm tra freshness từ manifest pipeline — hỗ trợ 2 boundary riêng biệt.

Boundary 1 (ingest): `ingest_start_timestamp` — khi pipeline bắt đầu đọc raw data.
Boundary 2 (publish): `embed_publish_timestamp` — khi embed upsert vào Chroma xong.

Distinction bonus: đo 2 boundary giúp phát hiện "pipeline chạy xanh nhưng publish trễ"
(ví dụ: embed mất 3 giờ sau khi ingest xong → freshness_check FAIL dù ingest OK).

Sinh viên mở rộng: đọc watermark DB, so sánh với clock batch, v.v.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        # Cho phép "2026-04-10T08:00:00" không có timezone
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def check_boundary_freshness(
    ts_raw: str | None,
    boundary_name: str,
    sla_hours: float,
    now: datetime,
) -> Dict[str, Any]:
    """
    Kiểm tra freshness cho 1 boundary.
    Trả về dict: {boundary, status, age_hours, sla_hours, ts_raw, reason?}
    """
    dt = parse_iso(str(ts_raw)) if ts_raw else None
    if dt is None:
        return {
            "boundary": boundary_name,
            "status": "WARN",
            "reason": f"no_{boundary_name}_timestamp",
            "ts_raw": ts_raw,
        }
    age_hours = (now - dt).total_seconds() / 3600.0
    result: Dict[str, Any] = {
        "boundary": boundary_name,
        "ts_raw": ts_raw,
        "age_hours": round(age_hours, 3),
        "sla_hours": sla_hours,
    }
    if age_hours <= sla_hours:
        result["status"] = "PASS"
    else:
        result["status"] = "FAIL"
        result["reason"] = "freshness_sla_exceeded"
    return result


def check_manifest_freshness(
    manifest_path: Path,
    *,
    sla_hours: float = 24.0,
    now: datetime | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Trả về ("PASS" | "WARN" | "FAIL", detail dict).

    Kiểm tra 2 boundary nếu có:
      - ingest_start_timestamp  (boundary 1: ingest)
      - embed_publish_timestamp (boundary 2: publish — tighter SLA)
      - fallback: latest_exported_at hoặc run_timestamp (backward compat)

    Worst-case status của 2 boundary được dùng làm status tổng.
    """
    now = now or datetime.now(timezone.utc)
    if not manifest_path.is_file():
        return "FAIL", {"reason": "manifest_missing", "path": str(manifest_path)}

    data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))

    boundaries = []

    # Boundary 1: ingest
    ingest_ts = data.get("ingest_start_timestamp") or data.get("latest_exported_at")
    boundaries.append(
        check_boundary_freshness(ingest_ts, "ingest", sla_hours, now)
    )

    # Boundary 2: publish (embed xong) — SLA chặt hơn ingest 1 giờ
    publish_ts = data.get("embed_publish_timestamp")
    if publish_ts:
        publish_sla = max(1.0, sla_hours - 1.0)  # publish SLA chặt hơn 1h
        boundaries.append(
            check_boundary_freshness(publish_ts, "publish", publish_sla, now)
        )

    # Tổng hợp worst-case status
    statuses = [b["status"] for b in boundaries]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses:
        overall = "WARN"
    else:
        overall = "PASS"

    detail = {
        "overall_status": overall,
        "sla_hours_configured": sla_hours,
        "boundaries": boundaries,
        # backward compat
        "latest_exported_at": ingest_ts,
        "age_hours": boundaries[0].get("age_hours") if boundaries else None,
        "sla_hours": sla_hours,
    }
    return overall, detail
