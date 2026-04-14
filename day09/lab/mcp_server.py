"""
mcp_server.py — Mock MCP Server
Sprint 3: Implement ít nhất 2 MCP tools.

Mô phỏng MCP (Model Context Protocol) interface trong Python.
Agent (MCP client) gọi dispatch_tool() thay vì hard-code từng API.

Tools available:
    1. search_kb(query, top_k)           → tìm kiếm Knowledge Base
    2. get_ticket_info(ticket_id)        → tra cứu thông tin ticket (mock data)
    3. check_access_permission(level, requester_role)  → kiểm tra quyền truy cập
    4. create_ticket(priority, title, description)     → tạo ticket mới (mock)

Sử dụng:
    from mcp_server import dispatch_tool, list_tools

    # Discover available tools
    tools = list_tools()

    # Call a tool
    result = dispatch_tool("search_kb", {"query": "SLA P1", "top_k": 3})

Sprint 3 TODO:
    - Option Standard: Sử dụng file này as-is (mock class)
    - Option Advanced: Implement HTTP server với FastAPI hoặc dùng `mcp` library

Chạy thử:
    python mcp_server.py
"""

import os
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────
# Tool Definitions (Schema Discovery)
# Giống với cách MCP server expose tool list cho client
# ─────────────────────────────────────────────

TOOL_SCHEMAS = {
    "search_kb": {
        "name": "search_kb",
        "description": "Tìm kiếm Knowledge Base nội bộ bằng semantic search. Trả về top-k chunks liên quan nhất.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Câu hỏi hoặc keyword cần tìm"},
                "top_k": {"type": "integer", "description": "Số chunks cần trả về", "default": 3},
            },
            "required": ["query"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "chunks": {"type": "array"},
                "sources": {"type": "array"},
                "total_found": {"type": "integer"},
            },
        },
    },
    "get_ticket_info": {
        "name": "get_ticket_info",
        "description": "Tra cứu thông tin ticket từ hệ thống Jira nội bộ.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "ID ticket (VD: IT-1234, P1-LATEST)"},
            },
            "required": ["ticket_id"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "priority": {"type": "string"},
                "status": {"type": "string"},
                "assignee": {"type": "string"},
                "created_at": {"type": "string"},
                "sla_deadline": {"type": "string"},
            },
        },
    },
    "check_access_permission": {
        "name": "check_access_permission",
        "description": "Kiểm tra điều kiện cấp quyền truy cập theo Access Control SOP.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "access_level": {"type": "integer", "description": "Level cần cấp (1, 2, hoặc 3)"},
                "requester_role": {"type": "string", "description": "Vai trò của người yêu cầu"},
                "is_emergency": {"type": "boolean", "description": "Có phải khẩn cấp không", "default": False},
            },
            "required": ["access_level", "requester_role"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "can_grant": {"type": "boolean"},
                "required_approvers": {"type": "array"},
                "emergency_override": {"type": "boolean"},
                "source": {"type": "string"},
            },
        },
    },
    "create_ticket": {
        "name": "create_ticket",
        "description": "Tạo ticket mới trong hệ thống Jira (MOCK — không tạo thật trong lab).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["priority", "title"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "url": {"type": "string"},
                "created_at": {"type": "string"},
            },
        },
    },
    "get_policy_exceptions": {
        "name": "get_policy_exceptions",
        "description": "Tra cứu danh sách ngoại lệ (exceptions) của một chính sách (policy). VD: refund, access.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy_type": {"type": "string", "description": "Loại policy: 'refund', 'access', 'sla'"},
            },
            "required": ["policy_type"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "policy_type": {"type": "string"},
                "exceptions": {"type": "array"},
                "source": {"type": "string"},
            },
        },
    },
    "search_by_source": {
        "name": "search_by_source",
        "description": "Lọc và truy xuất toàn bộ chunks từ một tài liệu nguồn cụ thể trong Knowledge Base. Dùng khi đã biết rõ tài liệu cần tra cứu.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Tên file nguồn (VD: 'policy/refund-v4.pdf', 'support/sla-p1-2026.pdf')"},
                "keyword": {"type": "string", "description": "(optional) Từ khoá để filter thêm trong tài liệu đó", "default": ""},
            },
            "required": ["source"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "chunks": {"type": "array"},
                "total_found": {"type": "integer"},
            },
        },
    },
    "calculate_sla_deadline": {
        "name": "calculate_sla_deadline",
        "description": "Tính toán SLA deadline dựa trên priority ticket và thời điểm tạo. Trả về thời hạn phản hồi, xử lý, và escalation.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "description": "Priority ticket: P1, P2, P3, P4"},
                "created_at": {"type": "string", "description": "ISO datetime khi tạo ticket (VD: 2026-04-13T22:47:00). Mặc định: now", "default": ""},
            },
            "required": ["priority"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string"},
                "first_response_deadline": {"type": "string"},
                "resolution_deadline": {"type": "string"},
                "escalation_after": {"type": "string"},
                "sla_minutes": {"type": "object"},
            },
        },
    },
    "get_escalation_contacts": {
        "name": "get_escalation_contacts",
        "description": "Tra cứu danh sách liên hệ escalation theo priority ticket. Bao gồm on-call engineer, manager, và kênh thông báo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "description": "Priority: P1, P2, P3"},
            },
            "required": ["priority"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string"},
                "on_call_engineer": {"type": "string"},
                "escalation_manager": {"type": "string"},
                "notification_channels": {"type": "array"},
                "escalation_timeout_minutes": {"type": "integer"},
            },
        },
    },
}


