# """
# index.py — Sprint 1: Build RAG Index
# ====================================
# Mục tiêu Sprint 1 (60 phút):
#   - Đọc và preprocess tài liệu từ data/docs/
#   - Chunk tài liệu theo cấu trúc tự nhiên (heading/section)
#   - Gắn metadata: source, section, department, effective_date, access
#   - Embed và lưu vào vector store (ChromaDB)

# Definition of Done Sprint 1:
#   ✓ Script chạy được và index đủ docs
#   ✓ Có ít nhất 3 metadata fields hữu ích cho retrieval
#   ✓ Có thể kiểm tra chunk bằng list_chunks()
# """

# import os
# import json
# import re
# from pathlib import Path
# from typing import List, Dict, Any, Optional
# from dotenv import load_dotenv

# load_dotenv()

# # =============================================================================
# # CẤU HÌNH
# # =============================================================================

# DOCS_DIR = Path(__file__).parent / "data" / "docs"
# CHROMA_DB_DIR = Path(__file__).parent / "chroma_db"

# # TODO Sprint 1: Điều chỉnh chunk size và overlap theo quyết định của nhóm
# # Gợi ý từ slide: chunk 300-500 tokens, overlap 50-80 tokens
# CHUNK_SIZE = 450       # tokens (ước lượng bằng số ký tự / 4)
# CHUNK_OVERLAP = 80     # tokens overlap giữa các chunk


# # =============================================================================
# # STEP 1: PREPROCESS
# # Làm sạch text trước khi chunk và embed
# # =============================================================================

# def preprocess_document(raw_text: str, filepath: str) -> Dict[str, Any]:
#     """
#     Preprocess một tài liệu: extract metadata từ header và làm sạch nội dung.

#     Args:
#         raw_text: Toàn bộ nội dung file text
#         filepath: Đường dẫn file để làm source mặc định

#     Returns:
#         Dict chứa:
#           - "text": nội dung đã clean
#           - "metadata": dict với source, department, effective_date, access

#     TODO Sprint 1:
#     - Extract metadata từ dòng đầu file (Source, Department, Effective Date, Access)
#     - Bỏ các dòng header metadata khỏi nội dung chính
#     - Normalize khoảng trắng, xóa ký tự rác

#     Gợi ý: dùng regex để parse dòng "Key: Value" ở đầu file.
#     """
#     lines = raw_text.strip().split("\n")
#     metadata = {
#         "source": filepath,
#         "section": "",
#         "department": "unknown",
#         "effective_date": "unknown",
#         "access": "internal",
#     }
#     content_lines = []
#     header_done = False

#     for line in lines:
#         if not header_done:
#             # TODO: Parse metadata từ các dòng "Key: Value"
#             # Ví dụ: "Source: policy/refund-v4.pdf" → metadata["source"] = "policy/refund-v4.pdf"
#             if line.startswith("Source:"):
#                 metadata["source"] = line.replace("Source:", "").strip()
#             elif line.startswith("Department:"):
#                 metadata["department"] = line.replace("Department:", "").strip()
#             elif line.startswith("Effective Date:"):
#                 # REGEX: Extract date pattern (YYYY-MM-DD or DD/MM/YYYY, etc.)
#                 date_match = re.search(r'(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})', line)
#                 if date_match:
#                     metadata["effective_date"] = date_match.group(1)
#                 else:
#                     metadata["effective_date"] = line.replace("Effective Date:", "").strip()
#             elif line.startswith("Access:"):
#                 metadata["access"] = line.replace("Access:", "").strip()
#             elif line.startswith("==="):
#                 # Gặp section heading đầu tiên → kết thúc header
#                 header_done = True
#                 content_lines.append(line)
#             elif line.strip() == "" or line.isupper():
#                 # Dòng tên tài liệu (toàn chữ hoa) hoặc dòng trống
#                 continue
#         else:
#             content_lines.append(line)

#     cleaned_text = "\n".join(content_lines)

#     # TODO: Thêm bước normalize text nếu cần
#     # Gợi ý: bỏ ký tự đặc biệt thừa, chuẩn hóa dấu câu
#     cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)  # max 2 dòng trống liên tiếp

#     return {
#         "text": cleaned_text,
#         "metadata": metadata,
#     }


