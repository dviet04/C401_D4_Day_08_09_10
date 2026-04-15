"""
workers/policy_tool.py — Policy & Tool Worker
Sprint 2+3: Kiểm tra policy dựa vào context, gọi MCP tools khi cần.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: context từ retrieval_worker
    - needs_tool: True nếu supervisor quyết định cần tool call

Output (vào AgentState):
    - policy_result: {"policy_applies", "policy_name", "exceptions_found", "source", "rule"}
    - mcp_tools_used: list of tool calls đã thực hiện
    - worker_io_log: log

Gọi độc lập để test:
    python workers/policy_tool.py
"""
#v1
import json
import os
import sys
from typing import Optional
from urllib import error, request

WORKER_NAME = "policy_tool_worker"


# ─────────────────────────────────────────────
# MCP Client — Sprint 3: Thay bằng real MCP call
# ─────────────────────────────────────────────

# def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
#     """
#     Gọi MCP tool.

#     Sprint 3 TODO: Implement bằng cách import mcp_server hoặc gọi HTTP.

#     Hiện tại: Import trực tiếp từ mcp_server.py (trong-process mock).
#     """
#     from datetime import datetime

#     try:
#         # TODO Sprint 3: Thay bằng real MCP client nếu dùng HTTP server
#         from mcp_server import dispatch_tool
#         result = dispatch_tool(tool_name, tool_input)
#         return {
#             "tool": tool_name,
#             "input": tool_input,
#             "output": result,
#             "error": None,
#             "timestamp": datetime.now().isoformat(),
#         }
#     except Exception as e:
#         return {
#             "tool": tool_name,
#             "input": tool_input,
#             "output": None,
#             "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
#             "timestamp": datetime.now().isoformat(),
#         }

def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
<<<<<<< HEAD
=======
    """
    Gọi MCP tool qua HTTP FastAPI server.

    Không đổi logic worker; chỉ đổi transport layer từ in-process import
    sang HTTP POST để đạt mức Advanced.
    """
>>>>>>> main
    from datetime import datetime
    import requests

    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000")
    endpoint = f"{mcp_server_url.rstrip('/')}/tools/call"
    payload = {"tool": tool_name, "input": tool_input}

    try:
<<<<<<< HEAD
        resp = requests.post(
            f"http://127.0.0.1:8000/tools/{tool_name}",
            json={"input": tool_input},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()

        return {
            "tool": tool_name,
            "input": tool_input,
            "output": payload.get("output"),
            "error": None,
=======
        req = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            result.setdefault("tool", tool_name)
            result.setdefault("input", tool_input)
            result.setdefault("timestamp", datetime.now().isoformat())
            result.setdefault("error", None)
            return result
    except error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"detail": err_body if 'err_body' in locals() else str(e)}
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_HTTP_ERROR", "reason": parsed},
>>>>>>> main
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
            "timestamp": datetime.now().isoformat(),
        }
def _extract_access_level(task: str) -> int | None:
    task_lower = task.lower()
    if "level 3" in task_lower or "admin access" in task_lower:
        return 3
    if "level 2" in task_lower:
        return 2
    if "level 1" in task_lower:
        return 1
    return None


def _extract_requester_role(task: str) -> str:
    task_lower = task.lower()
    if "contractor" in task_lower:
        return "contractor"
    if "employee" in task_lower or "nhân viên" in task_lower:
        return "employee"
    return "unknown"


def _extract_priority(task: str) -> str:
    task_upper = task.upper()
    for p in ["P1", "P2", "P3", "P4"]:
        if p in task_upper:
            return p
    return "P3"
# ─────────────────────────────────────────────
# Policy Analysis Logic
# ─────────────────────────────────────────────

