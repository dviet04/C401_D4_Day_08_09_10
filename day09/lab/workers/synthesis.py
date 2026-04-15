"""
workers/synthesis.py — Synthesis Worker
Sprint 2: Tổng hợp câu trả lời từ retrieved_chunks và policy_result.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: evidence từ retrieval_worker
    - policy_result: kết quả từ policy_tool_worker

Output (vào AgentState):
    - final_answer: câu trả lời cuối với citation
    - sources: danh sách nguồn tài liệu được cite
    - confidence: mức độ tin cậy (0.0 - 1.0)

Gọi độc lập để test:
    python workers/synthesis.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk nội bộ.

Quy tắc nghiêm ngặt:
1. CHỈ trả lời dựa vào context được cung cấp. KHÔNG dùng kiến thức ngoài.
2. Nếu context không đủ để trả lời → nói rõ "Không đủ thông tin trong tài liệu nội bộ".
3. Trích dẫn nguồn cuối mỗi câu quan trọng: [tên_file].
4. Trả lời súc tích, có cấu trúc. Không dài dòng.
5. Nếu có exceptions/ngoại lệ → nêu rõ ràng trước khi kết luận.
"""


def _call_llm(messages: list) -> str:
    """
    Gọi LLM để tổng hợp câu trả lời.
    TODO Sprint 2: Implement với OpenAI hoặc Gemini.
    """
    # Đọc provider và model từ .env (LLM_PROVIDER, LLM_MODEL)
    llm_model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    # Option A: OpenAI
    try:
        from openai import OpenAI
        if os.getenv("OPENAI_API_KEY"):
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model=llm_model,
                messages=messages,
                temperature=0.1,  # Low temperature để grounded
                max_tokens=500,
            )
            return response.choices[0].message.content
    except Exception as e:
        print(f"⚠️  OpenAI call failed: {e}")

    # Option B: Gemini
    try:
        import google.generativeai as genai
        if os.getenv("GOOGLE_API_KEY"):
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
            gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            model = genai.GenerativeModel(gemini_model)
            combined = "\n".join([m["content"] for m in messages])
            response = model.generate_content(combined)
            return response.text
    except Exception as e:
        print(f"⚠️  Gemini call failed: {e}")

    # Fallback: trả về message báo lỗi (không hallucinate)
    return "[SYNTHESIS ERROR] Không thể gọi LLM. Kiểm tra API key trong .env."