# # =============================================================================
# # STEP 2: CHUNK
# # Chia tài liệu thành các đoạn nhỏ theo cấu trúc tự nhiên
# # =============================================================================

# def chunk_document(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
#     """
#     Chunk một tài liệu đã preprocess thành danh sách các chunk nhỏ.

#     Args:
#         doc: Dict với "text" và "metadata" (output của preprocess_document)

#     Returns:
#         List các Dict, mỗi dict là một chunk với:
#           - "text": nội dung chunk
#           - "metadata": metadata gốc + "section" của chunk đó

#     TODO Sprint 1:
#     1. Split theo heading "=== Section ... ===" hoặc "=== Phần ... ===" trước
#     2. Nếu section quá dài (> CHUNK_SIZE * 4 ký tự), split tiếp theo paragraph
#     3. Thêm overlap: lấy đoạn cuối của chunk trước vào đầu chunk tiếp theo
#     4. Mỗi chunk PHẢI giữ metadata đầy đủ từ tài liệu gốc

#     Gợi ý: Ưu tiên cắt tại ranh giới tự nhiên (section, paragraph)
#     thay vì cắt theo token count cứng.
#     """
#     text = doc["text"]
#     base_metadata = doc["metadata"].copy()
#     chunks = []

#     # TODO: Implement chunking theo section heading
#     # Bước 1: Split theo heading pattern "=== ... ==="
#     sections = re.split(r"(===.*?===)", text)

#     current_section = "General"
#     current_section_text = ""
    
#     # REGEX: Extract section number from section header (Mục 1, Phần 2.1, etc.)
#     section_number_pattern = r"(Mục|Phần|Chương|Section)\s+([\d\.]+)"

#     for part in sections:
#         if re.match(r"===.*?===", part):
#             # Lưu section trước (nếu có nội dung)
#             if current_section_text.strip():
#                 section_chunks = _split_by_size(
#                     current_section_text.strip(),
#                     base_metadata=base_metadata,
#                     section=current_section,
#                 )
#                 chunks.extend(section_chunks)
#             # Bắt đầu section mới
#             current_section = part.strip("= ").strip()
#             # REGEX: Extract section number if exists
#             section_num_match = re.search(section_number_pattern, current_section)
#             if section_num_match:
#                 section_num = section_num_match.group(2)
#                 # Store section number in metadata for better filtering
#                 base_metadata["section_number"] = section_num
#             current_section_text = ""
#         else:
#             current_section_text += part

#     # Lưu section cuối cùng
#     if current_section_text.strip():
#         section_chunks = _split_by_size(
#             current_section_text.strip(),
#             base_metadata=base_metadata,
#             section=current_section,
#         )
#         chunks.extend(section_chunks)

#     return chunks


# def _split_by_size(
#     text: str,
#     base_metadata: Dict,
#     section: str,
#     chunk_chars: int = CHUNK_SIZE * 4,
#     overlap_chars: int = CHUNK_OVERLAP * 4,
# ) -> List[Dict[str, Any]]:
#     """
#     Helper: Split text dài thành chunks với overlap.
    
#     Recursive Character Text Splitting:
#     - Ưu tiên cắt tại ranh giới tự nhiên (paragraph/sentence)
#     - Cấp độ 1: Chia theo double newline (\n\n) - paragraph breaks
#     - Cấp độ 2: Chia theo single newline (\n) - line breaks
#     - Cấp độ 3: Chia theo dấu chấm + space (". ") - sentence breaks
#     - Cấp độ 4: Chia theo ký tự nếu cần

#     TODO Sprint 1:
#     Hiện tại dùng split đơn giản theo ký tự.
#     Cải thiện: split theo paragraph (\n\n) trước, rồi mới ghép đến khi đủ size.
#     """
#     if len(text) <= chunk_chars:
#         # Toàn bộ section vừa một chunk
#         return [{
#             "text": text,
#             "metadata": {**base_metadata, "section": section},
#         }]

#     # TODO: Implement split theo paragraph với overlap
#     # Gợi ý:
#     # paragraphs = text.split("\n\n")
#     # Ghép paragraphs lại cho đến khi gần đủ chunk_chars
#     # Lấy overlap từ đoạn cuối chunk trước
    
