# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Hồ Bảo Thư
**Vai trò trong nhóm:** Trace Owner, MCP Owner
**Ngày nộp:** 15/04/2026  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

> Mô tả cụ thể module, worker, contract, hoặc phần trace bạn trực tiếp làm.
> Không chỉ nói "tôi làm Sprint X" — nói rõ file nào, function nào, quyết định nào.
Trong Lab Day 09, tôi phụ trách hai phần chính là **trace/evaluation** và **MCP integration qua HTTP**. Ở phần trace, tôi trực tiếp chỉnh sửa file `eval_trace.py`, đặc biệt là các hàm `run_grading_questions()`, `analyze_traces()`, `compare_single_vs_multi()` và `save_eval_report()`. Mục tiêu của tôi là làm cho pipeline multi-agent không chỉ chạy được mà còn để lại trace đủ rõ để nhóm có thể phân tích routing, confidence, l_tency, MCP usage và HITL rate sau khi chạy grading.  

Song song với đó, tôi chỉnh `workers/policy_tool.py`, cụ thể là hàm `_call_mcp_tool()`, để worker không còn gọi MCP theo kiểu import trực tiếp trong cùng process nữa mà chuyển sang gọi HTTP tới MCP server. Việc này giúp kiến trúc bám sát kiểu client–server hơn. Tôi cũng kiểm tra tương thích với `mcp_server.py`, trong đó server đã expose các endpoint `/health`, `/tools` và `/tools/call`. Công việc của tôi kết nối trực tiếp với supervisor route, policy_tool_worker và phần grading/eval của cả nhóm.

**Module/file tôi chịu trách nhiệm:**  
- `eval_trace.py`  
- `workers/policy_tool.py`  
- Kiểm tra tương thích với `mcp_server.py`

**Bằng chứng:**  
- `commit c6c2baed0e42a7381c0ba0e1eb3dbc9fcdf3ceaa` — `Commit`  
- `commit 40ddb964187cb92e296a20cdeda7a4d70b52764f` — `Update http`

---
**Module/file tôi chịu trách nhiệm:**  
- `eval_trace.py`  
- `workers/policy_tool.py`  
- Kiểm tra tương thích với `mcp_server.py`

**Bằng chứng:**  
- `commit c6c2baed0e42a7381c0ba0e1eb3dbc9fcdf3ceaa` — `Commit`  
- `commit 40ddb964187cb92e296a20cdeda7a4d70b52764f` — `Update http`

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

Quyết định kỹ thuật quan trọng nhất mà tôi trực tiếp thực hiện là **chuyển cơ chế gọi MCP từ direct/in-process sang HTTP-based call** trong `policy_tool_worker`. Trước đó, một cách đơn giản là import thẳng `dispatch_tool()` từ server code rồi gọi nội bộ. Cách này chạy được ở mức demo, nhưng thực chất worker và MCP server vẫn đang dính chặt vào nhau, chưa thể hiện đúng tinh thần external capability của multi-agent orchestration.

Tôi chọn cách gọi HTTP vì nó tách rõ **worker = client** và **MCP server = external service**. Trong `workers/policy_tool.py`, tôi dùng `urllib.request` để gửi `POST` tới endpoint `/tools/call`, với payload dạng JSON gồm `tool` và `input`. Cách này khiến transport layer được chuẩn hóa, dễ test độc lập, và đúng hơn với yêu cầu nâng từ standard lên advanced. Ngoài ra, worker vẫn giữ nguyên business logic; tôi chỉ thay transport layer, nên giảm rủi ro làm vỡ pipeline đang chạy.

Trade-off tôi chấp nhận là gọi HTTP phức tạp hơn gọi hàm trực tiếp, có thêm khả năng phát sinh timeout hoặc HTTP error. Tuy nhiên, đổi lại hệ thống có tính mô-đun tốt hơn, đúng với ý tưởng MCP là mở rộng năng lực agent mà không cần hard-code tool execution vào core worker.