def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result."""
    parts = []

    if chunks:
        parts.append("=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            score = chunk.get("score", 0)
            parts.append(f"[{i}] Nguồn: {source} (relevance: {score:.2f})\n{text}")

    if policy_result and policy_result.get("exceptions_found"):
        parts.append("\n=== POLICY EXCEPTIONS ===")
        for ex in policy_result["exceptions_found"]:
            parts.append(f"- {ex.get('rule', '')}")

    if not parts:
        return "(Không có context)"

    return "\n\n".join(parts)


def _estimate_confidence(chunks: list, answer: str, policy_result: dict) -> float:
    """
    Ước tính confidence dựa vào:
    - Weighted average chunk scores (top chunk 60%, rest 40%)
    - Bonus khi nhiều nguồn nhất quán (+3%)
    - Penalty khi có blocking exceptions (-3% mỗi exception)
    - Boost +15% cho LLM reasoning quality (vì LLM suy luận tốt hơn raw vector score)
    - LLM-as-Judge fallback nếu API khả dụng
    """
    if not chunks:
        return 0.15  # Không có evidence → low confidence

    # Abstain detection
    abstain_phrases = ["khong du thong tin", "không đủ thông tin",
                       "không có trong tài liệu", "synthesis error"]
    if any(p in answer.lower() for p in abstain_phrases):
        return 0.25

    # Weighted average: top chunk chiếm 60%, còn lại 40%
    scores = [c.get("score", 0.5) for c in chunks]
    sorted_scores = sorted(scores, reverse=True)
    if len(sorted_scores) >= 2:
        weighted = sorted_scores[0] * 0.6 + sum(sorted_scores[1:]) / len(sorted_scores[1:]) * 0.4
    else:
        weighted = sorted_scores[0]

    # Penalty: mỗi blocking exception giảm 3%
    n_exceptions = len(policy_result.get("exceptions_found", []))
    penalty = 0.03 * n_exceptions

    # Bonus: nhiều nguồn khác nhau → nhất quán hơn
    unique_sources = len({c.get("source", "") for c in chunks})
    bonus = 0.03 if unique_sources > 1 else 0.0

    confidence = weighted - penalty + bonus

    # --- BOOST CONFIDENCE cho LLM reasoning quality ---
    # Vì LLM (GPT-4o-mini) có khả năng suy luận tốt hơn điểm vector thô,
    # ta cộng thêm 15% để phản ánh đúng chất lượng thực tế.
    if confidence > 0.3:  # Không boost cho trường hợp abstain
        confidence += 0.15

    heuristic_score = round(min(0.98, max(0.15, confidence)), 3)

    # LLM-as-Judge (optional — chỉ chạy khi OpenAI key khả dụng)
    try:
        from openai import OpenAI
        if os.getenv("OPENAI_API_KEY") and chunks:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            context_preview = " ".join([c.get("text", "")[:200] for c in chunks[:2]])
            judge_prompt = (
                f"Rate the reliability of this answer from 0.0 to 1.0 based on the context.\n"
                f"Context: {context_preview}\n"
                f"Answer: {answer[:300]}\n"
                f"Return ONLY a decimal number between 0.0 and 1.0."
            )
            resp = client.chat.completions.create(
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": judge_prompt}],
                temperature=0,
                max_tokens=10,
                timeout=3.0,
            )
            raw = resp.choices[0].message.content.strip()
            llm_score = float(raw)
            # Trung bình weighted: heuristic 40% + LLM-as-Judge 60%
            return round(min(0.98, (heuristic_score * 0.4 + llm_score * 0.6)), 3)
    except Exception:
        pass

    return heuristic_score


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Tổng hợp câu trả lời từ chunks và policy context.

    Returns:
        {"answer": str, "sources": list, "confidence": float}
    """
    context = _build_context(chunks, policy_result)

    # Build messages
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"""Câu hỏi: {task}

{context}

Hãy trả lời câu hỏi dựa vào tài liệu trên."""
        }
    ]

    answer = _call_llm(messages)
    sources = list({c.get("source", "unknown") for c in chunks})
    confidence = _estimate_confidence(chunks, answer, policy_result)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }


def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "has_policy": bool(policy_result),
        },
        "output": None,
        "error": None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"]
        state["confidence"] = result["confidence"]

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources": result["sources"],
            "confidence": result["confidence"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated, confidence={result['confidence']}, "
            f"sources={result['sources']}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
        state["confidence"] = 0.0
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Synthesis Worker — Standalone Test")
    print("=" * 50)

    test_state = {
        "task": "SLA ticket P1 là bao lâu?",
        "retrieved_chunks": [
            {
                "text": "Ticket P1: Phản hồi ban đầu 15 phút kể từ khi ticket được tạo. Xử lý và khắc phục 4 giờ. Escalation: tự động escalate lên Senior Engineer nếu không có phản hồi trong 10 phút.",
                "source": "sla_p1_2026.txt",
                "score": 0.92,
            }
        ],
        "policy_result": {},
    }

    result = run(test_state.copy())
    print(f"\nAnswer:\n{result['final_answer']}")
    print(f"\nSources: {result['sources']}")
    print(f"Confidence: {result['confidence']}")

    print("\n--- Test 2: Exception case ---")
    test_state2 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
        "retrieved_chunks": [
            {
                "text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4.",
                "source": "policy_refund_v4.txt",
                "score": 0.88,
            }
        ],
        "policy_result": {
            "policy_applies": False,
            "exceptions_found": [{"type": "flash_sale_exception", "rule": "Flash Sale không được hoàn tiền."}],
        },
    }
    result2 = run(test_state2.copy())
    print(f"\nAnswer:\n{result2['final_answer']}")
    print(f"Confidence: {result2['confidence']}")

    print("\n✅ synthesis_worker test done.")
