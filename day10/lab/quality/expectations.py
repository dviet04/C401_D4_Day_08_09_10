"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from transform.cleaning_rules import ALLOWED_DOC_IDS

@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7: không còn BOM trong chunk_text sau khi đã clean (chứng minh R7 hoạt động)
    bom_in_text = [
        r for r in cleaned_rows if "\ufeff" in (r.get("chunk_text") or "")
    ]
    ok7 = len(bom_in_text) == 0
    results.append(
        ExpectationResult(
            "no_bom_in_chunk_text",
            ok7,
            "halt",
            f"bom_violations={len(bom_in_text)} :: Sau R7 không được còn BOM; FAIL nghĩa là R7 bị bypass.",
        )
    )

    # E8: policy_refund_v4 phải có ít nhất 1 chunk sau clean (alert nếu bị quarantine hết)
    refund_chunks = [r for r in cleaned_rows if r.get("doc_id") == "policy_refund_v4"]
    ok8 = len(refund_chunks) >= 1
    results.append(
        ExpectationResult(
            "refund_doc_coverage_min1",
            ok8,
            "warn",
            f"refund_chunks_in_cleaned={len(refund_chunks)} :: Ít nhất 1 chunk policy_refund_v4 phải còn sau clean.",
        )
    )
    # E9: no duplicate normalized chunk_text
    seen = set()
    dup_count = 0
    for r in cleaned_rows:
        key = " ".join((r.get("chunk_text") or "").strip().split()).lower()
        if key in seen:
            dup_count += 1
        seen.add(key)
    ok9 = dup_count == 0
    results.append(
        ExpectationResult(
            "no_duplicate_chunk_text",
            ok9,
            "halt",
            f"duplicate_chunks={dup_count}",
        )
    )
    # E10: không còn row nào vi phạm min_effective_date theo config (R3 generic)
    stale_policy_rows = []
    for r in cleaned_rows:
        doc_id = r.get("doc_id")
        eff = (r.get("effective_date") or "").strip()
        doc_rules = ALLOWED_DOC_IDS.get(doc_id, {})
        min_eff = doc_rules.get("min_effective_date")

        if min_eff is not None and eff and eff < min_eff:
            stale_policy_rows.append(r)

    ok10 = len(stale_policy_rows) == 0
    results.append(
        ExpectationResult(
            "no_stale_policy_below_min_effective_date",
            ok10,
            "halt",
            f"violations={len(stale_policy_rows)}",
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
