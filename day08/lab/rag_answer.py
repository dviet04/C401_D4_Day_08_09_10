"""
rag_answer.py — Sprint 2 + Sprint 3: Retrieval & Grounded Answer
================================================================
Sprint 2 (60 phút): Baseline RAG
  - Dense retrieval từ ChromaDB
  - Grounded answer function với prompt ép citation
  - Trả lời được ít nhất 3 câu hỏi mẫu, output có source

Sprint 3 (60 phút): Tuning tối thiểu
  - Thêm hybrid retrieval (dense + sparse/BM25)
  - Hoặc thêm rerank (cross-encoder)
  - Hoặc thử query transformation (expansion, decomposition, HyDE)
  - Tạo bảng so sánh baseline vs variant

Definition of Done Sprint 2:
  ✓ rag_answer("SLA ticket P1?") trả về câu trả lời có citation
  ✓ rag_answer("Câu hỏi không có trong docs") trả về "Không đủ dữ liệu"

Definition of Done Sprint 3:
  ✓ Có ít nhất 1 variant (hybrid / rerank / query transform) chạy được
  ✓ Giải thích được tại sao chọn biến đó để tune
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CẤU HÌNH
# =============================================================================

TOP_K_SEARCH = 10    # Số chunk lấy từ vector store trước rerank (search rộng)
TOP_K_SELECT = 3     # Số chunk gửi vào prompt sau rerank/select (top-3 sweet spot)

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


# =============================================================================
# RETRIEVAL — DENSE (Vector Search)
# =============================================================================

def retrieve_dense(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Dense retrieval: tìm kiếm theo embedding similarity trong ChromaDB.

    Args:
        query: Câu hỏi của người dùng
        top_k: Số chunk tối đa trả về

    Returns:
        List các dict, mỗi dict là một chunk với:
          - "text": nội dung chunk
          - "metadata": metadata (source, section, effective_date, ...)
          - "score": cosine similarity score

    TODO Sprint 2:
    1. Embed query bằng cùng model đã dùng khi index (xem index.py)
    2. Query ChromaDB với embedding đó
    3. Trả về kết quả kèm score

    Gợi ý:
        import chromadb
        from index import get_embedding, CHROMA_DB_DIR

        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_collection("rag_lab")

        query_embedding = get_embedding(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        # Lưu ý: distances trong ChromaDB cosine = 1 - similarity
        # Score = 1 - distance
    """
    import chromadb
    from index import get_embedding, CHROMA_DB_DIR
    
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_collection("rag_lab")
    except Exception as e:
        print(f"Lỗi khởi tạo ChromaDB hoặc chưa có collection: {e}")
        return []

    query_embedding = get_embedding(query)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )
    
    chunks = []
    if results["documents"] and len(results["documents"]) > 0:
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]
        
        for doc, meta, dist in zip(docs, metas, distances):
            score = 1.0 - dist  # Cosine distance = 1 - similarity
            chunks.append({
                "text": doc,
                "metadata": meta,
                "score": score
            })
            
    return chunks


# =============================================================================
# RETRIEVAL — SPARSE / BM25 (Keyword Search)
# Dùng cho Sprint 3 Variant hoặc kết hợp Hybrid
# =============================================================================

