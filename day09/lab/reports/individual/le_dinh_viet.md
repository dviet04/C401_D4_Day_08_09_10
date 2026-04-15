# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Lê Đình Việt 
**Vai trò trong nhóm:** Supervisor Owner / Worker Owner / MCP Owner
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

Tôi phụ trách xây dựng hai module chính trong hệ thống gồm retrieval_worker (workers/retrieval.py) và synthesis_worker (workers/synthesis.py), tương ứng với hai thành phần quan trọng trong pipeline RAG: truy xuất dữ liệu và tổng hợp câu trả lời. Ở retrieval_worker, tôi implement retrieve_dense, _get_embedding_fn, _get_collection và run để thực hiện semantic search trên ChromaDB và chuẩn hóa output theo worker contract. Ở synthesis_worker, tôi thiết kế pipeline tổng hợp gồm _build_context, _call_llm, _estimate_confidence và synthesize nhằm tạo câu trả lời có dẫn nguồn và kiểm soát hallucination. Ngoài ra, tôi cũng có tham gia phát triển file mcp_server.py (Sprint 3), tuy nhiên phiên bản cuối cùng sử dụng trong hệ thống được thay bằng bản của bạn Tuấn do đạt hiệu năng tốt hơn.

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/retrieval.py, workers/synthesis.py `
- Functions tôi implement: `_get_embedding_fn, _get_collection, retrieve_dense, _build_context, _call_llm, _estimate_confidence, synthesize`

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Chúng tôi thảo luận và phân chia công việc cho nhau. Tuấn làm phần sprint 1, sau đó tôi dựa vào đó để xây dựng retrieval và synthesis trong khi Tuấn làm policy_tool. Sprint 3 chúng tôi làm cùng nhau và Tuấn có kết quả tốt hơn nên lấy spint3 của tuấn
_________________

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
commit a725279804f2c20d3903c20ae765157bfe279424 (HEAD -> viet_day9, origin/viet_day9)
Author: dviet04 <ledinhviet2507@gmail.com>
Date:   Tue Apr 14 16:49:38 2026 +0700

    update mcp_server and eval_trace

commit 2a42c637302885549f53530e7fd4e8f5627f1609 (HEAD -> main, origin/main)
Author: dviet04 <ledinhviet2507@gmail.com>
Date:   Tue Apr 14 16:06:17 2026 +0700

    update systhesis v2

commit d52ebdf0cd36cbdb257c7ffb89938578b6f28489
Author: dviet04 <ledinhviet2507@gmail.com>
Date:   Tue Apr 14 15:32:27 2026 +0700

    update retrieval v2

commit c032bacd40ecff3271785beed149d3f0e596b8e8
Author: dviet04 <ledinhviet2507@gmail.com>
Date:   Tue Apr 14 12:36:52 2026 +0700

    update eval
_________________

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
Sử dụng dense retrieval (embedding + vector search với ChromaDB).
> - Các lựa chọn thay thế là gì? 
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:** Sử dụng dense retrieval (embedding + vector search với ChromaDB) thay vì keyword-based (BM25) cho retrieval_worker

**Lý do:**
Tôi chọn dense retrieval vì hệ thống cần xử lý các câu hỏi tự nhiên (natural language) trong bối cảnh IT Helpdesk, nơi người dùng có thể diễn đạt linh hoạt. Dense retrieval giúp bắt được semantic similarity, thay vì chỉ dựa vào từ khóa trùng khớp.
_________________

**Trade-off đã chấp nhận:**
- Tốn tài nguyên hơn (embedding, vector DB)
- Cần setup phức tạp hơn BM25
- Đổi lại: hiểu ngữ nghĩa tốt hơn, cải thiện chất lượng RAG rõ rệt
_________________

**Bằng chứng từ trace/code:**

```
[PASTE ĐOẠN CODE HOẶC TRACE RELEVANT VÀO ĐÂY]
def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    """
    Dense retrieval: embed query → query ChromaDB → trả về top_k chunks.

    TODO Sprint 2: Implement phần này.
    - Dùng _get_embedding_fn() để embed query
    - Query collection với n_results=top_k
    - Format result thành list of dict

    Returns:
        list of {"text": str, "source": str, "score": float, "metadata": dict}
    """
    # TODO: Implement dense retrieval
    embed = _get_embedding_fn()
    query_embedding = embed(query)

    try:
        collection = _get_collection()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"]
        )

        chunks = []
        for i, (doc, dist, meta) in enumerate(zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0]
        )):
            chunks.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "score": round(1 - dist, 4),  # cosine similarity
                "metadata": meta,
            })
        return chunks

    except Exception as e:
        print(f"⚠️  ChromaDB query failed: {e}")
        # Fallback: return empty (abstain)
        return []
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:** Trả về kết quả truy vấn rỗng (0 chunks retrieved) do sai đường dẫn file Cấu hình ChromaDB khi đấu nối multi-agent.

