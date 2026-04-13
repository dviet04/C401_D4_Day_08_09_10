"""
eval.py — Sprint 4: Evaluation & Scorecard
==========================================
Mục tiêu Sprint 4 (60 phút):
  - Chạy 10 test questions qua pipeline
  - Chấm điểm theo 4 metrics: Faithfulness, Relevance, Context Recall, Completeness
  - So sánh baseline vs variant
  - Ghi kết quả ra scorecard

Definition of Done Sprint 4:
  ✓ Demo chạy end-to-end (index → retrieve → answer → score)
  ✓ Scorecard trước và sau tuning
  ✓ A/B comparison: baseline vs variant với giải thích vì sao variant tốt hơn

A/B Rule (từ slide):
  Chỉ đổi MỘT biến mỗi lần để biết điều gì thực sự tạo ra cải thiện.
  Đổi đồng thời chunking + hybrid + rerank + prompt = không biết biến nào có tác dụng.
"""

import json
import csv
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
from rag_answer import rag_answer

load_dotenv()

# =============================================================================
# CẤU HÌNH
# =============================================================================

TEST_QUESTIONS_PATH = Path(__file__).parent / "data" / "grading_questions.json"
RESULTS_DIR = Path(__file__).parent / "results"

# Cấu hình baseline (Sprint 2)
BASELINE_CONFIG = {
    "retrieval_mode": "dense",
    "top_k_search": 10,
    "top_k_select": 3,
    "use_rerank": False,
    "label": "baseline_dense",
}

# Cấu hình các variants (Sprint 3)
VARIANTS = [
    # {
    #     "retrieval_mode": "hybrid",
    #     "top_k_search": 10,
    #     "top_k_select": 3,
    #     "use_rerank": False,
    #     "query_transform_strategy": None,
    #     "label": "variant_hybrid",
    # },
    # {
    #     "retrieval_mode": "dense",
    #     "top_k_search": 10,
    #     "top_k_select": 3,
    #     "use_rerank": True,
    #     "query_transform_strategy": None,
    #     "label": "variant_dense_rerank",
    # },
    {
        "retrieval_mode": "dense",
        "top_k_search": 10,
        "top_k_select": 3,
        "use_rerank": False,
        "query_transform_strategy": "expansion",
        "label": "variant_transform_expansion",
    }
]


# =============================================================================
# SCORING FUNCTIONS
# 4 metrics từ slide: Faithfulness, Answer Relevance, Context Recall, Completeness
# =============================================================================
def is_no_data_answer(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    patterns = [
        "không đủ dữ liệu",
        "khong du du lieu",
        "không tìm thấy thông tin",
        "khong tim thay thong tin",
        "insufficient data",
        "not enough data",
        "not found in the provided documents",
        "not found in the provided context",
    ]
    return any(p in t for p in patterns)


def expected_is_no_data_case(expected_answer: str, expected_sources: List[str], category: str = "") -> bool:
    category_l = (category or "").strip().lower()
    if "insufficient" in category_l or "no answer" in category_l or "no-data" in category_l:
        return True

    if expected_sources:
        return False

    t = (expected_answer or "").strip().lower()
    patterns = [
        "không đủ dữ liệu",
        "không tìm thấy thông tin",
        "không có thông tin",
        "insufficient data",
        "not enough data",
        "not found",
    ]
    return any(p in t for p in patterns)


def answer_is_informative_abstention(answer: str) -> bool:
    if not is_no_data_answer(answer):
        return False
    t = (answer or "").strip()
    # câu quá cụt thì vẫn đúng nhưng chưa đủ informative
    return len(t) >= 30
    
def score_faithfulness(
    answer: str,
    chunks_used: List[Dict[str, Any]],
) -> Dict[str, Any]:
    from openai import OpenAI

    if answer.startswith("ERROR") or answer.startswith("PIPELINE"):
        return {"score": 1, "notes": "Lỗi pipeline"}

    if not chunks_used:
        if is_no_data_answer(answer):
            return {"score": 5, "notes": "Không có chunks và model abstain đúng, không bịa thông tin"}
        return {"score": 1, "notes": "Không có chunks nhưng model vẫn đưa ra nội dung cụ thể"}

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"score": None, "notes": "OPENAI_API_KEY không được tìm thấy"}

        client = OpenAI(api_key=api_key)

        chunks_text = "\n\n".join([
            f"[{i+1}] {c.get('text', '')}"
            for i, c in enumerate(chunks_used[:3])
        ])

        prompt = f"""Given these retrieved chunks:

{chunks_text}

And this model answer:

{answer}

Rate the faithfulness on a scale of 1-5:
5 = completely grounded, all information is supported by the chunks
4 = mostly grounded, with at most one minor unsupported detail
3 = partially grounded, some details are not clearly supported
2 = significant information is not supported by the chunks
1 = answer is mostly unsupported or hallucinated

Important:
- If the answer correctly states that there is not enough information in the provided context,
  and the chunks indeed do not contain the requested fact, this should be scored high.
- Do not penalize concise abstention if it avoids unsupported claims.

Output ONLY a JSON object: {{"score": <int 1-5>, "reason": "<brief reason>"}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )

        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)

        return {
            "score": result.get("score", 3),
            "notes": result.get("reason", ""),
        }
    except Exception as e:
        return {"score": None, "notes": f"LLM scoring error: {str(e)[:50]}"}
def score_answer_relevance(
    query: str,
    answer: str,
    expected_answer: str,
    expected_sources: List[str],
    category: str = "",
) -> Dict[str, Any]:
    from openai import OpenAI

    if answer.startswith("ERROR") or answer.startswith("PIPELINE"):
        return {"score": 1, "notes": "Lỗi pipeline"}

    no_data_case = expected_is_no_data_case(expected_answer, expected_sources, category)

    if no_data_case:
        if is_no_data_answer(answer):
            if answer_is_informative_abstention(answer):
                return {"score": 5, "notes": "Abstain đúng và đủ rõ ràng cho người dùng"}
            return {"score": 4, "notes": "Abstain đúng nhưng còn hơi cụt"}
        return {"score": 1, "notes": "Lẽ ra nên abstain nhưng model lại trả lời nội dung cụ thể"}

    if is_no_data_answer(answer) and not no_data_case:
        return {"score": 1, "notes": "Model abstain (không trả lời) trong khi câu hỏi có evidence và expect câu trả lời cụ thể"}

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"score": None, "notes": "OPENAI_API_KEY không được tìm thấy"}

        client = OpenAI(api_key=api_key)

        prompt = f"""Question: {query}