# ─────────────────────────────────────────────
# Tool Implementations
# ─────────────────────────────────────────────

def tool_search_kb(query: str, top_k: int = 3) -> dict:
    """
    Tìm kiếm Knowledge Base bằng semantic search.

    TODO Sprint 3: Kết nối với ChromaDB thực.
    Hiện tại: Delegate sang retrieval worker.
    """
    try:
        # Tái dùng retrieval logic từ workers/retrieval.py
        # Dùng đường dẫn tuyệt đối dựa trên __file__ để đảm bảo import đúng
        # bất kể CWD đang ở đâu (lab/, workers/, v.v.)
        _workers_dir = os.path.dirname(os.path.abspath(__file__))
        if _workers_dir not in sys.path:
            sys.path.insert(0, _workers_dir)
        from workers.retrieval import retrieve_dense
        chunks = retrieve_dense(query, top_k=top_k)
        sources = list({c["source"] for c in chunks})
        return {
            "chunks": chunks,
            "sources": sources,
            "total_found": len(chunks),
        }
    except Exception as e:
        # Fallback: return mock data nếu ChromaDB chưa setup
        return {
            "chunks": [
                {
                    "text": f"[MOCK] Không thể query ChromaDB: {e}. Kết quả giả lập.",
                    "source": "mock_data",
                    "score": 0.5,
                }
            ],
            "sources": ["mock_data"],
            "total_found": 1,
        }


# Mock ticket database
MOCK_TICKETS = {
    "P1-LATEST": {
        "ticket_id": "IT-9847",
        "priority": "P1",
        "title": "API Gateway down — toàn bộ người dùng không đăng nhập được",
        "status": "in_progress",
        "assignee": "nguyen.van.a@company.internal",
        "created_at": "2026-04-13T22:47:00",
        "sla_deadline": "2026-04-14T02:47:00",
        "escalated": True,
        "escalated_to": "senior_engineer_team",
        "notifications_sent": ["slack:#incident-p1", "email:incident@company.internal", "pagerduty:oncall"],
    },
    "IT-1234": {
        "ticket_id": "IT-1234",
        "priority": "P2",
        "title": "Feature login chậm cho một số user",
        "status": "open",
        "assignee": None,
        "created_at": "2026-04-13T09:15:00",
        "sla_deadline": "2026-04-14T09:15:00",
        "escalated": False,
    },
}