def retrieve_sparse(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Sparse retrieval: tìm kiếm theo keyword (BM25).

    Mạnh ở: exact term, mã lỗi, tên riêng (ví dụ: "ERR-403", "P1", "refund")
    Hay hụt: câu hỏi paraphrase, đồng nghĩa

    TODO Sprint 3 (nếu chọn hybrid):
    1. Cài rank_bm25: pip install rank-bm25
    2. Load tất cả chunks từ ChromaDB (hoặc rebuild từ docs)
    3. Tokenize và tạo BM25Index
    4. Query và trả về top_k kết quả

    Gợi ý:
        from rank_bm25 import BM25Okapi
        corpus = [chunk["text"] for chunk in all_chunks]
        tokenized_corpus = [doc.lower().split() for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    """
    import chromadb
    from rank_bm25 import BM25Okapi
    from index import CHROMA_DB_DIR
    
    try:
        client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
        collection = client.get_collection("rag_lab")
    except Exception as e:
        print(f"Lỗi khởi tạo ChromaDB hoặc chưa có collection: {e}")
        return []
    
    all_data = collection.get(include=["documents", "metadatas"])
    documents = all_data["documents"]
    metadatas = all_data["metadatas"]
    
    if not documents:
        return []
        
    tokenized_corpus = [doc.lower().split() for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)
    tokenized_query = query.lower().split()
    
    scores = bm25.get_scores(tokenized_query)
    
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
    
    chunks = []
    for idx in top_indices:
        score = float(scores[idx])
        if score > 0:
            chunks.append({
                "text": documents[idx],
                "metadata": metadatas[idx],
                "score": score
            })
            
    return chunks


# =============================================================================
# RETRIEVAL — HYBRID (Dense + Sparse với Reciprocal Rank Fusion)
# =============================================================================

def retrieve_hybrid(
    query: str,
    top_k: int = TOP_K_SEARCH,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: kết hợp dense và sparse bằng Reciprocal Rank Fusion (RRF).

    Mạnh ở: giữ được cả nghĩa (dense) lẫn keyword chính xác (sparse)
    Phù hợp khi: corpus lẫn lộn ngôn ngữ tự nhiên và tên riêng/mã lỗi/điều khoản

    Args:
        dense_weight: Trọng số cho dense score (0-1)
        sparse_weight: Trọng số cho sparse score (0-1)

    TODO Sprint 3 (nếu chọn hybrid):
    1. Chạy retrieve_dense() → dense_results
    2. Chạy retrieve_sparse() → sparse_results
    3. Merge bằng RRF:
       RRF_score(doc) = dense_weight * (1 / (60 + dense_rank)) +
                        sparse_weight * (1 / (60 + sparse_rank))
       60 là hằng số RRF tiêu chuẩn
    4. Sort theo RRF score giảm dần, trả về top_k

    Khi nào dùng hybrid (từ slide):
    - Corpus có cả câu tự nhiên VÀ tên riêng, mã lỗi, điều khoản
    - Query như "Approval Matrix" khi doc đổi tên thành "Access Control SOP"
    """
    dense_results = retrieve_dense(query, top_k=top_k * 2)
    sparse_results = retrieve_sparse(query, top_k=top_k * 2)
    
    rrf_scores = {}
    chunk_map = {}
    
    for rank, chunk in enumerate(dense_results):
        chunk_id = chunk["text"]
        chunk_map[chunk_id] = chunk
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + dense_weight * (1.0 / (60 + rank + 1))
        
    for rank, chunk in enumerate(sparse_results):
        chunk_id = chunk["text"]
        chunk_map[chunk_id] = chunk
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + sparse_weight * (1.0 / (60 + rank + 1))
        
    sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    
    final_chunks = []
    for chunk_id, score in sorted_chunks[:top_k]:
        chunk = chunk_map[chunk_id].copy()
        chunk["score"] = score
        final_chunks.append(chunk)
        
    return final_chunks


# =============================================================================
# RERANK (Sprint 3 alternative)
# Cross-encoder để chấm lại relevance sau search rộng
# =============================================================================

def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = TOP_K_SELECT,
) -> List[Dict[str, Any]]:
    """
    Rerank các candidate chunks bằng cross-encoder.

    Cross-encoder: chấm lại "chunk nào thực sự trả lời câu hỏi này?"
    MMR (Maximal Marginal Relevance): giữ relevance nhưng giảm trùng lặp

    Funnel logic (từ slide):
      Search rộng (top-20) → Rerank (top-6) → Select (top-3)

    TODO Sprint 3 (nếu chọn rerank):
    Option A — Cross-encoder:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        pairs = [[query, chunk["text"]] for chunk in candidates]
        scores = model.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [chunk for chunk, _ in ranked[:top_k]]

    Option B — Rerank bằng LLM (đơn giản hơn nhưng tốn token):
        Gửi list chunks cho LLM, yêu cầu chọn top_k relevant nhất

    Khi nào dùng rerank:
    - Dense/hybrid trả về nhiều chunk nhưng có noise
    - Muốn chắc chắn chỉ 3-5 chunk tốt nhất vào prompt
    """
    # TODO Sprint 3: Implement rerank
    # Tạm thời trả về top_k đầu tiên (không rerank)
    return candidates[:top_k]


# =============================================================================
# QUERY TRANSFORMATION (Sprint 3 alternative)
# =============================================================================

def transform_query(query: str, strategy: str = "expansion") -> List[str]:
    """
    Biến đổi query để tăng recall.

    Strategies:
      - "expansion": Thêm từ đồng nghĩa, alias, tên cũ
      - "decomposition": Tách query phức tạp thành 2-3 sub-queries
      - "hyde": Sinh câu trả lời giả (hypothetical document) để embed thay query

    TODO Sprint 3 (nếu chọn query transformation):
    Gọi LLM với prompt phù hợp với từng strategy.

    Ví dụ expansion prompt:
        "Given the query: '{query}'
         Generate 2-3 alternative phrasings or related terms in Vietnamese.
         Output as JSON array of strings."

    Ví dụ decomposition:
        "Break down this complex query into 2-3 simpler sub-queries: '{query}'
         Output as JSON array."

    Khi nào dùng:
    - Expansion: query dùng alias/tên cũ (ví dụ: "Approval Matrix" → "Access Control SOP")
    - Decomposition: query hỏi nhiều thứ một lúc
    - HyDE: query mơ hồ, search theo nghĩa không hiệu quả
    """
    import json
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY không được tìm thấy")
    
    client = OpenAI(api_key=api_key)
    
    if strategy == "expansion":
        # Thêm từ đồng nghĩa, alias, tên cũ
        prompt = f"""Given the Vietnamese query: '{query}'
Generate 2-3 alternative phrasings or related terms (synonyms, old names, aliases) that might retrieve the same documents.
Output as a JSON array of strings (Vietnamese), including the original query.
Example: ["original query", "alternative 1", "alternative 2"]

Output ONLY the JSON array, no other text."""
        
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        
        try:
            result_text = response.choices[0].message.content.strip()
            variants = json.loads(result_text)
            return variants if isinstance(variants, list) else [query]
        except json.JSONDecodeError:
            return [query]
    
    elif strategy == "decomposition":
        # Tách query phức tạp thành 2-3 sub-queries
        prompt = f"""Given the complex Vietnamese query: '{query}'
Break it down into 2-3 simpler, independent sub-queries that together answer the original question.
Output as a JSON array of strings (Vietnamese).
Example: ["subquery 1", "subquery 2"]

Output ONLY the JSON array, no other text."""
        
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        
        try:
            result_text = response.choices[0].message.content.strip()
            sub_queries = json.loads(result_text)
            return sub_queries if isinstance(sub_queries, list) else [query]
        except json.JSONDecodeError:
            return [query]
    
    elif strategy == "hyde":
        # HyDE: Sinh hypothetical document để embed thay query
        prompt = f"""Given the Vietnamese question: '{query}'
Generate a hypothetical answer or document snippet that would answer this question well.
This will be used as a search query to find relevant documents.
Keep it 1-2 sentences, natural Vietnamese.

Output ONLY the hypothetical document, no other text."""
        
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        
        try:
            hypothetical_doc = response.choices[0].message.content.strip()
            # Trả về cả query gốc và hypothetical doc
            return [hypothetical_doc, query]
        except Exception:
            return [query]
    
    else:
        # Fallback: trả về query gốc
        return [query]


# =============================================================================
# GENERATION — GROUNDED ANSWER FUNCTION
# =============================================================================

def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """
    Đóng gói danh sách chunks thành context block để đưa vào prompt.

    Format: structured snippets với source, section, score (từ slide).
    Mỗi chunk có số thứ tự [1], [2], ... để model dễ trích dẫn.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        score = chunk.get("score", 0)
        text = chunk.get("text", "")

        # TODO: Tùy chỉnh format nếu muốn (thêm effective_date, department, ...)
        header = f"[{i}] {source}"
        if section:
            header += f" | {section}"
        if score > 0:
            header += f" | score={score:.2f}"

        context_parts.append(f"{header}\n{text}")

    return "\n\n".join(context_parts)


def build_grounded_prompt(query: str, context_block: str) -> str:
    """
    Xây dựng grounded prompt theo 4 quy tắc từ slide:
    1. Evidence-only: Chỉ trả lời từ retrieved context
    2. Abstain: Thiếu context thì nói không đủ dữ liệu
    3. Citation: Gắn source/section khi có thể
    4. Short, clear, stable: Output ngắn, rõ, nhất quán

    TODO Sprint 2:
    Đây là prompt baseline. Trong Sprint 3, bạn có thể:
    - Thêm hướng dẫn về format output (JSON, bullet points)
    - Thêm ngôn ngữ phản hồi (tiếng Việt vs tiếng Anh)
    - Điều chỉnh tone phù hợp với use case (CS helpdesk, IT support)
    """
    prompt = f"""Answer only from the retrieved context below.
Nếu không thấy trong context, lập tức nói 'Không đủ dữ liệu', cấm viện dẫn luật bên ngoài.
Cite the source field (in brackets like [1]) when possible.
Keep your answer short, clear, and factual.
Respond in the same language as the question.

Question: {query}

Context:
{context_block}

Answer:"""
    return prompt


def call_llm(prompt: str) -> str:
    """
    Gọi LLM để sinh câu trả lời.

    TODO Sprint 2:
    Chọn một trong hai:

    Option A — OpenAI (cần OPENAI_API_KEY):
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,     # temperature=0 để output ổn định, dễ đánh giá
            max_tokens=512,
        )
        return response.choices[0].message.content

    Option B — Google Gemini (cần GOOGLE_API_KEY):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text

    Lưu ý: Dùng temperature=0 hoặc thấp để output ổn định cho evaluation.
    """
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY không được tìm thấy")
        
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=512,
    )
    return response.choices[0].message.content


def rag_answer(
    query: str,
    retrieval_mode: str = "dense",
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
    use_rerank: bool = False,
    query_transform_strategy: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Pipeline RAG hoàn chỉnh: query → [transform] → retrieve → (rerank) → generate.

    Args:
        query: Câu hỏi
        retrieval_mode: "dense" | "sparse" | "hybrid"
        top_k_search: Số chunk lấy từ vector store (search rộng)
        top_k_select: Số chunk đưa vào prompt (sau rerank/select)
        use_rerank: Có dùng cross-encoder rerank không
        query_transform_strategy: None | "expansion" | "decomposition" | "hyde" 
                                 (None = không transform, chỉ dùng query gốc)
        verbose: In thêm thông tin debug

    Returns:
        Dict với:
          - "answer": câu trả lời grounded
          - "sources": list source names trích dẫn
          - "chunks_used": list chunks đã dùng
          - "query": query gốc
          - "queries_used": list tất cả queries sau transform (nếu có)
          - "config": cấu hình pipeline đã dùng

    TODO Sprint 2 — Implement pipeline cơ bản:
    1. Chọn retrieval function dựa theo retrieval_mode
    2. Gọi rerank() nếu use_rerank=True
    3. Truncate về top_k_select chunks
    4. Build context block và grounded prompt
    5. Gọi call_llm() để sinh câu trả lời
    6. Trả về kết quả kèm metadata

    TODO Sprint 3 — Thử các variant:
    - Variant A: đổi retrieval_mode="hybrid"
    - Variant B: bật use_rerank=True
    - Variant C: thêm query transformation trước khi retrieve
    """
    config = {
        "retrieval_mode": retrieval_mode,
        "top_k_search": top_k_search,
        "top_k_select": top_k_select,
        "use_rerank": use_rerank,
        "query_transform_strategy": query_transform_strategy,
    }

    # --- Bước 0: Query Transformation (Sprint 3) ---
    queries_to_search = [query]
    if query_transform_strategy:
        try:
            transformed = transform_query(query, strategy=query_transform_strategy)
            queries_to_search = transformed
            if verbose:
                print(f"\n[RAG] Query transformed ({query_transform_strategy}):")
                for i, q in enumerate(queries_to_search):
                    print(f"  [{i+1}] {q}")
        except Exception as e:
            if verbose:
                print(f"[RAG] Query transform failed: {e}. Using original query.")
            queries_to_search = [query]

    # --- Bước 1: Retrieve ---
    # Lấy candidates từ tất cả transformed queries, merge và deduplicate
    all_candidates = {}  # dict để avoid duplicates, key = chunk text
    
    for transformed_query in queries_to_search:
        if retrieval_mode == "dense":
            candidates = retrieve_dense(transformed_query, top_k=top_k_search)
        elif retrieval_mode == "sparse":
            candidates = retrieve_sparse(transformed_query, top_k=top_k_search)
        elif retrieval_mode == "hybrid":
            candidates = retrieve_hybrid(transformed_query, top_k=top_k_search)
        else:
            raise ValueError(f"retrieval_mode không hợp lệ: {retrieval_mode}")
        
        # Merge candidates (deduplicate by text)
        for chunk in candidates:
            chunk_text = chunk["text"]
            if chunk_text not in all_candidates:
                all_candidates[chunk_text] = chunk
            else:
                # Update score if this one is higher
                if chunk.get("score", 0) > all_candidates[chunk_text].get("score", 0):
                    all_candidates[chunk_text]["score"] = chunk.get("score", 0)
    
    # Convert back to list and sort by score
    candidates = sorted(
        all_candidates.values(),
        key=lambda x: x.get("score", 0),
        reverse=True
    )[:top_k_search]

    if verbose:
        print(f"\n[RAG] Query: {query}")
        if query_transform_strategy:
            print(f"[RAG] Transform strategy: {query_transform_strategy}")
        print(f"[RAG] Retrieved {len(candidates)} candidates (mode={retrieval_mode})")
        for i, c in enumerate(candidates[:3]):
            print(f"  [{i+1}] score={c.get('score', 0):.3f} | {c['metadata'].get('source', '?')}")

    # --- Bước 2: Rerank (optional) ---
    if use_rerank:
        candidates = rerank(query, candidates, top_k=top_k_select)
    else:
        candidates = candidates[:top_k_select]

    if verbose:
        print(f"[RAG] After select: {len(candidates)} chunks")

    # Ngưỡng Similarity Threshold (Chỉ nên cài cho Dense)
    if retrieval_mode == 'dense' and candidates:
        all_below_threshold = all(c.get('score', 0) < 0.5 for c in candidates)
        if all_below_threshold:
            if verbose:
                print("[RAG] Tất cả chunks đều dưới ngưỡng Similarity Threshold 0.5 -> Abstain")
            return {
                "query": query,
                "queries_used": queries_to_search,
                "answer": "Không đủ dữ liệu",
                "sources": [],
                "chunks_used": candidates,
                "config": config,
            }

    # --- Bước 3: Build context và prompt ---
    context_block = build_context_block(candidates)
    prompt = build_grounded_prompt(query, context_block)

    if verbose:
        print(f"\n[RAG] Prompt:\n{prompt[:500]}...\n")

    # --- Bước 4: Generate ---
    answer = call_llm(prompt)

    # --- Bước 5: Extract sources ---
    sources = list({
        c["metadata"].get("source", "unknown")
        for c in candidates
    })

    return {
        "query": query,
        "queries_used": queries_to_search,
        "answer": answer,
        "sources": sources,
        "chunks_used": candidates,
        "config": config,
    }