Reference expected answer:
{expected_answer}

Model Answer: {answer}

Rate the relevance to the question on a scale of 1-5:
5 = directly and completely answers the question
4 = answers correctly but misses minor details
3 = relevant but doesn't fully address the core question
2 = partially off-topic
1 = does not answer the question

Important:
- The reference expected answer describes the intended outcome, not the only acceptable wording.
- Do not require wording overlap.
- If the expected answer implies insufficient information, then a correct abstention would be relevant.

Output ONLY a JSON object: {{"score": <int 1-5>, "reason": "<brief reason>"}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )

        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)

        return {
            "score": result.get("score", 3),
            "notes": result.get("reason", ""),
        }
    except Exception as e:
        return {"score": None, "notes": f"LLM scoring error: {str(e)[:50]}"}

def score_context_recall(
    chunks_used: List[Dict[str, Any]],
    expected_sources: List[str],
    expected_answer: str = "",
    category: str = "",
) -> Dict[str, Any]:
    no_data_case = expected_is_no_data_case(expected_answer, expected_sources, category)

    if not expected_sources:
        if no_data_case and not chunks_used:
            return {
                "score": 5,
                "recall": 1.0,
                "found": 0,
                "missing": [],
                "notes": "No expected sources and no retrieved chunks: correct no-data retrieval behavior",
            }
        if no_data_case:
            return {
                "score": 4,
                "recall": 1.0,
                "found": 0,
                "missing": [],
                "notes": "No expected sources; retrieved chunks exist but no source was required",
            }
        return {"score": None, "recall": None, "notes": "No expected sources"}

    retrieved_sources = {
        c.get("metadata", {}).get("source", "")
        for c in chunks_used
    }

    found = 0
    missing = []
    for expected in expected_sources:
        expected_name = expected.split("/")[-1].replace(".pdf", "").replace(".md", "")
        matched = any(expected_name.lower() in r.lower() for r in retrieved_sources)
        if matched:
            found += 1
        else:
            missing.append(expected)

    recall = found / len(expected_sources)

    score = max(1, round(recall * 5))
    return {
        "score": score,
        "recall": recall,
        "found": found,
        "missing": missing,
        "notes": f"Retrieved: {found}/{len(expected_sources)} expected sources" +
                 (f". Missing: {missing}" if missing else ""),
    }

