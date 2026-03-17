# ino_merge_outputs.py

import os
import json
from glob import glob
from datetime import datetime, timezone
from typing import Dict, List


OUTPUT_DIR = "output"
BACKUP_DIR = "backup"


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_from_outputs_only(label: str) -> tuple[list[dict], list[str]]:
    items_by_id: Dict[str, dict] = {}
    paths: List[str] = []

    pattern = os.path.join(OUTPUT_DIR, f"{label}_*.json")
    for path in sorted(glob(pattern)):
        print(f"Merging batch output {path}")
        paths.append(path)
        for item in load_json(path):
            iid = item.get("id")
            if not iid:
                continue
            items_by_id[iid] = item

    return list(items_by_id.values()), paths


def write_batch_backup_and_clear_outputs(label: str) -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)

    batch_items, paths = collect_from_outputs_only(label)
    if not batch_items:
        print(f"No output files found for label '{label}' to build batch backup.")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    batch_path = os.path.join(BACKUP_DIR, f"{label}_{stamp}.json")
    with open(batch_path, "w", encoding="utf-8") as f:
        json.dump(batch_items, f, ensure_ascii=False, indent=2)
    print(
        f"Wrote batch backup (outputs only, {len(batch_items)} items) to {batch_path}"
    )

    # Clear merged output files
    for path in paths:
        try:
            os.remove(path)
            print(f"Deleted merged output file {path}")
        except OSError as e:
            print(f"Failed to delete {path}: {e}")


def collect_full_from_full_and_dated(label: str) -> list[dict]:
    items_by_id: Dict[str, dict] = {}

    # 1) existing full backup
    full_path = os.path.join(BACKUP_DIR, f"{label}.json")
    if os.path.exists(full_path):
        print(f"Loading existing full backup {full_path}")
        for item in load_json(full_path):
            iid = item.get("id")
            if not iid:
                continue
            items_by_id[iid] = item

    # 2) all dated backups
    pattern = os.path.join(BACKUP_DIR, f"{label}_*.json")
    for path in sorted(glob(pattern)):
        print(f"Merging dated backup {path}")
        for item in load_json(path):
            iid = item.get("id")
            if not iid:
                continue
            items_by_id[iid] = item

    return list(items_by_id.values())


def write_full_backup(label: str) -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)

    full_items = collect_full_from_full_and_dated(label)
    full_path = os.path.join(BACKUP_DIR, f"{label}.json")
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(full_items, f, ensure_ascii=False, indent=2)
    print(f"Updated full backup at {full_path} with {len(full_items)} items")


def run_for_label(label: str) -> None:
    """
    Import-friendly entry point for batch runs.

    Example:
        from ino_merge_outputs import run_for_label
        run_for_label("android-stuff")
    """
    write_batch_backup_and_clear_outputs(label)
    write_full_backup(label)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "For a label: (1) merge output/<label>_*.json into a dated "
            "backup/<label>_<timestamp>.json and delete those outputs, "
            "then (2) rebuild backup/<label>.json from existing full and "
            "all dated backups."
        )
    )
    parser.add_argument("label", help="Label/tag name, e.g. travel")
    args = parser.parse_args()

    run_for_label(args.label)


if __name__ == "__main__":
    main()
