"""
eval_trace.py — Trace Evaluation & Comparison
Sprint 4: Chạy pipeline với test questions, phân tích trace, so sánh single vs multi.

Chạy:
    python eval_trace.py                  # Chạy 15 test questions
    python eval_trace.py --grading        # Chạy grading questions (sau 17:00)
    python eval_trace.py --analyze        # Phân tích trace đã có
    python eval_trace.py --compare        # So sánh single vs multi

Outputs:
    artifacts/traces/          — trace của từng câu hỏi
    artifacts/grading_run.jsonl — log câu hỏi chấm điểm
    artifacts/eval_report.json  — báo cáo tổng kết
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Import graph
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from graph import run_graph, save_trace


# ─────────────────────────────────────────────
# 0. Scoring Helpers
# ─────────────────────────────────────────────

def score_answer(result: dict, expected_answer: str, expected_sources: list) -> dict:
    """
    Tính điểm cho một câu trả lời dựa trên:
    - source_recall: tỷ lệ expected sources được retrieve đúng
    - route_correct: supervisor có route đúng expected_route hay không
    - answer_length_ok: câu trả lời có nội dung (không phải lỗi)
    - abstain_correct: nếu expected_sources rỗng, hệ thống có abstain đúng không
    - keyword_overlap: % từ khóa từ expected_answer xuất hiện trong answer

    Returns:
        dict với các score fields
    """
    answer = result.get("final_answer", "")
    retrieved_sources = set(result.get("retrieved_sources", []))
    confidence = result.get("confidence", 0.0)

    # Source recall: số expected sources được retrieve / tổng expected
    if expected_sources:
        # So sánh basename của source để tránh mismatch đường dẫn
        retrieved_basenames = {os.path.basename(s).lower() for s in retrieved_sources}
        expected_basenames = {os.path.basename(s).lower() for s in expected_sources}
        matched = retrieved_basenames & expected_basenames
        source_recall = len(matched) / len(expected_basenames)
    else:
        # Không có expected source → số điểm dựa vào abstain hay không
        source_recall = 1.0  # N/A → cũng tích là 1 để không phạt

    # Abstain check: nếu expected_sources rỗng, expected_answer có từ "không" → abstain là đúng
    is_abstain_expected = (not expected_sources) or ("không tìm thấy" in expected_answer.lower())
    is_abstained = "không đủ thông tin" in answer.lower() or "không tìm thấy" in answer.lower()
    abstain_correct = (is_abstain_expected == is_abstained)

    # Keyword overlap: lấy từ khóa có ý nghĩa (>= 4 ký tự) từ expected_answer
    import re
    expected_keywords = set(re.findall(r'\b\w{4,}\b', expected_answer.lower()))
    answer_keywords = set(re.findall(r'\b\w{4,}\b', answer.lower()))
    keyword_overlap = (
        len(expected_keywords & answer_keywords) / len(expected_keywords)
        if expected_keywords else 0.0
    )

    # Answer có nội dung thực (không phải error message)
    answer_length_ok = len(answer) > 20 and not answer.startswith("SYNTHESIS_ERROR")

    # Tổng hợp score (0.0 – 1.0)
    composite_score = round(
        0.4 * source_recall
        + 0.3 * keyword_overlap
        + 0.2 * float(answer_length_ok)
        + 0.1 * float(abstain_correct),
        3
    )

    return {
        "source_recall": round(source_recall, 3),
        "keyword_overlap": round(keyword_overlap, 3),
        "answer_length_ok": answer_length_ok,
        "abstain_correct": abstain_correct,
        "confidence": confidence,
        "composite_score": composite_score,
    }


# ─────────────────────────────────────────────
# 1. Run Pipeline on Test Questions
# ─────────────────────────────────────────────

def run_test_questions(questions_file: str = "data/test_questions.json") -> list:
    """
    Chạy pipeline với danh sách câu hỏi, lưu trace từng câu.

    Returns:
        list of (question, result) tuples
    """
    with open(questions_file, encoding="utf-8") as f:
        questions = json.load(f)

    print(f"\n📋 Running {len(questions)} test questions from {questions_file}")
    print("=" * 60)

    results = []
    for i, q in enumerate(questions, 1):
        question_text = q["question"]
        q_id = q.get("id", f"q{i:02d}")

        print(f"[{i:02d}/{len(questions)}] {q_id}: {question_text[:65]}...")

        try:
            result = run_graph(question_text)
            result["question_id"] = q_id

            # Save individual trace
            trace_file = save_trace(result, f"artifacts/traces")
            print(f"  ✓ route={result.get('supervisor_route', '?')}, "
                  f"conf={result.get('confidence', 0):.2f}, "
                  f"{result.get('latency_ms', 0)}ms")

            results.append({
                "id": q_id,
                "question": question_text,
                "expected_answer": q.get("expected_answer", ""),
                "expected_sources": q.get("expected_sources", []),
                "difficulty": q.get("difficulty", "unknown"),
                "category": q.get("category", "unknown"),
                "result": result,
            })

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            results.append({
                "id": q_id,
                "question": question_text,
                "error": str(e),
                "result": None,
            })

    print(f"\n✅ Done. {sum(1 for r in results if r.get('result'))} / {len(results)} succeeded.")
    return results


# ─────────────────────────────────────────────
# 2. Run Grading Questions (Sprint 4)
# ─────────────────────────────────────────────

def run_grading_questions(questions_file: str = "data/grading_questions.json") -> str:
    """
    Chạy pipeline với grading questions và lưu JSONL log.
    Dùng cho chấm điểm nhóm (chạy sau khi grading_questions.json được public lúc 17:00).

    Returns:
        path tới grading_run.jsonl
    """
    if not os.path.exists(questions_file):
        print(f"❌ {questions_file} chưa được public (sau 17:00 mới có).")
        return ""

    with open(questions_file, encoding="utf-8") as f:
        questions = json.load(f)

    os.makedirs("artifacts", exist_ok=True)
    output_file = "artifacts/grading_run.jsonl"

    print(f"\n🎯 Running GRADING questions — {len(questions)} câu")
    print(f"   Output → {output_file}")
    print("=" * 60)

    with open(output_file, "w", encoding="utf-8") as out:
        for i, q in enumerate(questions, 1):
            q_id = q.get("id", f"gq{i:02d}")
            question_text = q["question"]
            print(f"[{i:02d}/{len(questions)}] {q_id}: {question_text[:65]}...")

            try:
                result = run_graph(question_text)
                record = {
                    "id": q_id,
                    "question": question_text,
                    "answer": result.get("final_answer", "PIPELINE_ERROR: no answer"),
                    "sources": result.get("retrieved_sources", []),
                    "supervisor_route": result.get("supervisor_route", ""),
                    "route_reason": result.get("route_reason", ""),
                    "workers_called": result.get("workers_called", []),
                    "mcp_tools_used": [t.get("tool") for t in result.get("mcp_tools_used", [])],
                    "confidence": result.get("confidence", 0.0),
                    "hitl_triggered": result.get("hitl_triggered", False),
                    "latency_ms": result.get("latency_ms"),
                    "timestamp": datetime.now().isoformat(),
                }
                print(f"  ✓ route={record['supervisor_route']}, conf={record['confidence']:.2f}")
            except Exception as e:
                record = {
                    "id": q_id,
                    "question": question_text,
                    "answer": f"PIPELINE_ERROR: {e}",
                    "sources": [],
                    "supervisor_route": "error",
                    "route_reason": str(e),
                    "workers_called": [],
                    "mcp_tools_used": [],
                    "confidence": 0.0,
                    "hitl_triggered": False,
                    "latency_ms": None,
                    "timestamp": datetime.now().isoformat(),
                }
                print(f"  ✗ ERROR: {e}")

            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n✅ Grading log saved → {output_file}")
    return output_file


# ─────────────────────────────────────────────
# 3. Analyze Traces
# ─────────────────────────────────────────────

def analyze_traces(traces_dir: str = "artifacts/traces") -> dict:
    """
    Đọc tất cả trace files và tính metrics tổng hợp.

    Metrics:
    - routing_distribution: % câu đi vào mỗi worker
    - avg_confidence: confidence trung bình
    - avg_latency_ms: latency trung bình
    - mcp_usage_rate: % câu có MCP tool call
    - hitl_rate: % câu trigger HITL
    - source_coverage: các tài liệu nào được dùng nhiều nhất

    Returns:
        dict of metrics
    """
    if not os.path.exists(traces_dir):
        print(f"⚠️  {traces_dir} không tồn tại. Chạy run_test_questions() trước.")
        return {}

    trace_files = [f for f in os.listdir(traces_dir) if f.endswith(".json")]
    if not trace_files:
        print(f"⚠️  Không có trace files trong {traces_dir}.")
        return {}

    traces = []
    for fname in trace_files:
        with open(os.path.join(traces_dir, fname), encoding="utf-8") as f:
            traces.append(json.load(f))

    # Compute metrics
    routing_counts = {}
    confidences = []
    latencies = []
    mcp_calls = 0
    hitl_triggers = 0
    source_counts = {}

    for t in traces:
        route = t.get("supervisor_route", "unknown")
        routing_counts[route] = routing_counts.get(route, 0) + 1

        conf = t.get("confidence", 0)
        if conf:
            confidences.append(conf)

        lat = t.get("latency_ms")
        if lat:
            latencies.append(lat)

        if t.get("mcp_tools_used"):
            mcp_calls += 1

        if t.get("hitl_triggered"):
            hitl_triggers += 1

        for src in t.get("retrieved_sources", []):
            source_counts[src] = source_counts.get(src, 0) + 1

    total = len(traces)
    metrics = {
        "total_traces": total,
        "routing_distribution": {k: f"{v}/{total} ({100*v//total}%)" for k, v in routing_counts.items()},
        "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "mcp_usage_rate": f"{mcp_calls}/{total} ({100*mcp_calls//total}%)" if total else "0%",
        "hitl_rate": f"{hitl_triggers}/{total} ({100*hitl_triggers//total}%)" if total else "0%",
        "top_sources": sorted(source_counts.items(), key=lambda x: -x[1])[:5],
    }

    return metrics


# ─────────────────────────────────────────────
# 4. Compare Single vs Multi Agent
# ─────────────────────────────────────────────

def compare_single_vs_multi(
    multi_traces_dir: str = "artifacts/traces",
    day08_results_file: Optional[str] = None,
) -> dict:
    """
    So sánh Day 08 (single agent RAG) vs Day 09 (multi-agent).

    TODO Sprint 4: Điền kết quả thực tế từ Day 08 vào day08_baseline.

    Returns:
        dict của comparison metrics
    """
    multi_metrics = analyze_traces(multi_traces_dir)

    # TODO: Load Day 08 results nếu có
    # Nếu không có, dùng baseline giả lập để format
    day08_baseline = {
        "total_questions": 15,
        "avg_confidence": 0.85,         # TODO: Điền từ Day 08 eval.py (giả lập 0.85)
        "avg_latency_ms": 1200,         # TODO: Điền từ Day 08 (giả lập 1200ms)
        "abstain_rate": "15%",          # TODO: Điền từ Day 08
        "multi_hop_accuracy": "40%",    # TODO: Điền từ Day 08
    }

    if day08_results_file and os.path.exists(day08_results_file):
        try:
            with open(day08_results_file, encoding='utf-8') as f:
                day08_baseline = json.load(f)
        except Exception as e:
            print(f"⚠️  Could not load Day 08 results from {day08_results_file}: {e}")

    comparison = {
        "generated_at": datetime.now().isoformat(),
        "day08_single_agent": day08_baseline,
        "day09_multi_agent": multi_metrics,
        "analysis": {
            "routing_visibility": "Day 09 có route_reason cho từng câu → dễ debug hơn Day 08",
            "latency_delta": (
                f"{multi_metrics.get('avg_latency_ms', 0) - day08_baseline.get('avg_latency_ms', 0)}ms "
                "(TODO: review latency impact due to multi-agent overhead)"
            ),
            # TODO: Điền delta accuracy thực tế từ grading sau khi chạy grading
            # accuracy_delta được tính tự động sau khi có run_test_questions() với expected_answer
            "accuracy_delta": (
                f"Day 09 avg_confidence={multi_metrics.get('avg_confidence', 0):.3f} vs "
                f"Day 08 avg_confidence={day08_baseline.get('avg_confidence', 0):.2f} "
                "(Đựa trên confidence hơn độ; accuracy thực tế cần grading_run.jsonl để so sánh)"
            ),
            "debuggability": "Multi-agent: có thể test từng worker độc lập. Single-agent: không thể.",
            "mcp_benefit": "Day 09 có thể extend capability qua MCP không cần sửa core. Day 08 phải hard-code.",
        },
    }

    return comparison


# ─────────────────────────────────────────────
# 5. Save Eval Report
# ─────────────────────────────────────────────

def save_eval_report(comparison: dict) -> str:
    """Lưu báo cáo eval tổng kết ra file JSON."""
    os.makedirs("artifacts", exist_ok=True)
    output_file = "artifacts/eval_report.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    return output_file


# ─────────────────────────────────────────────
# 6. CLI Entry Point
# ─────────────────────────────────────────────

def print_metrics(metrics: dict):
    """Print metrics đẹp."""
    if not metrics:
        return
    print("\n📊 Trace Analysis:")
    for k, v in metrics.items():
        if isinstance(v, list):
            print(f"  {k}:")
            for item in v:
                print(f"    • {item}")
        elif isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")


def score_test_results(results: list) -> dict:
    """
    Tính điểm tổng hợp trên toàn bộ kết quả test.
    Gọi sau run_test_questions() để có bảng điểm chi tiết.
    """
    scored = []
    for r in results:
        if not r.get("result"):
            continue
        s = score_answer(
            r["result"],
            r.get("expected_answer", ""),
            r.get("expected_sources", []),
        )
        scored.append({
            "id": r["id"],
            "category": r.get("category", "unknown"),
            "difficulty": r.get("difficulty", "unknown"),
            **s,
        })

    if not scored:
        return {}

    avg_composite = round(sum(s["composite_score"] for s in scored) / len(scored), 3)
    avg_source_recall = round(sum(s["source_recall"] for s in scored) / len(scored), 3)
    avg_keyword_overlap = round(sum(s["keyword_overlap"] for s in scored) / len(scored), 3)

    return {
        "total_scored": len(scored),
        "avg_composite_score": avg_composite,
        "avg_source_recall": avg_source_recall,
        "avg_keyword_overlap": avg_keyword_overlap,
        "per_question": scored,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 09 Lab — Trace Evaluation")
    parser.add_argument("--grading", action="store_true", help="Run grading questions")
    parser.add_argument("--analyze", action="store_true", help="Analyze existing traces")
    parser.add_argument("--compare", action="store_true", help="Compare single vs multi")
    parser.add_argument("--score", action="store_true", help="Run test questions và tính điểm chi tiết")
    parser.add_argument("--test-file", default="data/test_questions.json", help="Test questions file")
    parser.add_argument("--day08-file", default=None, help="Day 08 baseline JSON file (tùy chọn)")
    args = parser.parse_args()

    if args.grading:
        # Chạy grading questions
        log_file = run_grading_questions()
        if log_file:
            print(f"\n✅ Grading log: {log_file}")
            print("   Nộp file này trước 18:00!")

    elif args.analyze:
        # Phân tích traces
        metrics = analyze_traces()
        print_metrics(metrics)

    elif args.compare:
        # So sánh single vs multi
        comparison = compare_single_vs_multi(day08_results_file=args.day08_file)
        report_file = save_eval_report(comparison)
        print(f"\n📊 Comparison report saved → {report_file}")
        print("\n=== Day 08 vs Day 09 ===")
        for k, v in comparison.get("analysis", {}).items():
            print(f"  {k}: {v}")

    elif args.score:
        # Chạy test + tính điểm chi tiết từng câu
        results = run_test_questions(args.test_file)
        scores = score_test_results(results)
        print(f"\n🎯 Scoring Results:")
        print(f"  avg_composite_score : {scores.get('avg_composite_score')}")
        print(f"  avg_source_recall   : {scores.get('avg_source_recall')}")
        print(f"  avg_keyword_overlap : {scores.get('avg_keyword_overlap')}")
        print(f"\n  Per-question breakdown:")
        for q in scores.get("per_question", []):
            print(f"  [{q['id']}] {q['category']:20s} composite={q['composite_score']:.2f} "
                  f"src_recall={q['source_recall']:.2f} kw={q['keyword_overlap']:.2f}")
        # Lưu scores ra file
        os.makedirs("artifacts", exist_ok=True)
        scores_file = "artifacts/scores.json"
        with open(scores_file, "w", encoding="utf-8") as f:
            json.dump(scores, f, ensure_ascii=False, indent=2)
        print(f"\n📄 Scores saved → {scores_file}")

    else:
        # Default: chạy test questions
        results = run_test_questions(args.test_file)

        # Phân tích trace
        metrics = analyze_traces()
        print_metrics(metrics)

        # Lưu báo cáo
        comparison = compare_single_vs_multi(day08_results_file=args.day08_file)
        report_file = save_eval_report(comparison)
        print(f"\n📄 Eval report → {report_file}")
        print("\n✅ Sprint 4 complete!")
        print("   Next: Điền docs/ templates và viết reports/")