def tool_get_ticket_info(ticket_id: str) -> dict:
    """
    Tra cứu thông tin ticket (mock data).
    """
    ticket = MOCK_TICKETS.get(ticket_id.upper())
    if ticket:
        return ticket
    # Không tìm thấy
    return {
        "error": f"Ticket '{ticket_id}' không tìm thấy trong hệ thống.",
        "available_mock_ids": list(MOCK_TICKETS.keys()),
    }


# Mock access control rules
ACCESS_RULES = {
    1: {
        "required_approvers": ["Line Manager"],
        "emergency_can_bypass": False,
        "note": "Standard user access",
    },
    2: {
        "required_approvers": ["Line Manager", "IT Admin"],
        "emergency_can_bypass": True,
        "emergency_bypass_note": "Level 2 có thể cấp tạm thời với approval đồng thời của Line Manager và IT Admin on-call.",
        "note": "Elevated access",
    },
    3: {
        "required_approvers": ["Line Manager", "IT Admin", "IT Security"],
        "emergency_can_bypass": False,
        "note": "Admin access — không có emergency bypass",
    },
}


def tool_check_access_permission(access_level: int, requester_role: str, is_emergency: bool = False) -> dict:
    """
    Kiểm tra điều kiện cấp quyền theo Access Control SOP.
    """
    rule = ACCESS_RULES.get(access_level)
    if not rule:
        return {"error": f"Access level {access_level} không hợp lệ. Levels: 1, 2, 3."}

    can_grant = True
    notes = []

    if is_emergency and rule.get("emergency_can_bypass"):
        notes.append(rule.get("emergency_bypass_note", ""))
        can_grant = True
    elif is_emergency and not rule.get("emergency_can_bypass"):
        notes.append(f"Level {access_level} KHÔNG có emergency bypass. Phải follow quy trình chuẩn.")

    return {
        "access_level": access_level,
        "can_grant": can_grant,
        "required_approvers": rule["required_approvers"],
        "approver_count": len(rule["required_approvers"]),
        "emergency_override": is_emergency and rule.get("emergency_can_bypass", False),
        "notes": notes,
        "source": "access_control_sop.txt",
    }


def tool_create_ticket(priority: str, title: str, description: str = "") -> dict:
    """
    Tạo ticket mới (MOCK — in log, không tạo thật).
    """
    mock_id = f"IT-{9900 + hash(title) % 99}"
    ticket = {
        "ticket_id": mock_id,
        "priority": priority,
        "title": title,
        "description": description[:200],
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "url": f"https://jira.company.internal/browse/{mock_id}",
        "note": "MOCK ticket — không tồn tại trong hệ thống thật",
    }
    print(f"  [MCP create_ticket] MOCK: {mock_id} | {priority} | {title[:50]}")
    return ticket


# Mock policy exception database
MOCK_POLICY_EXCEPTIONS = {
    "refund": {
        "policy_type": "refund",
        "source": "policy/refund-v4.pdf",
        "exceptions": [
            {"id": "flash_sale_exception", "rule": "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4)."},
            {"id": "digital_product_exception", "rule": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3)."},
            {"id": "activated_exception", "rule": "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3)."},
            {"id": "old_order_v3", "rule": "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách v3 (không có trong tài liệu hiện tại)."},
        ],
    },
    "access": {
        "policy_type": "access",
        "source": "it/access-control-sop.md",
        "exceptions": [
            {"id": "contractor_no_admin", "rule": "Contractor không được cấp Level 3 (Admin) Access."},
            {"id": "emergency_level2_ok", "rule": "Level 2 có thể cấp tạm thời trong emergency với approval đồng thời của Line Manager và IT Admin on-call."},
            {"id": "no_emergency_level3", "rule": "Level 3 không có emergency bypass, buộc phải follow quy trình chuẩn."},
        ],
    },
    "sla": {
        "policy_type": "sla",
        "source": "support/sla-p1-2026.pdf",
        "exceptions": [
            {"id": "force_majeure", "rule": "SLA không áp dụng trong trường hợp force majeure (thiên tai, mất điện trung tâm dữ liệu)."},
            {"id": "maintenance_window", "rule": "SLA không tính trong maintenance window đã thông báo trước 48 giờ."},
        ],
    },
}