#     # RECURSIVE CHARACTER TEXT SPLITTING
#     # Level 1: Split by double newline (paragraph breaks)
#     separators = ["\n\n", "\n", ". ", " ", ""]
#     chunks = []
    
#     def _recursive_split(text_to_split: str, separators_list: List[str]) -> List[str]:
#         """Recursively split text by separators, preserving natural boundaries."""
#         if not text_to_split or len(text_to_split) <= chunk_chars:
#             return [text_to_split] if text_to_split else []
        
#         if not separators_list:
#             # Fallback: split by character if no separators work
#             return [text_to_split[i:i+chunk_chars] for i in range(0, len(text_to_split), chunk_chars)]
        
#         separator = separators_list[0]
#         good_splits = []
        
#         if separator:
#             # Split by current separator
#             splits = text_to_split.split(separator)
#         else:
#             splits = list(text_to_split)  # character-level
        
#         # Group splits to reach chunk_chars without exceeding it too much
#         good_split = []
#         for split in splits:
#             if len("".join(good_split + [split])) > chunk_chars:
#                 if good_split:
#                     good_splits.append("".join(good_split))
#                 good_split = [split]
#             else:
#                 good_split.append(split)
        
#         if good_split:
#             good_splits.append("".join(good_split))
        
#         # Recursively split any piece that's still too long
#         merged_text = []
#         for split in good_splits:
#             if len(split) > chunk_chars:
#                 merged_text.extend(_recursive_split(split, separators_list[1:]))
#             else:
#                 if split:  # Skip empty strings
#                     merged_text.append(split)
        
#         return merged_text
    
#     # Get recursively-split pieces
#     split_texts = _recursive_split(text, separators)
    
#     # Now merge pieces with overlap context
#     current_chunk = ""
#     for i, split_text in enumerate(split_texts):
#         if not split_text:
#             continue
            
#         # Check if adding this split would exceed chunk size
#         combined = current_chunk + split_text
#         if len(combined) <= chunk_chars * 1.2:  # Allow slight overage for natural breaks
#             current_chunk = combined
#         else:
#             # Save current chunk if it has content
#             if current_chunk:
#                 chunks.append({
#                     "text": current_chunk.strip(),
#                     "metadata": {**base_metadata, "section": section},
#                 })
#             # Add overlap: start new chunk with end of previous
#             if overlap_chars > 0 and len(current_chunk) > overlap_chars:
#                 # Get last overlap_chars characters as context
#                 overlap_text = current_chunk[-overlap_chars:]
#                 current_chunk = overlap_text + split_text
#             else:
#                 current_chunk = split_text
    
#     # Add final chunk
#     # Nếu chunk cuối cùng quá nhỏ (< 30% chunk_chars), append vào chunk trước đó
#     # thay vì tạo chunk riêng
#     if current_chunk.strip():
#         MIN_CHUNK_THRESHOLD = chunk_chars * 0.3  # 30% của chunk size
        
#         if chunks and len(current_chunk.strip()) < MIN_CHUNK_THRESHOLD:
#             # Append vào chunk cuối cùng thay vì tạo chunk mới
#             chunks[-1]["text"] += "\n" + current_chunk.strip()
#         else:
#             # Tạo chunk mới
#             chunks.append({
#                 "text": current_chunk.strip(),
#                 "metadata": {**base_metadata, "section": section},
#             })
    
#     return chunks


# # =============================================================================
# # STEP 3: EMBED + STORE
# # Embed các chunk và lưu vào ChromaDB
# # =============================================================================

# # Dense Vector Embedding - Initialize OpenAI client
# _openai_client = None

# def _get_openai_client():
#     """Lazy-load OpenAI client."""
#     global _openai_client
#     if _openai_client is None:
#         from openai import OpenAI
#         api_key = os.getenv("OPENAI_API_KEY")
#         if not api_key:
#             raise ValueError(
#                 "OPENAI_API_KEY không được tìm thấy. "
#                 "Vui lòng tạo file .env với nội dung: OPENAI_API_KEY=your_key_here"
#             )
#         _openai_client = OpenAI(api_key=api_key)
#     return _openai_client

# def get_embedding(text: str) -> List[float]:
#     """
#     Tạo embedding vector cho một đoạn text dùng Dense Vector Embedding.
    
#     Sử dụng OpenAI's text-embedding-3-small model cho embedding chất lượng cao
#     và hiệu suất tốt.