**Symptom (pipeline làm gì sai?):**
Khi chạy nội bộ trong file `retrieval.py` thì có kết quả chunk bình thường, nhưng khi chạy pipeline tổng qua `graph.py` hoặc CLI `eval_trace.py` ở thư mục rút gọn, `retrieval_worker` hoàn toàn không kiếm được vector nào. Tỉ lệ abstain (từ chối trả lời do thiếu context) tǎng vô lý, confidence ở mức tối thiểu 0.1 dù source chắc chắn có thông tin.

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
Lỗi nằm ở *worker logic* của `retrieval.py` bên trong hàm `_get_collection()`. Hệ thống config ChromaDB theo đường dẫn relative `path = "../../day08/lab/chroma_db"`. Thuộc tính relative path dựa vào Context Working Directory (CWD) thực thi của Terminal. Cho nên, khi terminal chạy run từ root directory (`day09/lab`), path tương đối bị sai lệch gốc dẫn đến Chroma tự động khởi tạo kết nối rỗng (Empty SQLite vector database) thay vì mở repo index có sẵn.

**Cách sửa:**
Sửa `retrieval.py`, neo đường dẫn tĩnh tuyệt đối dựa vào chính location của file code bằng `__file__`. Thay thế code cũ thành `db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../day08/lab/chroma_db"))` để truy cập db day08 chính xác mà không phụ thuộc lệnh CWD nằm ở đâu.

**Bằng chứng trước/sau:**

*Trước khi sửa:*
```json
// Log trace hiển thị fail 
"retrieved_sources": [],
"confidence": 0.1,
"final_answer": "Hiện tại hệ thống không đủ dữ liệu để trả lời câu hỏi này."
```

*Sau khi sửa:*
```json
// Log truy xuất đúng policy
"retrieved_sources": [".../day08/lab/data/raw/policy/refund-v4.pdf"],
"confidence": 0.85,
"final_answer": "Khách hàng có thể yêu cầu hoàn tiền trong vòng 7 ngày làm việc..."
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**
Tôi làm tốt ở việc thiết kế và implement hai module core của pipeline RAG là retrieval và synthesis, đảm bảo chúng hoạt động ổn định, có logging rõ ràng và tuân thủ worker contract. Đặc biệt, phần synthesis có kiểm soát hallucination tốt (prompt chặt, có citation, có confidence), giúp output đáng tin cậy.
_________________

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
Tôi chưa tối ưu chất lượng retrieval (chưa có reranking hoặc filtering tốt), dẫn đến một số câu hỏi phức tạp có confidence chưa cao. Ngoài ra, ở Sprint 3, phần MCP server của tôi chưa đạt hiệu quả tốt bằng bạn Tuấn nên không được dùng bản cuối.
_________________

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_
Nhóm phụ thuộc vào tôi ở retrieval_worker và synthesis_worker — nếu hai module này chưa hoàn thiện thì toàn bộ pipeline RAG (từ lấy dữ liệu đến sinh câu trả lời) sẽ không chạy được.
_________________

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_
Tôi phụ thuộc vào phần MCP server và policy_tool_worker (do bạn Tuấn phụ trách) để cung cấp dữ liệu policy/exceptions chính xác; nếu thiếu phần này thì các câu hỏi liên quan policy hoặc multi-hop sẽ không xử lý đầy đủ
_________________

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*
Cải tiến: Tôi sẽ thử reranking các retrieved_chunks trước khi đưa vào synthesis_worker.
Lý do: Trong trace, câu gq03 có confidence thấp (0.638) dù retrieval đúng nguồn . Nguyên nhân có thể do nhiều chunk liên quan nhưng không được sắp xếp theo mức độ quan trọng, khiến synthesis sử dụng chưa tối ưu evidence. Nếu thêm bước rerank (ví dụ cross-encoder), hệ thống sẽ ưu tiên chunk chứa thông tin “IT Security là người phê duyệt cuối”, từ đó cải thiện độ chính xác và tăng confidence cho các câu hỏi multi-hop/phức tạp.

_________________

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
