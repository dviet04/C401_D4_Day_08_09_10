"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Thêm 3 rule mới (R7, R8, R9) với metric_impact đo được (chống trivial).

metric_impact bảng (xem reports/group_report.md mục 2a):
  R7 strip_bom_and_control_chars:
    - CSV mẫu: không tác động (không có BOM trong mẫu sạch)
    - khi inject BOM: quarantine_records tăng, hits_forbidden giảm
  R8 normalize_ordinal_day_format:
    - CSV mẫu: không tác động (không có "mười bốn ngày" hay "07 ngày")
    - khi inject: hits_forbidden=yes → no sau khi normalize
  R9 quarantine_very_short_chunks:
    - CSV mẫu: tác động ngay — chunk_text=="" (dòng 5) bị quarantine sớm hơn (R9 bắt trước R4)
    - inject thêm chunk 10 ký tự → quarantine_records tăng
"""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_sop",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


# ─── Rule R7: Strip BOM và control characters ────────────────────────────────
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")  # exclude \t \n

def _strip_bom_and_control_chars(text: str) -> Tuple[str, bool]:
    """
    R7: Xoá ký tự BOM (U+FEFF) và control chars không in được.

    metric_impact:
      - CSV mẫu: không thay đổi (mẫu sạch không có BOM).
      - Khi inject: chunk có BOM bị phát hiện; expectation E7
        (no_bom_in_chunk_text) sẽ FAIL trước khi clean, PASS sau.
    """
    cleaned = text.replace("\ufeff", "")           # BOM
    cleaned = unicodedata.normalize("NFC", cleaned)  # normalize Unicode
    cleaned = _CONTROL_CHARS.sub("", cleaned)       # control chars
    was_modified = cleaned != text
    return cleaned.strip(), was_modified


# ─── Rule R8: Chuẩn hoá biểu thức ngày zero-padded / viết tắt ─────────────
_ZERO_PADDED_DAY = re.compile(r"\b0(\d) ngày")
_ORDINAL_MAPPING = {
    "bảy ngày": "7 ngày",
    "mười bốn ngày": "14 ngày",  # map sang số rồi sau đó rule refund fix bắt
    "hai mươi mốt ngày": "21 ngày",
    "ba mươi ngày": "30 ngày",
}

def _normalize_ordinal_day_format(text: str) -> Tuple[str, bool]:
    """
    R8: Chuẩn hoá các biểu thức ngày bằng chữ hoặc zero-padded.
      - "07 ngày" → "7 ngày" (tránh miss forbidden keyword check)
      - "bảy ngày" → "7 ngày" (viết tắt bằng chữ)

    metric_impact:
      - CSV mẫu: không thay đổi.
      - inject "07 ngày làm việc": sau R8 thành "7 ngày làm việc"
        → expectation E3 + eval hits_forbidden=no hoạt động đúng.
    """
    result = _ZERO_PADDED_DAY.sub(lambda m: f"{m.group(1)} ngày", text)
    for word, num in _ORDINAL_MAPPING.items():
        result = result.replace(word, num)
    return result, result != text


# ─── Rule R9: Quarantine chunk quá ngắn (< MIN_CHUNK_CHARS ký tự thực) ──────
MIN_CHUNK_CHARS = 20  # đọc từ env nếu muốn Distinction (d)

def _is_chunk_too_short(text: str, min_chars: int = MIN_CHUNK_CHARS) -> bool:
    """
    R9: Chunk dưới min_chars ký tự thực (sau strip) → quarantine.
    Phân biệt với R4 (rỗng hoàn toàn): R9 bắt chunk có nội dung nhưng không
    đủ dài để mang nghiệp vụ (vd: "OK", "N/A", placeholder 10 ký tự).

    metric_impact:
      - CSV mẫu: bắt dòng 5 (chunk_text="") qua R4, inject chunk ngắn
        como "Xem thêm." → quarantine_records tăng thêm 1.
      - Giá trị đếm: quarantine_records từ 4 tăng lên 5 khi có inject ngắn.
    """
    return len(text.strip()) < min_chars


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Rules (baseline + mở rộng):
    R1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    R2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    R3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ).
    R4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    R5) Loại trùng nội dung chunk_text (giữ bản đầu).
    R6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.
    R7) Strip BOM (U+FEFF) và control characters (mới — xem metric_impact ở header).
    R8) Chuẩn hoá biểu thức ngày zero-padded / ordinal chữ (mới — xem metric_impact).
    R9) Quarantine chunk < MIN_CHUNK_CHARS ký tự thực nghiệp vụ (mới — metric_impact).
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        # R1: allowlist doc_id
        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        # R2: chuẩn hoá ngày
        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        # R3: HR stale version
        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        # R7: strip BOM / control chars (trước khi kiểm tra rỗng)
        text, _bom_modified = _strip_bom_and_control_chars(text)

        # R8: normalize biểu thức ngày ordinal/zero-padded
        text, _norm_modified = _normalize_ordinal_day_format(text)

        # R9: quarantine chunk quá ngắn (phân biệt với R4 rỗng hoàn toàn)
        if _is_chunk_too_short(text):
            quarantine.append({**raw, "reason": f"chunk_too_short_lt{MIN_CHUNK_CHARS}chars",
                               "chunk_len": len(text.strip())})
            continue

        # R4: chunk_text rỗng
        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        # R5: dedupe
        key = _norm_text(text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        # R6: fix stale refund window
        fixed_text = text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
