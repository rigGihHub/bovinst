import json
from pathlib import Path
from datetime import datetime, timezone

SCHEMA_VERSION = 1

def _safe_case_id(case_id: str) -> str:
    value = "".join(ch for ch in (case_id or "") if ch.isalnum() or ch in ("-", "_"))
    return value[:80] or "default"

def save_local(case_id, case, costs, directory=".bovinst_data"):
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "case": case,
        "costs": costs,
    }
    target = folder / f"{_safe_case_id(case_id)}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return payload["saved_at"]

def load_local(case_id, directory=".bovinst_data"):
    target = Path(directory) / f"{_safe_case_id(case_id)}.json"
    if not target.exists():
        return None
    data = json.loads(target.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Ärendet är sparat med en annan dataversion.")
    return data

def delete_local(case_id, directory=".bovinst_data"):
    target = Path(directory) / f"{_safe_case_id(case_id)}.json"
    if target.exists():
        target.unlink()
        return True
    return False