def score_completeness(
    query: str,
    answer: str,
    expected_answer: str,
    expected_sources: List[str],
    category: str = "",
) -> Dict[str, Any]:
    from openai import OpenAI

    if answer.startswith("ERROR"):
        return {"score": None, "notes": "Lỗi pipeline"}

    no_data_case = expected_is_no_data_case(expected_answer, expected_sources, category)

    if no_data_case:
        if is_no_data_answer(answer):
            if answer_is_informative_abstention(answer):
                return {"score": 5, "notes": "Đáp án đầy đủ cho no-data case"}
            return {"score": 4, "notes": "Đúng ý nhưng còn ngắn, chưa giải thích đủ"}
        return {"score": 1, "notes": "Expected no-data behavior nhưng model lại trả lời cụ thể"}

    if is_no_data_answer(answer) and not no_data_case:
        return {"score": 1, "notes": "Model abstain (không trả lời) nên completeness = 1"}

    if not expected_answer:
        return {"score": None, "notes": "Không có expected_answer"}

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"score": None, "notes": "OPENAI_API_KEY không được tìm thấy"}

        client = OpenAI(api_key=api_key)

        prompt = f"""
Expected Answer (reference intent):
{expected_answer}

Model Answer:
{answer}

Compare the model answer with the expected answer.

IMPORTANT:
- Identify ALL key facts and conditions in the expected answer.
- Check whether the model answer includes EACH of them.
- Missing ANY important condition (e.g., approval requirement, constraints, exceptions) MUST reduce the score.

Rate completeness on a scale of 1-5:
5 = all key facts and conditions are present
4 = missing a minor detail
3 = missing one important detail
2 = missing multiple important details
1 = missing most key content

Output ONLY JSON:
{{"score": <int>, "missing": "<what is missing>"}}
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
        )

        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)

        return {
            "score": result.get("score", 3),
            "notes": result.get("missing", ""),
        }
    except Exception as e:
        return {"score": None, "notes": f"LLM scoring error: {str(e)[:50]}"}

# =============================================================================
# SCORECARD RUNNER
# =============================================================================

def run_scorecard(
    config: Dict[str, Any],
    test_questions: Optional[List[Dict]] = None,
    verbose: bool = True,
) -> List[Dict[str, Any]]:
    """
    Chạy toàn bộ test questions qua pipeline và chấm điểm.

    Args:
        config: Pipeline config (retrieval_mode, top_k, use_rerank, ...)
        test_questions: List câu hỏi (load từ JSON nếu None)
        verbose: In kết quả từng câu

    Returns:
        List scorecard results, mỗi item là một row

    TODO Sprint 4:
    1. Load test_questions từ data/test_questions.json
    2. Với mỗi câu hỏi:
       a. Gọi rag_answer() với config tương ứng
       b. Chấm 4 metrics
       c. Lưu kết quả
    3. Tính average scores
    4. In bảng kết quả
    """
    if test_questions is None:
        with open(TEST_QUESTIONS_PATH, "r", encoding="utf-8") as f:
            test_questions = json.load(f)

    results = []
    label = config.get("label", "unnamed")

    print(f"\n{'='*70}")
    print(f"Chạy scorecard: {label}")
    print(f"Config: {config}")
    print('='*70)

    for q in test_questions:
        question_id = q["id"]
        query = q["question"]
        expected_answer = q.get("expected_answer", "")
        expected_sources = q.get("expected_sources", [])
        category = q.get("category", "")

        if verbose:
            print(f"\n[{question_id}] {query}")

        # --- Gọi pipeline ---
        try:
            result = rag_answer(
                query=query,
                retrieval_mode=config.get("retrieval_mode", "dense"),
                top_k_search=config.get("top_k_search", 10),
                top_k_select=config.get("top_k_select", 3),
                use_rerank=config.get("use_rerank", False),
                query_transform_strategy=config.get("query_transform_strategy"),
                verbose=False,
            )
            answer = result["answer"]
            chunks_used = result["chunks_used"]

        except NotImplementedError:
            answer = "PIPELINE_NOT_IMPLEMENTED"
            chunks_used = []
        except Exception as e:
            answer = f"ERROR: {str(e)[:100]}"
            chunks_used = []

        # --- Chấm điểm ---
        faith = score_faithfulness(answer, chunks_used)
        relevance = score_answer_relevance(
            query=query,
            answer=answer,
            expected_answer=expected_answer,
            expected_sources=expected_sources,
            category=category,
        )
        recall = score_context_recall(
            chunks_used=chunks_used,
            expected_sources=expected_sources,
            expected_answer=expected_answer,
            category=category,
        )
        complete = score_completeness(
            query=query,
            answer=answer,
            expected_answer=expected_answer,
            expected_sources=expected_sources,
            category=category,
        )

        row = {
            "id": question_id,
            "category": category,
            "query": query,
            "answer": answer,
            "expected_answer": expected_answer,
            "faithfulness": faith["score"],
            "faithfulness_notes": faith["notes"],
            "relevance": relevance["score"],
            "relevance_notes": relevance["notes"],
            "context_recall": recall["score"],
            "context_recall_notes": recall["notes"],
            "completeness": complete["score"],
            "completeness_notes": complete["notes"],
            "config_label": label,
        }
        results.append(row)

        if verbose:
            print(f"  Answer: {answer}...")
            print(f"  Faithful: {faith['score']} | Relevant: {relevance['score']} | "
                  f"Recall: {recall['score']} | Complete: {complete['score']}")

    # Tính averages (bỏ qua None)
    for metric in ["faithfulness", "relevance", "context_recall", "completeness"]:
        scores = [r[metric] for r in results if r[metric] is not None]
        avg = sum(scores) / len(scores) if scores else None
        print(f"\nAverage {metric}: {avg:.2f}" if avg else f"\nAverage {metric}: N/A (chưa chấm)")

    return results


# =============================================================================
# A/B COMPARISON
# =============================================================================

def compare_ab(
    baseline_results: List[Dict],
    variant_results: List[Dict],
    output_csv: Optional[str] = None,
) -> None:
    """
    So sánh baseline vs variant theo từng câu hỏi và tổng thể.

    TODO Sprint 4:
    Điền vào bảng sau để trình bày trong báo cáo:

    | Metric          | Baseline | Variant | Delta |
    |-----------------|----------|---------|-------|
    | Faithfulness    |   ?/5    |   ?/5   |  +/?  |
    | Answer Relevance|   ?/5    |   ?/5   |  +/?  |
    | Context Recall  |   ?/5    |   ?/5   |  +/?  |
    | Completeness    |   ?/5    |   ?/5   |  +/?  |

    Câu hỏi cần trả lời:
    - Variant tốt hơn baseline ở câu nào? Vì sao?
    - Biến nào (chunking / hybrid / rerank) đóng góp nhiều nhất?
    - Có câu nào variant lại kém hơn baseline không? Tại sao?
    """
    metrics = ["faithfulness", "relevance", "context_recall", "completeness"]

    print(f"\n{'='*70}")
    print("A/B Comparison: Baseline vs Variant")
    print('='*70)
    print(f"{'Metric':<20} {'Baseline':>10} {'Variant':>10} {'Delta':>8}")
    print("-" * 55)

    for metric in metrics:
        b_scores = [r[metric] for r in baseline_results if r[metric] is not None]
        v_scores = [r[metric] for r in variant_results if r[metric] is not None]

        b_avg = sum(b_scores) / len(b_scores) if b_scores else None
        v_avg = sum(v_scores) / len(v_scores) if v_scores else None
        delta = (v_avg - b_avg) if (b_avg and v_avg) else None

        b_str = f"{b_avg:.2f}" if b_avg else "N/A"
        v_str = f"{v_avg:.2f}" if v_avg else "N/A"
        d_str = f"{delta:+.2f}" if delta else "N/A"

        print(f"{metric:<20} {b_str:>10} {v_str:>10} {d_str:>8}")

    # Per-question comparison
    print(f"\n{'Câu':<6} {'Baseline F/R/Rc/C':<22} {'Variant F/R/Rc/C':<22} {'Better?':<10}")
    print("-" * 65)

    b_by_id = {r["id"]: r for r in baseline_results}
    for v_row in variant_results:
        qid = v_row["id"]
        b_row = b_by_id.get(qid, {})

        b_scores_str = "/".join([
            str(b_row.get(m, "?")) for m in metrics
        ])
        v_scores_str = "/".join([
            str(v_row.get(m, "?")) for m in metrics
        ])

        # So sánh đơn giản
        b_total = sum(b_row.get(m, 0) or 0 for m in metrics)
        v_total = sum(v_row.get(m, 0) or 0 for m in metrics)
        better = "Variant" if v_total > b_total else ("Baseline" if b_total > v_total else "Tie")

        print(f"{qid:<6} {b_scores_str:<22} {v_scores_str:<22} {better:<10}")

    # Export to CSV
    if output_csv:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = RESULTS_DIR / output_csv
        combined = baseline_results + variant_results
        if combined:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=combined[0].keys())
                writer.writeheader()
                writer.writerows(combined)
            print(f"\nKết quả đã lưu vào: {csv_path}")


# =============================================================================
# REPORT GENERATOR
# =============================================================================

def generate_scorecard_summary(results: List[Dict], label: str) -> str:
    """
    Tạo báo cáo tóm tắt scorecard dạng markdown.

    TODO Sprint 4: Cập nhật template này theo kết quả thực tế của nhóm.
    """
    metrics = ["faithfulness", "relevance", "context_recall", "completeness"]
    averages = {}
    for metric in metrics:
        scores = [r[metric] for r in results if r[metric] is not None]
        averages[metric] = sum(scores) / len(scores) if scores else None

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    md = f"""# Scorecard: {label}
Generated: {timestamp}