# =============================================================================
# SPRINT 3: SO SÁNH BASELINE VS VARIANT
# =============================================================================

def compare_retrieval_strategies(
    query: str,
    retrieval_modes: List[str] = None,
    transform_strategies: List[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    So sánh các retrieval strategies và query transformation với cùng một query.

    TODO Sprint 3:
    Chạy hàm này để thấy sự khác biệt giữa density strategies hay transform strategies.
    Dùng để justify tại sao chọn variant đó cho Sprint 3.

    A/B Rule (từ slide): Chỉ đổi MỘT biến mỗi lần.
    
    Args:
        query: Query để test
        retrieval_modes: List retrieval modes để test (default: ["dense"])
        transform_strategies: List query transform strategies (default: ["expansion", "decomposition", "hyde"])
    
    Returns:
        Dict kết quả so sánh
    """
    if retrieval_modes is None:
        retrieval_modes = ["dense"]
    
    if transform_strategies is None:
        transform_strategies = ["expansion", "decomposition", "hyde"]
    
    results = {}
    
    print(f"\n{'='*80}")
    print(f"SPRINT 3: COMPARE QUERY TRANSFORMATION STRATEGIES")
    print(f"{'='*80}")
    print(f"\nOriginal Query: {query}\n")
    
    # Baseline: Dense without transformation
    print(f"{'─'*80}")
    print("BASELINE: Dense Retrieval (No Transform)")
    print(f"{'─'*80}")
    try:
        result = rag_answer(query, retrieval_mode="dense", verbose=False)
        results["baseline_dense"] = result
        print(f"Answer: {result['answer'][:200]}...")
        print(f"Sources: {result['sources']}")
        print(f"Chunks used: {len(result['chunks_used'])}")
        print(f"Top chunk score: {result['chunks_used'][0].get('score', 0):.3f if result['chunks_used'] else 'N/A'}")
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        results["baseline_dense"] = None
    
    # Test each transform strategy
    for strategy in transform_strategies:
        print(f"\n{'─'*80}")
        print(f"VARIANT: Dense + Query Transform ({strategy})")
        print(f"{'─'*80}")
        try:
            result = rag_answer(
                query,
                retrieval_mode="dense",
                query_transform_strategy=strategy,
                verbose=False
            )
            results[f"dense_transform_{strategy}"] = result
            print(f"Queries used: {result['queries_used']}")
            print(f"Answer: {result['answer'][:200]}...")
            print(f"Sources: {result['sources']}")
            print(f"Chunks used: {len(result['chunks_used'])}")
            print(f"Top chunk score: {result['chunks_used'][0].get('score', 0):.3f if result['chunks_used'] else 'N/A'}")
        except Exception as e:
            print(f"❌ Lỗi: {e}")
            results[f"dense_transform_{strategy}"] = None
    
    # Print comparison summary
    print(f"\n{'='*80}")
    print("COMPARISON SUMMARY")
    print(f"{'='*80}\n")
    
    comparison_data = []
    for key, result in results.items():
        if result:
            comparison_data.append({
                "Method": key,
                "Answer Length": len(result["answer"]),
                "Num Sources": len(result["sources"]),
                "Num Chunks": len(result["chunks_used"]),
                "Top Score": result["chunks_used"][0].get("score", 0) if result["chunks_used"] else 0,
            })
    
    if comparison_data:
        print(f"{'Method':<30} {'Ans Len':>8} {'Sources':>8} {'Chunks':>8} {'Top Score':>10}")
        print("─" * 70)
        for row in comparison_data:
            print(f"{row['Method']:<30} {row['Answer Length']:>8} {row['Num Sources']:>8} {row['Num Chunks']:>8} {row['Top Score']:>10.3f}")
    
    print(f"\n{'='*80}\n")
    
    return results


# =============================================================================
# MAIN — Demo và Test
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 2 + 3: RAG Answer Pipeline")
    print("=" * 60)

    # Test queries từ data/test_questions.json
    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?",
        "Ai phải phê duyệt để cấp quyền Level 3?",
        "ERR-403-AUTH là lỗi gì?",  # Query không có trong docs → kiểm tra abstain
    ]

    print("\n--- Sprint 2: Test Baseline (Dense) ---")
    for query in test_queries[:2]:  # Test 2 queries đầu để tiết kiệm token
        print(f"\nQuery: {query}")
        try:
            result = rag_answer(query, retrieval_mode="dense", verbose=False)
            print(f"Answer: {result['answer'][:150]}...")
            print(f"Sources: {result['sources']}")
        except NotImplementedError:
            print("Chưa implement — hoàn thành TODO trong retrieve_dense() và call_llm() trước.")
        except Exception as e:
            print(f"Lỗi: {e}")

    # Sprint 3: So sánh Query Transformation strategies
    print("\n\n" + "="*80)
    print("SPRINT 3: QUERY TRANSFORMATION STRATEGIES")
    print("="*80)
    print("Chọn 1 query để test các transformation strategies\n")
    
    test_query = "Ai phải phê duyệt để cấp quyền Level 3?"
    compare_retrieval_strategies(test_query)
    
    print("\n\nNgười dùng có thể test thêm queries khác:")
    print("  - compare_retrieval_strategies('Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?')")
    print("  - compare_retrieval_strategies('SLA xử lý ticket P1 là bao lâu?')")


    print("\nViệc cần làm Sprint 3:")
    print("  1. Chọn 1 trong 3 variants: hybrid, rerank, hoặc query transformation")
    print("  2. Implement variant đó")
    print("  3. Chạy compare_retrieval_strategies() để thấy sự khác biệt")
    print("  4. Ghi lý do chọn biến đó vào docs/tuning-log.md")
