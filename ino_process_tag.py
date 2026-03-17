# ino_process_tag.py
# per-tag worker

import os
import json
import time
from typing import Optional

from ino_state import load_state, save_state, add_pending_ids
from ino_api import (
    get_access_token,
    fetch_stream_for_label,
    remove_label_from_item,
)

OUTPUT_DIR = "output"


def save_items(label: str, items) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    ts = int(time.time())
    out_path = os.path.join(OUTPUT_DIR, f"{label}_{ts}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} items to {out_path}")


def process_tag(
    label: str,
    clear_tags: bool = False,
    max_items: int = 5000,
    ot: Optional[int] = None,
) -> None:
    access_token = get_access_token()

    print(f"Fetching items for label '{label}' (ot={ot})...")
    items, rlim = fetch_stream_for_label(
        label=label,
        access_token=access_token,
        max_items=max_items,
        ot=ot,
    )

    print(f"Total items fetched for '{label}': {len(items)}")
    print("Rate limits after fetch:", rlim)

    if not items:
        return

    # Update state.json pending_ids for this label
    state = load_state()
    raw_ids = [it.get("id") for it in items]
    ids: list[str] = [iid for iid in raw_ids if isinstance(iid, str)]
    add_pending_ids(state, label, ids)

    save_state(state)

    save_items(label, items)

    if not clear_tags:
        return

    print(f"Clearing label '{label}' from fetched items...")
    for idx, item in enumerate(items, start=1):
        item_id = item.get("id")
        if not item_id:
            continue

        try:
            rlim = remove_label_from_item(item_id, label, access_token)
        except Exception:
            print(f"Failed to remove label from item {item_id}, continuing.")
            continue

        if idx % 50 == 0:
            print(f" Cleared {idx} items so far for '{label}'. Latest limits: {rlim}")

    print(f"Done processing label '{label}'.")


def run_for_label(
    label: str,
    *,
    clear_tags: bool = False,
    max_items: int = 5000,
    ot: Optional[int] = None,
) -> None:
    """
    Import-friendly entry point for batch runs.

    Example:
        from ino_process_tag import run_for_label
        run_for_label("android-stuff")
    """
    process_tag(
        label=label,
        clear_tags=clear_tags,
        max_items=max_items,
        ot=ot,
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Process a single Inoreader tag/label."
    )
    parser.add_argument("label", help="Label/tag name, e.g. linux-stuff")
    parser.add_argument(
        "--clear-tags",
        action="store_true",
        help="After saving, remove this label from each fetched item.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=5000,
        help="Max items to fetch for this label.",
    )
    parser.add_argument(
        "--ot",
        type=int,
        default=None,
        help="Optional 'ot' (older-than) unix timestamp for incremental fetch.",
    )

    args = parser.parse_args()

    process_tag(
        label=args.label,
        clear_tags=args.clear_tags,
        max_items=args.max_items,
        ot=args.ot,
    )


if __name__ == "__main__":
    main()