#     TODO Sprint 1:
#     Chọn một trong hai:

#     Option A — OpenAI Embeddings (cần OPENAI_API_KEY):
#         from openai import OpenAI
#         client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#         response = client.embeddings.create(
#             input=text,
#             model="text-embedding-3-small"
#         )
#         return response.data[0].embedding

#     Option B — Sentence Transformers (chạy local, không cần API key):
#         from sentence_transformers import SentenceTransformer
#         model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
#         return model.encode(text).tolist()
#     """
#     # DENSE VECTOR EMBEDDING - Using OpenAI text-embedding-3-small
#     try:
#         client = _get_openai_client()
#         response = client.embeddings.create(
#             input=text,
#             model="text-embedding-3-small"
#         )
#         return response.data[0].embedding
#     except ImportError:
#         raise ImportError(
#             "OpenAI package không được tìm thấy. "
#             "Chạy: pip install openai"
#         )


# def build_index(docs_dir: Path = DOCS_DIR, db_dir: Path = CHROMA_DB_DIR) -> None:
#     """
#     Pipeline hoàn chỉnh: đọc docs → preprocess → chunk → embed → store.

#     TODO Sprint 1:
#     1. Cài thư viện: pip install chromadb
#     2. Khởi tạo ChromaDB client và collection
#     3. Với mỗi file trong docs_dir:
#        a. Đọc nội dung
#        b. Gọi preprocess_document()
#        c. Gọi chunk_document()
#        d. Với mỗi chunk: gọi get_embedding() và upsert vào ChromaDB
#     4. In số lượng chunk đã index

#     Gợi ý khởi tạo ChromaDB:
#         import chromadb
#         client = chromadb.PersistentClient(path=str(db_dir))
#         collection = client.get_or_create_collection(
#             name="rag_lab",
#             metadata={"hnsw:space": "cosine"}
#         )
#     """
#     import chromadb

#     print(f"Đang build index từ: {docs_dir}")
#     db_dir.mkdir(parents=True, exist_ok=True)

#     # TODO: Khởi tạo ChromaDB
#     client = chromadb.PersistentClient(path=str(db_dir))
#     collection = client.get_or_create_collection(
#         name="rag_lab",
#         metadata={"hnsw:space": "cosine"}
#     )

#     total_chunks = 0
#     doc_files = list(docs_dir.glob("*.txt"))

#     if not doc_files:
#         print(f"Không tìm thấy file .txt trong {docs_dir}")
#         return

#     for filepath in doc_files:
#         print(f"  Processing: {filepath.name}")
#         raw_text = filepath.read_text(encoding="utf-8")

#         # TODO: Gọi preprocess_document
#         doc = preprocess_document(raw_text, str(filepath))

#         # TODO: Gọi chunk_document
#         chunks = chunk_document(doc)

#         # TODO: Embed và lưu từng chunk vào ChromaDB
#         for i, chunk in enumerate(chunks):
#             chunk_id = f"{filepath.stem}_{i}"
#             try:
#                 # Dense Vector Embedding - Get embedding for each chunk
#                 embedding = get_embedding(chunk["text"])
#                 collection.upsert(
#                     ids=[chunk_id],
#                     embeddings=[embedding],
#                     documents=[chunk["text"]],
#                     metadatas=[chunk["metadata"]],
#                 )
#             except Exception as e:
#                 print(f"    Lỗi embed chunk {chunk_id}: {e}")
#                 continue
#         total_chunks += len(chunks)
#         print(f"    → {len(chunks)} chunks đã được embed và lưu")

#     print(f"\nHoàn thành! Tổng số chunks: {total_chunks}")
#     print(f"Index được lưu tại: {db_dir}")


# # =============================================================================
# # STEP 4: INSPECT / KIỂM TRA
# # Dùng để debug và kiểm tra chất lượng index
# # =============================================================================

# def list_chunks(db_dir: Path = CHROMA_DB_DIR, n: int = 5) -> None:
#     """
#     In ra n chunk đầu tiên trong ChromaDB để kiểm tra chất lượng index.

