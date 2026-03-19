# ino_state.py

import json
from pathlib import Path
from typing import Dict, Any, List

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
STATE_PATH = STATE_DIR / "state.json"


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {"labels": {}}
    with STATE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def ensure_label_state(state: Dict[str, Any], label: str) -> Dict[str, Any]:
    labels = state.setdefault("labels", {})
    entry = labels.get(label)
    if entry is None:
        entry = {"pending_ids": [], "done_ids": []}
        labels[label] = entry
    return entry


def add_pending_ids(state: Dict[str, Any], label: str, ids: List[str]) -> None:
    entry = ensure_label_state(state, label)
    existing = set(entry.get("pending_ids", []))
    for iid in ids:
        if iid and iid not in existing:
            entry["pending_ids"].append(iid)
            existing.add(iid)


def mark_ids_done(state: Dict[str, Any], label: str, ids: List[str]) -> None:
    entry = ensure_label_state(state, label)
    pending = set(entry.get("pending_ids", []))
    done = set(entry.get("done_ids", []))
    for iid in ids:
        if iid in pending:
            pending.remove(iid)
        if iid:
            done.add(iid)
    entry["pending_ids"] = list(pending)
    entry["done_ids"] = list(done)


def summarize_labels(state: Dict[str, Any]) -> List[str]:
    """
    Return human-readable summary lines for each label in state.json.
    """
    labels = state.get("labels", {})
    lines: List[str] = []
    for label, entry in labels.items():
        pending = len(entry.get("pending_ids", []))
        done = len(entry.get("done_ids", []))
        lines.append(f"{label}: pending={pending}, done={done}")
    return sorted(lines)
