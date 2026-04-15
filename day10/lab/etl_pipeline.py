#!/usr/bin/env python3
"""
Lab Day 10 — ETL entrypoint: ingest → clean → validate → embed.

Tiếp nối Day 09: cùng corpus docs trong data/docs/; pipeline này xử lý *export* raw (CSV)
đại diện cho lớp ingestion từ DB/API trước khi embed lại vector store.

Chạy nhanh:
  pip install -r requirements.txt
  cp .env.example .env
  python etl_pipeline.py run

Chế độ inject (Sprint 3 — bỏ fix refund để expectation fail / eval xấu):
  python etl_pipeline.py run --no-refund-fix --skip-validate
"""
from __future__ import annotations
import logging

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from pydantic import ValidationError
from quality.schema import CleanedRecord

# Fix UnicodeEncodeError trên Windows (cp1252 không encode được tiếng Việt / ký tự đặc biệt)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

from monitoring.freshness_check import check_manifest_freshness
from quality.expectations import run_expectations
from transform.cleaning_rules import clean_rows, load_raw_csv, write_cleaned_csv, write_quarantine_csv

load_dotenv()

ROOT = Path(__file__).resolve().parent
RAW_DEFAULT = ROOT / "data" / "raw" / "policy_export_dirty.csv"
ART = ROOT / "artifacts"
LOG_DIR = ART / "logs"
MAN_DIR = ART / "manifests"
QUAR_DIR = ART / "quarantine"
CLEAN_DIR = ART / "cleaned"

def setup_logger(log_path: Path):
    logger = logging.getLogger("etl_pipeline")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def cmd_run(args: argparse.Namespace) -> int:
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%MZ")
    raw_path = Path(args.raw)
    if not raw_path.is_file():
        print(f"ERROR: raw file not found: {raw_path}", file=sys.stderr)
        return 1

    log_path = LOG_DIR / f"run_{run_id.replace(':', '-')}.log"
    logger = setup_logger(log_path)

    for p in (LOG_DIR, MAN_DIR, QUAR_DIR, CLEAN_DIR):
        p.mkdir(parents=True, exist_ok=True)

    rows = load_raw_csv(raw_path)
    raw_count = len(rows)
    if raw_count == 0:
        logger.error("Raw data rỗng --> pipeline dừng.")
        return 1
    
    ingest_start_ts = datetime.now(timezone.utc).isoformat()
    logger.info(f"run_id={run_id}")
    logger.info(f"ingest_start_timestamp={ingest_start_ts}")
    logger.info(f"raw_records={raw_count}")

    cleaned, quarantine = clean_rows(
        rows,
        apply_refund_window_fix=not args.no_refund_fix,
    )
    schema_errors = []
    validated_cleaned = []

    for row in cleaned:
        try:
            validated = CleanedRecord(**row)
            validated_cleaned.append(validated.model_dump(mode="json"))
        except ValidationError as e:
            schema_errors.append({
                "row": row,
                "error": str(e),
            })

    if schema_errors:
        logger.error(f"pydantic_validation_failed count={len(schema_errors)}")
        return 2

    cleaned = validated_cleaned
    logger.info(f"pydantic_validation_passed count={len(cleaned)}")
    
    cleaned_path = CLEAN_DIR / f"cleaned_{run_id.replace(':', '-')}.csv"
    quar_path = QUAR_DIR / f"quarantine_{run_id.replace(':', '-')}.csv"
    write_cleaned_csv(cleaned_path, cleaned)
    write_quarantine_csv(quar_path, quarantine)

    logger.info(f"cleaned_records={len(cleaned)}")
    logger.info(f"quarantine_records={len(quarantine)}")
    logger.info(f"cleaned_csv={cleaned_path.relative_to(ROOT)}")
    logger.info(f"quarantine_csv={quar_path.relative_to(ROOT)}")

    results, halt = run_expectations(cleaned)
    for r in results:
        if not r.passed:
            if r.severity == "halt":
                logger.error(f"[FAIL] {r.name} :: {r.detail}")
            else:
                logger.warning(f"[WARN] {r.name} :: {r.detail}")
    if halt and not args.skip_validate:
        logger.error("PIPELINE HALTED: critical expectation failed.")
        return 2
    if halt and args.skip_validate:
        logger.warning("Expectation failed but --skip-validate is enabled; continuing to embed.")
    fail_count = sum(1 for r in results if not r.passed and r.severity == "halt")
    warn_count = sum(1 for r in results if not r.passed and r.severity == "warn")

    if fail_count == 0 and warn_count == 0:
        logger.info("Validation passed with no issues.")
    else:
        logger.info(f"Validation summary: {fail_count} FAIL, {warn_count} WARN")
    # Embed

    embed_ok = cmd_embed_internal(
        cleaned_path,
        run_id=run_id,
        logger=logger,
    )
    if not embed_ok:
        return 3

    latest_exported = ""
    if cleaned:
        latest_exported = max((r.get("exported_at") or "" for r in cleaned), default="")
    embed_publish_ts = datetime.now(timezone.utc).isoformat()
    logger.info(f"embed_publish_timestamp={embed_publish_ts}")

    manifest = {
        "run_id": run_id,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "ingest_start_timestamp": ingest_start_ts,
        "embed_publish_timestamp": embed_publish_ts,
        "raw_path": str(raw_path.relative_to(ROOT)),
        "raw_records": raw_count,
        "cleaned_records": len(cleaned),
        "quarantine_records": len(quarantine),
        "latest_exported_at": latest_exported,
        "no_refund_fix": bool(args.no_refund_fix),
        "skipped_validate": bool(args.skip_validate and halt),
        "cleaned_csv": str(cleaned_path.relative_to(ROOT)),
        "chroma_path": os.environ.get("CHROMA_DB_PATH", "./chroma_db"),
        "chroma_collection": os.environ.get("CHROMA_COLLECTION", "day10_kb"),
    }
    man_path = MAN_DIR / f"manifest_{run_id.replace(':', '-')}.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"manifest_written={man_path.relative_to(ROOT)}")

    status, fdetail = check_manifest_freshness(man_path, sla_hours=float(os.environ.get("FRESHNESS_SLA_HOURS", "24")))
    logger.info(f"freshness_check={status} {json.dumps(fdetail, ensure_ascii=False)}")

    logger.info("PIPELINE_OK")
    return 0