#     TODO Sprint 1:
#     Implement sau khi hoàn thành build_index().
#     Kiểm tra:
#     - Chunk có giữ đủ metadata không? (source, section, effective_date)
#     - Chunk có bị cắt giữa điều khoản không?
#     - Metadata effective_date có đúng không?
#     """
#     try:
#         import chromadb
#         client = chromadb.PersistentClient(path=str(db_dir))
#         collection = client.get_collection("rag_lab")
#         results = collection.get(limit=n, include=["documents", "metadatas"])

#         print(f"\n=== Top {n} chunks trong index ===\n")
#         for i, (doc, meta) in enumerate(zip(results["documents"], results["metadatas"])):
#             print(f"[Chunk {i+1}]")
#             print(f"  Source: {meta.get('source', 'N/A')}")
#             print(f"  Section: {meta.get('section', 'N/A')}")
#             print(f"  Effective Date: {meta.get('effective_date', 'N/A')}")
#             print(f"  Text preview: {doc[:120]}...")
#             print()
#     except Exception as e:
#         print(f"Lỗi khi đọc index: {e}")
#         print("Hãy chạy build_index() trước.")


# def inspect_metadata_coverage(db_dir: Path = CHROMA_DB_DIR) -> None:
#     """
#     Kiểm tra phân phối metadata trong toàn bộ index.

#     Checklist Sprint 1:
#     - Mọi chunk đều có source?
#     - Có bao nhiêu chunk từ mỗi department?
#     - Chunk nào thiếu effective_date?

#     TODO: Implement sau khi build_index() hoàn thành.
#     """
#     try:
#         import chromadb
#         client = chromadb.PersistentClient(path=str(db_dir))
#         collection = client.get_collection("rag_lab")
#         results = collection.get(include=["metadatas"])

#         print(f"\nTổng chunks: {len(results['metadatas'])}")

#         # TODO: Phân tích metadata
#         # Đếm theo department, kiểm tra effective_date missing, v.v.
#         departments = {}
#         missing_date = 0
#         for meta in results["metadatas"]:
#             dept = meta.get("department", "unknown")
#             departments[dept] = departments.get(dept, 0) + 1
#             if meta.get("effective_date") in ("unknown", "", None):
#                 missing_date += 1

#         print("Phân bố theo department:")
#         for dept, count in departments.items():
#             print(f"  {dept}: {count} chunks")
#         print(f"Chunks thiếu effective_date: {missing_date}")

#     except Exception as e:
#         print(f"Lỗi: {e}. Hãy chạy build_index() trước.")


# # =============================================================================
# # MAIN
# # =============================================================================

# if __name__ == "__main__":
#     print("=" * 60)
#     print("Sprint 1: Build RAG Index")
#     print("=" * 60)

#     # Bước 1: Kiểm tra docs
#     doc_files = list(DOCS_DIR.glob("*.txt"))
#     print(f"\nTìm thấy {len(doc_files)} tài liệu:")
#     for f in doc_files:
#         print(f"  - {f.name}")

#     # Bước 2: Test preprocess và chunking (không cần API key)
#     print("\n--- Test preprocess + chunking ---")
#     for filepath in doc_files[:1]:  # Test với 1 file đầu
#         raw = filepath.read_text(encoding="utf-8")
#         doc = preprocess_document(raw, str(filepath))
#         chunks = chunk_document(doc)
#         print(f"\nFile: {filepath.name}")
#         print(f"  Metadata: {doc['metadata']}")
#         print(f"  Số chunks: {len(chunks)}")
#         for i, chunk in enumerate(chunks[:3]):
#             print(f"\n  [Chunk {i+1}] Section: {chunk['metadata']['section']}")
#             print(f"  Text: {chunk['text'][:150]}...")

#     # Bước 3: Build index (yêu cầu implement get_embedding)
#     print("\n--- Build Full Index ---")
#     try:
#         build_index()
        
#         # Bước 4: Kiểm tra index
#         print("\n--- Inspection Index ---")
#         list_chunks(n=3)
#         print("\n--- Metadata Coverage ---")
#         inspect_metadata_coverage()
        
#         print("\nSprint 1 hoàn thành thành công!")
#     except Exception as e:
#         print(f"Lỗi khi build index: {e}")
#         print("Vui lòng kiểm tra:")
#         print("  1. OPENAI_API_KEY được set trong .env file")
#         print("  2. Đã cài đặt thư viện: pip install chromadb openai")
