"""Script demo freshness FAIL với data mẫu cũ (exported_at = 2026-04-10)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from monitoring.freshness_check import check_manifest_freshness

# Tạo manifest giả với timestamp cũ (~5 ngày trước)
old_manifest = {
    "run_id": "demo-stale",
    "ingest_start_timestamp": "2026-04-10T08:00:00+00:00",
    "embed_publish_timestamp": "2026-04-10T09:00:00+00:00",
    "latest_exported_at": "2026-04-10T08:00:00+00:00",
}
p = Path("artifacts/manifests/manifest_demo-stale.json")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(old_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

status, detail = check_manifest_freshness(p, sla_hours=24.0)
print(f"=== FRESHNESS CHECK DEMO (data cu 5 ngay) ===")
print(f"Overall: {status}")
for b in detail.get("boundaries", []):
    s = b["status"]
    age = b.get("age_hours", "?")
    sla = b.get("sla_hours", "?")
    reason = b.get("reason", "")
    print(f"  [{b['boundary']}] {s} | age={age}h | SLA={sla}h {reason}")