def cmd_embed_internal(cleaned_csv: Path, *, run_id: str, logger: logging.Logger) -> bool:
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError:
        logger.error("chromadb chưa cài. Hãy chạy: pip install -r requirements.txt")
        return False

    db_path = os.environ.get("CHROMA_DB_PATH", str(ROOT / "chroma_db"))
    collection_name = os.environ.get("CHROMA_COLLECTION", "day10_kb")
    model_name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    from transform.cleaning_rules import load_raw_csv as load_csv  # same loader

    rows = load_csv(cleaned_csv)
    if not rows:
        logger.warning("Cleaned CSV rỗng — không embed.")
        return True

    client = chromadb.PersistentClient(path=db_path)
    emb = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
    col = client.get_or_create_collection(name=collection_name, embedding_function=emb)

    ids = [r["chunk_id"] for r in rows]
    # Tránh “mồi cũ” trong top-k: xóa id không còn trong cleaned run này (index = snapshot publish).
    try:
        prev = col.get(include=[])
        prev_ids = set(prev.get("ids") or [])
        drop = sorted(prev_ids - set(ids))
        if drop:
            col.delete(ids=drop)
            logger.info(f"embed_prune_removed={len(drop)}")
    except Exception as e:
        logger.warning(f"Embed prune skip: {e}")
    documents = [r["chunk_text"] for r in rows]
    metadatas = [
        {
            "doc_id": r.get("doc_id", ""),
            "effective_date": r.get("effective_date", ""),
            "run_id": run_id,
        }
        for r in rows
    ]
    # Idempotent: upsert theo chunk_id
    col.upsert(ids=ids, documents=documents, metadatas=metadatas)
    logger.info(f"embed_upsert count={len(ids)} collection={collection_name}")
    return True


def cmd_freshness(args: argparse.Namespace) -> int:
    p = Path(args.manifest)
    if not p.is_file():
        print(f"manifest not found: {p}", file=sys.stderr)
        return 1
    sla = float(os.environ.get("FRESHNESS_SLA_HOURS", "24"))
    status, detail = check_manifest_freshness(p, sla_hours=sla)
    print(status, json.dumps(detail, ensure_ascii=False))
    return 0 if status != "FAIL" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Day 10 ETL pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="ingest → clean → validate → embed")
    p_run.add_argument("--raw", default=str(RAW_DEFAULT), help="Đường dẫn CSV raw export")
    p_run.add_argument("--run-id", default="", help="ID run (mặc định: UTC timestamp)")
    p_run.add_argument(
        "--no-refund-fix",
        action="store_true",
        help="Không áp dụng rule fix cửa sổ 14→7 ngày (dùng cho inject corruption / before).",
    )
    p_run.add_argument(
        "--skip-validate",
        action="store_true",
        help="Vẫn embed khi expectation halt (chỉ phục vụ demo có chủ đích).",
    )
    p_run.set_defaults(func=cmd_run)

    p_fr = sub.add_parser("freshness", help="Đọc manifest và kiểm tra SLA freshness")
    p_fr.add_argument("--manifest", required=True)
    p_fr.set_defaults(func=cmd_freshness)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