def analyze_policy(task: str, chunks: list) -> dict:
    """
    Phân tích policy dựa trên context chunks.

    TODO Sprint 2: Implement logic này với LLM call hoặc rule-based check.

    Cần xử lý các exceptions:
    - Flash Sale → không được hoàn tiền
    - Digital product / license key / subscription → không được hoàn tiền
    - Sản phẩm đã kích hoạt → không được hoàn tiền
    - Đơn hàng trước 01/02/2026 → áp dụng policy v3 (không có trong docs)

    Returns:
        dict with: policy_applies, policy_name, exceptions_found, source, rule, explanation
    """
    task_lower = task.lower()
    context_text = " ".join([c.get("text", "") for c in chunks]).lower()

    # --- Rule-based exception detection ---
    exceptions_found = []

    # Exception 1: Flash Sale
    if "flash sale" in task_lower or "flash sale" in context_text:
        exceptions_found.append({
            "type": "flash_sale_exception",
            "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 2: Digital product
    if any(kw in task_lower for kw in ["license key", "license", "subscription", "kỹ thuật số"]):
        exceptions_found.append({
            "type": "digital_product_exception",
            "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Exception 3: Activated product
    if any(kw in task_lower for kw in ["đã kích hoạt", "đã đăng ký", "đã sử dụng"]):
        exceptions_found.append({
            "type": "activated_exception",
            "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # Determine policy_applies
    policy_applies = len(exceptions_found) == 0

    # Determine which policy version applies (temporal scoping)
    # TODO: Check nếu đơn hàng trước 01/02/2026 → v3 applies (không có docs, nên flag cho synthesis)
    policy_name = "refund_policy_v4"
    policy_version_note = ""
    if "31/01" in task_lower or "30/01" in task_lower or "trước 01/02" in task_lower:
        policy_version_note = "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách v3 (không có trong tài liệu hiện tại)."

    # TODO Sprint 2: Gọi LLM để phân tích phức tạp hơn
    # Ví dụ:
    # from openai import OpenAI
    # client = OpenAI()
    # response = client.chat.completions.create(
    #     model="gpt-4o-mini",
    #     messages=[
    #         {"role": "system", "content": "Bạn là policy analyst. Dựa vào context, xác định policy áp dụng và các exceptions."},
    #         {"role": "user", "content": f"Task: {task}\n\nContext:\n" + "\n".join([c['text'] for c in chunks])}
    #     ]
    # )
    # analysis = response.choices[0].message.content

    sources = list({c.get("source", "unknown") for c in chunks if c})

    return {
        "policy_applies": policy_applies,
        "policy_name": policy_name,
        "exceptions_found": exceptions_found,
        "source": sources,
        "policy_version_note": policy_version_note,
        "explanation": "Analyzed via rule-based policy check. TODO: upgrade to LLM-based analysis.",
    }


# ─────────────────────────────────────────────
# Worker Entry Point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với policy_result và mcp_tools_used
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "needs_tool": needs_tool,
        },
        "output": None,
        "error": None,
    }

    try:
        # Step 1: Nếu chưa có chunks, gọi MCP search_kb
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")

            if mcp_result.get("output") and mcp_result["output"].get("chunks"):
                chunks = mcp_result["output"]["chunks"]
                state["retrieved_chunks"] = chunks

        # Step 2: Phân tích policy
        policy_result = analyze_policy(task, chunks)
        state["policy_result"] = policy_result

        # Step 3: Nếu cần thêm info từ MCP (e.g., ticket status), gọi get_ticket_info
        # if needs_tool and any(kw in task.lower() for kw in ["ticket", "p1", "jira"]):
        #     mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
        #     state["mcp_tools_used"].append(mcp_result)
        #     state["history"].append(f"[{WORKER_NAME}] called MCP get_ticket_info")
        if needs_tool and any(kw in task.lower() for kw in ["ticket", "p1", "jira"]):
            mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP get_ticket_info")

            if mcp_result.get("output") and not mcp_result.get("error"):
                state["ticket_info"] = mcp_result["output"]
        
            if needs_tool and any(kw in task.lower() for kw in [
                "access", "level 1", "level 2", "level 3", "admin access", "contractor", "phê duyệt"
            ]):
                access_level = _extract_access_level(task)
                requester_role = _extract_requester_role(task)
                is_emergency = any(kw in task.lower() for kw in ["emergency", "khẩn cấp", "p1", "2am"])

                if access_level is not None:
                    mcp_result = _call_mcp_tool(
                        "check_access_permission",
                        {
                            "access_level": access_level,
                            "requester_role": requester_role,
                            "is_emergency": is_emergency,
                        }
                    )
                    state["mcp_tools_used"].append(mcp_result)
                    state["history"].append(f"[{WORKER_NAME}] called MCP check_access_permission")

                    if mcp_result.get("output") and not mcp_result.get("error"):
                        state["access_check"] = mcp_result["output"]
        if needs_tool and any(kw in task.lower() for kw in [
            "tạo ticket", "create ticket", "mở ticket", "log incident", "log ticket"
        ]):
            priority = _extract_priority(task)
            title = task[:80]
            description = f"Auto-created from policy_tool_worker for task: {task}"

            mcp_result = _call_mcp_tool(
                "create_ticket",
                {
                    "priority": priority,
                    "title": title,
                    "description": description,
                }
            )
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP create_ticket")

            if mcp_result.get("output") and not mcp_result.get("error"):
                state["created_ticket"] = mcp_result["output"]

        worker_io["output"] = {
            "policy_applies": policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "policy_name": policy_result.get("policy_name"),
            "sources": policy_result.get("source", []),
            "mcp_calls": len(state["mcp_tools_used"]),
            "mcp_tool_names": [x.get("tool") for x in state.get("mcp_tools_used", [])],
            "has_ticket_info": "ticket_info" in state,
            "has_access_check": "access_check" in state,
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Policy Tool Worker — Standalone Test")
    print("=" * 50)

    test_cases = [
        {
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "retrieved_chunks": [
                {"text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.9}
            ],
        },
        {
            "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
            "retrieved_chunks": [
                {"text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.88}
            ],
        },
        {
            "task": "Khách hàng yêu cầu hoàn tiền trong 5 ngày, sản phẩm lỗi, chưa kích hoạt.",
            "retrieved_chunks": [
                {"text": "Yêu cầu trong 7 ngày làm việc, sản phẩm lỗi nhà sản xuất, chưa dùng.", "source": "policy_refund_v4.txt", "score": 0.85}
            ],
        },
    ]

    for tc in test_cases:
        print(f"\n▶ Task: {tc['task'][:70]}...")
        result = run(tc.copy())
        pr = result.get("policy_result", {})
        print(f"  policy_applies: {pr.get('policy_applies')}")
        if pr.get("exceptions_found"):
            for ex in pr["exceptions_found"]:
                print(f"  exception: {ex['type']} — {ex['rule'][:60]}...")
        print(f"  MCP calls: {len(result.get('mcp_tools_used', []))}")

    print("\n✅ policy_tool_worker test done.")
