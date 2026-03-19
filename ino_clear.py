# ino_clear.py

from typing import List, Optional

from ino_api import get_access_token, remove_label_from_items
from ino_state import load_state, save_state, mark_ids_done, summarize_labels


def clear_label_from_state(
    label: str,
    batch_size: int = 5000,
    max_calls: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    """
    Clear a label from items listed in state.json (pending_ids),
    using batched edit-tag calls.

    dry_run: if True, only print what would be done, no API calls or state changes.

    This script only calls Zone 2 (edit-tag) and is safe to run even when
    Zone 1 (read) quota is exhausted, as long as your access token is valid.
    """
    access_token: str = get_access_token()  # always a str

    state = load_state()
    labels = state.get("labels", {})
    label_state = labels.get(label)
    if not label_state:
        print(f"No state found for label '{label}', nothing to clear.")
        return

    pending: List[str] = label_state.get("pending_ids", [])
    if not pending:
        print(f"No pending IDs for label '{label}', nothing to clear.")
        return

    total = len(pending)
    print(
        f"{'[DRY-RUN] ' if dry_run else ''}"
        f"Clearing label '{label}' from {total} pending items "
        f"(batch_size={batch_size}, max_calls={max_calls})..."
    )

    calls = 0
    idx = 0

    while idx < total:
        if max_calls is not None and calls >= max_calls:
            print(
                f"Reached max_calls={max_calls}, stopping early at index {idx}/{total}."
            )
            break

        batch = pending[idx : idx + batch_size]
        if not batch:
            break

        print(
            f"  {'[DRY-RUN] ' if dry_run else ''}"
            f"Batch {calls + 1}: items {idx}–{idx + len(batch) - 1} "
            f"({len(batch)} IDs) in one edit-tag call."
        )

        if not dry_run:
            try:
                rlim = remove_label_from_items(batch, label, access_token)
            except Exception as exc:
                print(f"  [ERROR] edit-tag failed for batch starting at {idx}: {exc!r}")
                break

            calls += 1
            print(f"  [OK] Cleared {len(batch)} items. Latest limits: {rlim}")
            mark_ids_done(state, label, batch)
            save_state(state)
        else:
            calls += 1  # hypothetical call

        idx += len(batch)

    if dry_run:
        print(
            f"[DRY-RUN] Would make {calls} edit-tag calls "
            f"to process {min(idx, total)} of {total} items."
        )
    else:
        # Reload to show final counts
        state = load_state()
        labels = state.get("labels", {})
        label_state = labels.get(label, {})
        pending_after: List[str] = label_state.get("pending_ids", [])
        done_after: List[str] = label_state.get("done_ids", [])
        print(
            f"Done clearing label '{label}'. "
            f"Pending now: {len(pending_after)}, done total: {len(done_after)}."
        )


def clear_all_labels(
    batch_size: int = 5000,
    max_calls: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    """
    Clear all labels that currently have pending_ids in state.json.
    """
    state = load_state()
    labels = state.get("labels", {})

    if not labels:
        print("No labels in state.json, nothing to clear.")
        return

    # Collect labels with pending work
    labels_with_pending = [
        name for name, entry in labels.items() if entry.get("pending_ids")
    ]

    if not labels_with_pending:
        print("No labels have pending_ids, nothing to clear.")
        return

    print(
        f"{'[DRY-RUN] ' if dry_run else ''}"
        f"Clearing all labels with pending_ids: {', '.join(labels_with_pending)}"
    )

    for label in labels_with_pending:
        print(f"\n=== Clearing label '{label}' ===")
        clear_label_from_state(
            label=label,
            batch_size=batch_size,
            max_calls=max_calls,
            dry_run=dry_run,
        )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Clear a label from items based on state/state.json using "
            "batched edit-tag calls, or show a summary."
        )
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Show per-label pending/done counts from state.json and exit.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Clear all labels that have pending_ids.",
    )
    parser.add_argument(
        "label",
        nargs="?",
        help="Label/tag name, e.g. cpp (required unless --summary or --all).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Max item IDs per edit-tag call (default: 5000).",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=None,
        help=(
            "Optional max number of edit-tag calls for this run. "
            "For --all, this limit applies per label."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without calling the API.",
    )
    args = parser.parse_args()

    if args.summary:
        state = load_state()
        lines = summarize_labels(state)
        if not lines:
            print("No labels in state.json.")
        else:
            print("Label state summary:")
            for line in lines:
                print(f"  {line}")
        return

    if args.all:
        clear_all_labels(
            batch_size=args.batch_size,
            max_calls=args.max_calls,
            dry_run=args.dry_run,
        )
        return

    if not args.label:
        parser.error("label is required unless --summary or --all is given")

    clear_label_from_state(
        args.label,
        batch_size=args.batch_size,
        max_calls=args.max_calls,
        dry_run=args.dry_run,
    )


# Optional legacy alias
def clearlabelfromstate(label: str) -> None:
    clear_label_from_state(label)


if __name__ == "__main__":
    main()