**Bằng chứng từ code:**  
- `policy_tool.py`: `_call_mcp_tool()` gửi request tới `http://127.0.0.1:8000/tools/call`  
- `mcp_server.py`: FastAPI expose `/health`, `/tools`, `/tools/call`

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

Lỗi thực tế tôi sửa là: **policy_tool_worker vẫn gọi MCP theo kiểu trực tiếp thay vì qua HTTP**, nên hệ thống chưa đạt đúng kiến trúc external tool server như yêu cầu của Sprint 3/4. Triệu chứng dễ thấy là worker vẫn hoạt động nếu mọi thứ nằm chung trong một process, nhưng khi tách vai trò server–client rõ hơn thì phần tool orchestration không còn đúng bản chất “MCP over HTTP”.

Root cause nằm ở **transport layer**, không phải logic policy. Cụ thể, vấn đề không nằm ở `analyze_policy()` hay routing của supervisor, mà nằm ở cách worker kết nối tới tool server. Nếu tiếp tục gọi trực tiếp, worker phụ thuộc chặt vào server implementation, làm mất tính độc lập giữa các thành phần.

Cách tôi sửa là viết lại `_call_mcp_tool()` trong `workers/policy_tool.py` để gửi HTTP request tới MCP server bằng `urllib`. Tôi thêm xử lý cho cả trường hợp thành công, `HTTPError` và lỗi kết nối thông thường. Sau khi sửa, worker có thể gọi `search_kb` hoặc `get_ticket_info` qua endpoint `/tools/call`, nhận response JSON chuẩn gồm `tool`, `input`, `output`, `timestamp` và `error` nếu có. Điều này giúp trace ghi lại rõ ràng hơn tool nào đã được gọi, input là gì và MCP có phản hồi ra sao.

**Bằng chứng trước/sau:**  

*Trước khi sửa:* worker chỉ là internal call, chưa tách đúng client–server.  

*Sau khi sửa:* worker gọi HTTP đến MCP server, ví dụ:  
- `POST /tools/call` với payload `{"tool": "search_kb", "input": {...}}`  
- Có thể kiểm tra server qua `/health` và discover tool qua `/tools`

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

Điểm tôi làm tốt nhất là biến phần trace từ chỗ chỉ để chạy thử thành một phần có ích cho việc debug và so sánh hệ thống. Nhờ `eval_trace.py`, nhóm có thể nhìn thấy routing distribution, confidence trung bình, latency, MCP usage rate và top sources, thay vì chỉ nhìn câu trả lời cuối. Tôi cũng làm tốt ở việc sửa transport layer của worker theo hướng đúng kiến trúc hơn, tức là worker gọi MCP server qua HTTP chứ không gọi nội bộ.

Điểm tôi làm chưa tốt là phần này thiên về hạ tầng và quan sát hệ thống hơn là cải thiện trực tiếp answer quality. Nói cách khác, tôi giúp hệ thống “đúng kiến trúc” và “dễ debug” hơn, nhưng chưa tác động mạnh đến độ chính xác như retrieval tuning hoặc synthesis prompt tuning. Tôi cũng còn phụ thuộc vào việc MCP server phải chạy ổn định thì worker mới phát huy hết tác dụng.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Nếu có thêm 2 giờ, tôi sẽ bổ sung **logging chi tiết hơn cho HTTP MCP calls trong trace**, ví dụ tách rõ thời gian gọi tool, status code và lỗi kết nối. Lý do là trace hiện đã có `mcp_tools_used`, nhưng vẫn chưa đủ sâu để phân biệt lỗi do routing, lỗi do worker, hay lỗi do MCP server phản hồi chậm. Nếu bổ sung lớp trace này, việc debug các câu có confidence thấp hoặc tool call thất bại sẽ nhanh và thuyết phục hơn.
_________________

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
