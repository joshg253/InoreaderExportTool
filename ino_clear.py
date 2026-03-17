# ino_clear.py

from typing import List

from ino_api import get_access_token, remove_label_from_item
from ino_state import load_state, save_state


def clear_label_from_state(label: str) -> None:
    access_token = get_access_token()

    state = load_state()
    label_state = state.get("labels", {}).get(label)
    if not label_state:
        print(f"No state found for label '{label}', nothing to clear.")
        return

    pending: List[str] = label_state.get("pending_ids", [])
    if not pending:
        print(f"No pending IDs for label '{label}', nothing to clear.")
        return

    done: List[str] = label_state.get("done_ids", [])

    print(f"Clearing label '{label}' from {len(pending)} items...")

    cleared = 0
    failed = 0

    for idx, item_id in enumerate(pending, start=1):
        try:
            rlim = remove_label_from_item(item_id, label, access_token)
        except Exception as exc:
            failed += 1
            print(f"  [ERROR] Failed to remove label from item {item_id}: {exc!r}")
            continue

        done.append(item_id)
        cleared += 1

        if idx % 50 == 0:
            print(f"  Cleared {idx} items so far for '{label}'. Latest limits: {rlim}")

    state.setdefault("labels", {})[label] = {
        "pending_ids": [],
        "done_ids": done,
    }
    save_state(state)

    print(f"Done clearing label '{label}'. Cleared {cleared} items, {failed} failures.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Clear a label from items based on state/state.json."
    )
    parser.add_argument("label", help="Label/tag name, e.g. travel")
    args = parser.parse_args()

    clear_label_from_state(args.label)


if __name__ == "__main__":
    main()