def tool_get_policy_exceptions(policy_type: str) -> dict:
    """
    Tra cứu danh sách ngoại lệ (exceptions) của một policy.
    Dùng để làm rõ những trường hợp không áp dụng policy tiêu chuẩn.
    """
    policy_type_normalized = policy_type.lower().strip()
    result = MOCK_POLICY_EXCEPTIONS.get(policy_type_normalized)
    if result:
        return result
    # Không tìm thấy policy type
    return {
        "error": f"Policy type '{policy_type}' không tìm thấy.",
        "available_policy_types": list(MOCK_POLICY_EXCEPTIONS.keys()),
    }


def tool_search_by_source(source: str, keyword: str = "") -> dict:
    """
    Lọc chunks từ một tài liệu nguồn cụ thể trong ChromaDB.
    Dùng khi đã biết rõ file cần tra cứu (VD: tất cả nội dung từ refund policy).

    Kết hợp: lấy chunks từ retrieval rồi filter theo source.
    """
    try:
        # Dùng đường dẫn tuyệt đối dựa trên __file__ để đảm bảo import đúng
        _workers_dir = os.path.dirname(os.path.abspath(__file__))
        if _workers_dir not in sys.path:
            sys.path.insert(0, _workers_dir)
        from workers.retrieval import retrieve_dense

        # Query rộng để lấy nhiều chunks, rồi filter theo source
        query = keyword if keyword else source
        all_chunks = retrieve_dense(query, top_k=10)

        # Filter chunks thuộc đúng source
        matched = [c for c in all_chunks if source.lower() in c.get("source", "").lower()]

        # Nếu keyword, filter thêm theo keyword trong text
        if keyword:
            matched = [c for c in matched if keyword.lower() in c.get("text", "").lower()] or matched

        return {
            "source": source,
            "chunks": matched,
            "total_found": len(matched),
        }
    except Exception as e:
        return {
            "error": f"search_by_source failed: {e}",
            "source": source,
            "chunks": [],
            "total_found": 0,
        }


# SLA config theo priority (chuẩn theo sla_p1_2026.txt)
SLA_CONFIG = {
    "P1": {
        "first_response_minutes": 15,
        "resolution_minutes": 240,    # 4 giờ
        "escalation_minutes": 10,     # escalate nếu không phản hồi sau 10 phút
    },
    "P2": {
        "first_response_minutes": 60,
        "resolution_minutes": 480,    # 8 giờ
        "escalation_minutes": 30,
    },
    "P3": {
        "first_response_minutes": 240,
        "resolution_minutes": 1440,   # 24 giờ
        "escalation_minutes": 120,
    },
    "P4": {
        "first_response_minutes": 480,
        "resolution_minutes": 4320,   # 3 ngày
        "escalation_minutes": 480,
    },
}


def tool_calculate_sla_deadline(priority: str, created_at: str = "") -> dict:
    """
    Tính SLA deadline dựa trên priority và thời điểm tạo ticket.
    Trả về: first_response_deadline, resolution_deadline, escalation_after.
    """
    from datetime import timedelta

    priority_upper = priority.upper()
    config = SLA_CONFIG.get(priority_upper)
    if not config:
        return {
            "error": f"Priority '{priority}' không hợp lệ. Hợp lệ: P1, P2, P3, P4.",
            "available_priorities": list(SLA_CONFIG.keys()),
        }

    # Parse hoặc dùng now
    try:
        base_time = datetime.fromisoformat(created_at) if created_at else datetime.now()
    except ValueError:
        base_time = datetime.now()

    first_response = base_time + timedelta(minutes=config["first_response_minutes"])
    resolution = base_time + timedelta(minutes=config["resolution_minutes"])
    escalation = base_time + timedelta(minutes=config["escalation_minutes"])

    return {
        "priority": priority_upper,
        "created_at": base_time.isoformat(),
        "first_response_deadline": first_response.isoformat(),
        "resolution_deadline": resolution.isoformat(),
        "escalation_after": escalation.isoformat(),
        "sla_minutes": {
            "first_response": config["first_response_minutes"],
            "resolution": config["resolution_minutes"],
            "escalation_trigger": config["escalation_minutes"],
        },
        "source": "support/sla-p1-2026.pdf",
    }


