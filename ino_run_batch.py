# ino_run_batch.py

import json
from datetime import datetime, timezone
from pathlib import Path

from ino_api import get_access_token, list_exportable_labels, RateLimitInfo
from ino_process_tag import run_for_label as fetch_for_label
from ino_merge_outputs import run_for_label as merge_for_label
from ino_clear import clear_label_from_state  # new import


STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
LABELS_PATH = STATE_DIR / "labels.json"


def write_labels_state(labels: list[str], rlim: RateLimitInfo) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "labels": labels,
        "rate_limits": {
            "zone1_limit": rlim.zone1_limit,
            "zone1_usage": rlim.zone1_usage,
            "zone2_limit": rlim.zone2_limit,
            "zone2_usage": rlim.zone2_usage,
            "reset_after": rlim.reset_after,
        },
    }
    LABELS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_for_label_batch(label: str, clear_after: bool) -> None:
    print(f"Batch-All: processing label {label!r}")

    # 1) Fetch and update state + output
    fetch_for_label(label)

    # 2) Merge outputs into backups
    merge_for_label(label)

    # 3) Optionally clear tag from articles based on state
    if clear_after:
        clear_label_from_state(label)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch run: fetch + backup (and optionally clear) labels."
    )
    parser.add_argument(
        "--clear-after",
        action="store_true",
        help="After backing up each label, clear that label from its items.",
    )
    args = parser.parse_args()
    clear_after = args.clear_after

    access_token = get_access_token()

    labels, rlim = list_exportable_labels(access_token)
    if not labels:
        print("No labels found from tag/list; nothing to do.")
        return

    # Hardcoded subset
    # subset = {"travel", "android-stuff"}
    # labels = [lbl for lbl in labels if lbl in subset]

    # Only act on lowercase labels
    labels = [lbl for lbl in labels if lbl.islower()]

    write_labels_state(labels, rlim)

    for label in labels:
        try:
            run_for_label_batch(label, clear_after=clear_after)
        except Exception as exc:
            print(f"[ERROR] Label {label!r} failed in batch: {exc!r}")


if __name__ == "__main__":
    main()