## Summary

| Metric | Average Score |
|--------|--------------|
"""
    for metric, avg in averages.items():
        avg_str = f"{avg:.2f}/5" if avg else "N/A"
        md += f"| {metric.replace('_', ' ').title()} | {avg_str} |\n"

    md += "\n## Per-Question Results\n\n"
    md += "| ID | Category | Faithful | Relevant | Recall | Complete | Notes |\n"
    md += "|----|----------|----------|----------|--------|----------|-------|\n"

    for r in results:
        md += (f"| {r['id']} | {r['category']} | {r.get('faithfulness', 'N/A')} | "
               f"{r.get('relevance', 'N/A')} | {r.get('context_recall', 'N/A')} | "
               f"{r.get('completeness', 'N/A')} | {r.get('faithfulness_notes', '')[:50]} |\n")

    return md


# =============================================================================
# MAIN — Chạy evaluation
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 4: Evaluation & Scorecard")
    print("=" * 60)

    # Kiểm tra test questions
    print(f"\nLoading test questions from: {TEST_QUESTIONS_PATH}")
    try:
        with open(TEST_QUESTIONS_PATH, "r", encoding="utf-8") as f:
            test_questions = json.load(f)
        print(f"Tìm thấy {len(test_questions)} câu hỏi")

        # In preview
        for q in test_questions[:3]:
            print(f"  [{q['id']}] {q['question']} ({q['category']})")
        print("  ...")

    except FileNotFoundError:
        print("Không tìm thấy file test_questions.json!")
        test_questions = []

    # --- Chạy Baseline ---
    print("\n--- Chạy Baseline ---")
    print("Lưu ý: Cần hoàn thành Sprint 2 trước khi chạy scorecard!")
    try:
        baseline_results = run_scorecard(
            config=BASELINE_CONFIG,
            test_questions=test_questions,
            verbose=True,
        )

        # Save scorecard
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        baseline_md = generate_scorecard_summary(baseline_results, "baseline_dense")
        scorecard_path = RESULTS_DIR / "scorecard_baseline.md"
        scorecard_path.write_text(baseline_md, encoding="utf-8")
        print(f"\nScorecard lưu tại: {scorecard_path}")

    except NotImplementedError:
        print("Pipeline chưa implement. Hoàn thành Sprint 2 trước.")
        baseline_results = []

    # --- Chạy Các Variant (sau khi Sprint 3 hoàn thành) ---
    print("\n--- Chạy Các Variant ---")
    all_variant_results = {}
    for v_config in VARIANTS:
        try:
            v_results = run_scorecard(
                config=v_config,
                test_questions=test_questions,
                verbose=True,
            )
            v_md = generate_scorecard_summary(v_results, v_config["label"])
            (RESULTS_DIR / f"scorecard_{v_config['label']}.md").write_text(v_md, encoding="utf-8")
            all_variant_results[v_config["label"]] = v_results
        except Exception as e:
            print(f"Lỗi chạy variant {v_config['label']}: {e}")
            all_variant_results[v_config["label"]] = []

    # --- A/B Comparison ---
    if baseline_results:
        for label, v_results in all_variant_results.items():
            if v_results:
                compare_ab(
                    baseline_results,
                    v_results,
                    output_csv=f"ab_comparison_{label}.csv"
                )

    print("\n\nViệc cần làm Sprint 4:")
    print("  1. Hoàn thành Sprint 2 + 3 trước")
    print("  2. Chấm điểm thủ công hoặc implement LLM-as-Judge trong score_* functions")
    print("  3. Chạy run_scorecard(BASELINE_CONFIG)")
    print("  4. Chạy run_scorecard(VARIANT_CONFIG)")
    print("  5. Gọi compare_ab() để thấy delta")
    print("  6. Cập nhật docs/tuning-log.md với kết quả và nhận xét")