# Mock escalation contacts theo priority
ESCALATION_CONTACTS = {
    "P1": {
        "priority": "P1",
        "on_call_engineer": "oncall-primary@company.internal",
        "escalation_manager": "incident-manager@company.internal",
        "notification_channels": [
            "slack:#incident-p1",
            "pagerduty:oncall",
            "email:incident@company.internal",
            "sms:+84-xxx-xxx-xxx",
        ],
        "escalation_timeout_minutes": 10,
        "note": "P1 yêu cầu escalation tự động sau 10 phút không phản hồi.",
        "source": "support/sla-p1-2026.pdf",
    },
    "P2": {
        "priority": "P2",
        "on_call_engineer": "support-team@company.internal",
        "escalation_manager": "support-lead@company.internal",
        "notification_channels": [
            "slack:#support-queue",
            "email:support@company.internal",
        ],
        "escalation_timeout_minutes": 30,
        "note": "P2 escalate lên Support Lead sau 30 phút không xử lý.",
        "source": "support/sla-p1-2026.pdf",
    },
    "P3": {
        "priority": "P3",
        "on_call_engineer": "support-team@company.internal",
        "escalation_manager": "support-lead@company.internal",
        "notification_channels": [
            "slack:#support-queue",
            "email:support@company.internal",
        ],
        "escalation_timeout_minutes": 120,
        "note": "P3 xử lý theo queue bình thường, escalate sau 2 giờ.",
        "source": "support/sla-p1-2026.pdf",
    },
}


def tool_get_escalation_contacts(priority: str) -> dict:
    """
    Tra cứu thông tin liên hệ escalation theo priority.
    Bao gồm on-call engineer, manager, và kênh thông báo tương ứng.
    """
    priority_upper = priority.upper()
    contacts = ESCALATION_CONTACTS.get(priority_upper)
    if contacts:
        return contacts
    # Không tìm thấy priority
    return {
        "error": f"Priority '{priority}' không có cấu hình escalation. Hỗ trợ: P1, P2, P3.",
        "available_priorities": list(ESCALATION_CONTACTS.keys()),
    }


# ─────────────────────────────────────────────
# Dispatch Layer — MCP server interface
# ─────────────────────────────────────────────

TOOL_REGISTRY = {
    "search_kb": tool_search_kb,
    "get_ticket_info": tool_get_ticket_info,
    "check_access_permission": tool_check_access_permission,
    "create_ticket": tool_create_ticket,
    "get_policy_exceptions": tool_get_policy_exceptions,
    "search_by_source": tool_search_by_source,
    "calculate_sla_deadline": tool_calculate_sla_deadline,
    "get_escalation_contacts": tool_get_escalation_contacts,
}


def list_tools() -> list:
    """
    MCP discovery: trả về danh sách tools có sẵn.
    Tương đương với `tools/list` trong MCP protocol.
    """
    return list(TOOL_SCHEMAS.values())


def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    """
    MCP execution: nhận tool_name và input, gọi tool tương ứng.
    Tương đương với `tools/call` trong MCP protocol.

    Args:
        tool_name: tên tool (phải có trong TOOL_REGISTRY)
        tool_input: input dict (phải match với tool's inputSchema)

    Returns:
        Tool output dict, hoặc error dict nếu thất bại
    """
    if tool_name not in TOOL_REGISTRY:
        return {
            "error": f"Tool '{tool_name}' không tồn tại. Available: {list(TOOL_REGISTRY.keys())}"
        }

    tool_fn = TOOL_REGISTRY[tool_name]
    try:
        result = tool_fn(**tool_input)
        return result
    except TypeError as e:
        return {
            "error": f"Invalid input for tool '{tool_name}': {e}",
            "schema": TOOL_SCHEMAS[tool_name]["inputSchema"],
        }
    except Exception as e:
        return {
            "error": f"Tool '{tool_name}' execution failed: {e}",
        }


# ─────────────────────────────────────────────
# Test & Demo
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("MCP Server — Tool Discovery & Test")
    print("=" * 60)

    # 1. Discover tools
    print("\n📋 Available Tools:")
    for tool in list_tools():
        print(f"  • {tool['name']}: {tool['description'][:60]}...")

    # 2. Test search_kb
    print("\n🔍 Test: search_kb")
    result = dispatch_tool("search_kb", {"query": "SLA P1 resolution time", "top_k": 2})
    if result.get("chunks"):
        for c in result["chunks"]:
            print(f"  [{c.get('score', '?')}] {c.get('source')}: {c.get('text', '')[:70]}...")
    else:
        print(f"  Result: {result}")

    # 3. Test get_ticket_info
    print("\n🎫 Test: get_ticket_info")
    ticket = dispatch_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
    print(f"  Ticket: {ticket.get('ticket_id')} | {ticket.get('priority')} | {ticket.get('status')}")
    if ticket.get("notifications_sent"):
        print(f"  Notifications: {ticket['notifications_sent']}")

    # 4. Test check_access_permission
    print("\n🔐 Test: check_access_permission (Level 3, emergency)")
    perm = dispatch_tool("check_access_permission", {
        "access_level": 3,
        "requester_role": "contractor",
        "is_emergency": True,
    })
    print(f"  can_grant: {perm.get('can_grant')}")
    print(f"  required_approvers: {perm.get('required_approvers')}")
    print(f"  emergency_override: {perm.get('emergency_override')}")
    print(f"  notes: {perm.get('notes')}")

    # 5. Test invalid tool
    print("\n❌ Test: invalid tool")
    err = dispatch_tool("nonexistent_tool", {})
    print(f"  Error: {err.get('error')}")

    # 6. Test get_policy_exceptions
    print("\n📜 Test: get_policy_exceptions (refund)")
    excs = dispatch_tool("get_policy_exceptions", {"policy_type": "refund"})
    print(f"  Source: {excs.get('source')}")
    for ex in excs.get("exceptions", [])[:2]:
        print(f"  [{ex['id']}] {ex['rule'][:70]}")

    # 7. Test search_by_source
    print("\n📂 Test: search_by_source (refund-v4.pdf)")
    src_result = dispatch_tool("search_by_source", {"source": "refund", "keyword": "hoàn tiền"})
    print(f"  Total found: {src_result.get('total_found')}")
    for c in src_result.get("chunks", [])[:2]:
        print(f"  [{c.get('score', '?'):.3f}] {c.get('text', '')[:70]}...")

    # 8. Test calculate_sla_deadline
    print("\n⏱️  Test: calculate_sla_deadline (P1, created now)")
    sla = dispatch_tool("calculate_sla_deadline", {"priority": "P1", "created_at": "2026-04-13T22:47:00"})
    print(f"  Priority: {sla.get('priority')}")
    print(f"  First Response: {sla.get('first_response_deadline')}")
    print(f"  Resolution: {sla.get('resolution_deadline')}")
    print(f"  Escalate after: {sla.get('escalation_after')}")

    # 9. Test get_escalation_contacts
    print("\n📞 Test: get_escalation_contacts (P1)")
    contacts = dispatch_tool("get_escalation_contacts", {"priority": "P1"})
    print(f"  On-call: {contacts.get('on_call_engineer')}")
    print(f"  Channels: {contacts.get('notification_channels')}")
    print(f"  Escalate after: {contacts.get('escalation_timeout_minutes')} phút")

    print("\n✅ MCP server test done.")
    # TODO Sprint 3: Implement HTTP server nếu muốn bonus +2.
    # Phương án dùng FastAPI:
    # from fastapi import FastAPI
    # app = FastAPI()
    # @app.get("/tools") → list_tools()
    # @app.post("/tools/{tool_name}") → dispatch_tool(tool_name, body)
    # uvicorn mcp_server:app --host 0.0.0.0 --port 8000

