# InoreaderExportTool

Tool for backing up tagged items from Inoreader using the official API and local JSON backups.

## Label naming convention (folders vs tags)

Inoreader’s API refers to both folders and tags as “labels,” but this toolset relies on a naming convention to tell them apart:

- Folders are **Title Case** (e.g. `Programming`, `Travel`, `Linux Stuff`).
- Tags are **lowercase** (e.g. `cpp`, `linux-stuff`, `games to play`).

Only lowercase labels are treated as “exportable” tags for backup and clearing:

- `ino_run_batch.py` uses `tag/list` and filters to labels whose names are entirely lowercase.
- Those lowercase labels are the ones processed by `ino_process_tag.py`, merged by `ino_merge_outputs.py`, and optionally cleared by `ino_clear.py`.

If you follow the same convention (folders Title Case, tags lowercase), the tools will avoid touching your folder structure and will only operate on your tag-style labels.

## Setup

1. Install Python (3.11+ recommended) and optionally create/activate a virtual env.
2. Install dependencies (managed by `uv`):

    ```bash
    uv sync
    ```

3. Create `.env` from the example:

    ```bash
    copy .env.example .env   # Windows
    # or
    cp .env.example .env     # macOS/Linux
    ```

4. Run the setup helper to configure OAuth:

    ```bash
    uv run ino_setup.py
    ```

    - First run (no `.env` yet) does full setup:
        - Prompts for `INOREADER_CLIENT_ID`, `INOREADER_CLIENT_SECRET`, `INOREADER_REDIRECT_URI`.
        - Prompts for `INOREADER_SCOPE` with: `Scope [Enter=keep, r=read, rw=readwrite, custom=type value]:`
        - Prints an auth URL, you open it, authorize, and paste back the `code`.
        - Saves `INOREADER_ACCESS_TOKEN` and `INOREADER_REFRESH_TOKEN` into `.env`.
    - Later, to refresh tokens:

        ```bash
        uv run ino_setup.py
        ```

        This uses the existing `.env` and refresh token to get a new access token and update `.env`.
            - To force a clean full setup (e.g. new app or redirect URI):

        ```bash
        uv run ino_setup.py --full
        ```

5. Ensure your `.env` scope allows tag editing. For batch label clears, you need Zone 2 access, for example:

    ```bash
    INOREADER_SCOPE="read write"
    ```

    so that `edit-tag` operations are permitted.

## Rate limiting and batching

Inoreader enforces strict daily limits **per client app**:

- Zone 1 (read operations like `stream/contents`, `tag/list`): **100 requests per day**.
- Zone 2 (write operations like `edit-tag`): **100 requests per day**.

This tool is designed to:

- Use Zone 1 sparingly, fetching up to 100 items per `stream/contents` call (Inoreader’s maximum `n`) and stopping early when the daily Zone 1 cap is reached.
- Use Zone 2 **aggressively** by batching many article IDs into each `edit-tag` call:
    - Inoreader’s `edit-tag` API lets you pass the `i` parameter multiple times (or as an array) to apply the same add/remove tags to multiple items at once.
    - In practice, we’ve verified that a single `edit-tag` call can handle **thousands of item IDs** (e.g., 1k–5k IDs in one request) and still only counts as **one** Zone 2 request.

The effective pattern is:

- Use `stream/contents` (Zone 1) to walk each label once per day, up to the 100‑request limit, writing JSON snapshots and tracking item IDs in `state/state.json`.
- Use batched `edit-tag` (Zone 2) to clear labels from those items in as **few requests as possible**, often clearing thousands of items per day with just a handful of Zone 2 calls.

When the daily Zone 1 limit is exhausted (HTTP 429 “Daily request limit reached!”), the batch driver exits cleanly and you can still run `ino_clear.py` to perform Zone 2-only cleanup using IDs already stored in `state/state.json`.

## Core tools

### ino_process_tag.py

Fetch items for a single Inoreader label via `stream/contents` and write per-run JSON snapshots.

**Input**

- Env vars from `.env`:
    - `INOREADER_ACCESS_TOKEN` (used at runtime).
- Label name (e.g. `travel`, `android-stuff`).

**Behavior**

- Calls Inoreader’s `stream/contents/user/-/label/<label>` API and pages up to 100 items per request (Inoreader’s max) until:
    - The stream ends,
    - `max_items` is reached, or
    - Zone 1 quota is nearly exhausted (based on rate-limit headers).
- Writes each run to:
    - `output/<label>_<unix_timestamp>.json` (immutable per-run snapshot).
- Updates `state/state.json` with `pending_ids` for that label (one ID per item still carrying the label).

**Usage**

```bash
uv run --env-file .env ino_process_tag.py travel
uv run --env-file .env ino_process_tag.py travel --max-items 5000
```

---

### ino_merge_outputs.py

Turn per-run outputs into backups for a label and keep backups tidy.

**Input**

- Per-run outputs for a label:
    - `output/<label>_*.json`
- Existing backups (if any):
    - `backup/<label>_*.json`
    - `backup/<label>.json`

**Behavior per run for a label**

1. **Batch backup from outputs, then clear outputs**
    - Merge all `output/<label>_*.json` into a dict keyed by `id` (deduped).
    - Write a dated batch backup:
        - `backup/<label>_<YYYY-MM-DDTHH-MM-SSZ>.json`
    - Delete the merged `output/<label>_*.json` files.
2. **Full backup from existing full + all dated**
    - Start from existing `backup/<label>.json` if present.
    - Merge in all `backup/<label>_*.json`.
    - Dedupe by `id`.
    - Write updated full backup:
        - `backup/<label>.json` (always “everything so far” for that label).

**Usage**

```bash
uv run --env-file .env ino_merge_outputs.py travel
```

After running:

- `backup/travel_*.json` = batch snapshots.
- `backup/travel.json` = full backup for `travel`.

---

### ino_clear.py

Clear labels from items using the IDs tracked in `state/state.json`, using **batched** `edit-tag` calls in Zone 2.

**Input**

- `state/state.json` with per-label `pending_ids`.
- Label name (e.g. `travel`, `cpp`).
- Optional CLI flags to control batching.

**Behavior**

- For the given label, reads `pending_ids` and calls Inoreader’s `edit-tag` to remove that label from those items, moving IDs into `done_ids` in `state/state.json`.
- Uses a single `edit-tag` call with **many** `i` parameters per batch, so thousands of items can be cleared in just a few Zone 2 requests (batches of up to ~5k IDs have been confirmed to work).
- Does not perform any Zone 1 (read) calls; it only uses stored IDs and the rate-limit info returned by `edit-tag`. This means you can keep using `ino_clear.py` even after the daily Zone 1 limit is exhausted, as long as Zone 2 still has quota.

**Usage**

```bash
# Clear a specific label with large batched Zone 2 calls
uv run --env-file .env ino_clear.py travel --batch-size 5000

# Cap the number of edit-tag calls for this run
uv run --env-file .env ino_clear.py cpp --batch-size 5000 --max-calls 5

# See how many calls a given batch size would use, without hitting the API
uv run --env-file .env ino_clear.py cpp --batch-size 5000 --dry-run

# Show per-label pending/done counts from state/state.json
uv run --env-file .env ino_clear.py --summary
```

Flags:

- `--batch-size`: Maximum item IDs per `edit-tag` call (default: 5000).
- `--max-calls`: Optional cap on the number of `edit-tag` calls for this run (useful to respect the 100‑requests/day Zone 2 limit).
- `--dry-run`: Print what *would* be done (batches and call counts) without calling the API or modifying state.
- `--summary`: Do not clear anything; just print per‑label `pending` / `done` counts from `state/state.json`.

**Usage**

```bash
# Daily backup for all lowercase “exportable” labels
uv run --env-file .env ino_run_batch.py

# Daily backup + post-backup label clearing (Zone2 batched)
uv run --env-file .env ino_run_batch.py --clear-after
```

With `--clear-after`, a single daily run can:

- Walk each exportable label via `stream/contents` up to the 100‑requests/day Zone 1 limit.
- Maintain deduped JSON backups per label on disk.
- Clear thousands of labeled items per label in just a few Zone 2 calls, thanks to batched `edit-tag`.


## Auth and state helpers

### ino_setup.py

Single entry point for Inoreader OAuth:

- Full setup when `.env` is missing or `--full` is passed.
- Refresh access token when `.env` already exists.

See **Setup** section above for details and usage.

### ino_api.py

Low-level helpers around the Inoreader API:

- `get_access_token()` – read `INOREADER_ACCESS_TOKEN` from env.
- `fetch_tags()` / `list_exportable_labels()` – wrap `tag/list` to discover labels.
- `fetch_stream_for_label()` – paged fetch from `stream/contents` for a label (with rate-limit aware stopping).
- `remove_label_from_item()` – call `edit-tag` to remove a label from a single item.
- `remove_label_from_items()` – call `edit-tag` once to remove a label from many items in a batch (multiple `i` parameters).
- `RateLimitInfo` – wraps Inoreader’s rate-limit headers (`X-Reader-Zone1-*`, `X-Reader-Zone2-*`, `X-Reader-Limits-Reset-After`) and exposes helpers like `remaining_zone1()`, `remaining_zone2()`, `can_afford(zone, calls)`.


### ino_state.py

State management for label runs (backed by `state/state.json`):

- Tracks, per label:
    - `pending_ids` – items whose label is still applied.
    - `done_ids` – items where the label has been cleared.

Typical helpers:

- `load_state()` / `save_state()` – read/write `state/state.json`.
- `add_pending_ids(state, label, ids)` – add new IDs to `pending_ids` without duplicates.
- `mark_ids_done(state, label, ids)` – move IDs from `pending_ids` to `done_ids`.
- `summarize_labels(state)` – return simple per-label summary lines `label: pending=N, done=M` (used by `ino_clear.py --summary`).

Used by:

- `ino_process_tag.py` on fetch (to add pending IDs).
- `ino_clear.py` on clear (to move IDs to done and show summaries).


## Test helpers

### test_auth_url.py

Small helper to exercise `build_auth_url` from `ino_setup.py` with your current `.env`.

**Usage**

```bash
uv run test_auth_url.py
```

Prints the auth URL that `ino_setup.py` uses internally.

### test_token_flow.py

Interactive helper for testing token exchange and refresh functions.

**Usage**

```bash
uv run test_token_flow.py
```

- Option 1: test `exchange_code_for_tokens` with a pasted auth code.
- Option 2: test `refresh_tokens` with your current refresh token (prints the raw response; normal refresh is handled by `ino_setup.py`).


## Typical daily workflow

A common way to use these tools together is:

1. Run the batch driver to fetch and back up items for all “exportable” labels (lowercase names):

    ```bash
    uv run --env-file .env ino_run_batch.py
    ```

    This walks labels via `stream/contents` (Zone 1), writes per-run snapshots under `output/`, and updates `state/state.json` with `pending_ids` per label.

2. (Optional) Immediately clear labels after backup in the same run:

    ```bash
    uv run --env-file .env ino_run_batch.py --clear-after
    ```

    With `--clear-after`, each processed label is also passed to `ino_clear.clear_label_from_state`, which removes that label from items using batched `edit-tag` calls in Zone 2.

3. At any later point (even after Zone 1 is exhausted for the day), run targeted clears for individual labels using only Zone 2:

   ```bash
   # Clear a single lowercase label based on pending IDs already stored in state.json
   uv run --env-file .env ino_clear.py cpp --batch-size 5000 --max-calls 5

   # Inspect current state without clearing anything
   uv run --env-file .env ino_clear.py --summary
    ```

    Because `ino_clear.py` only uses stored IDs and calls `edit-tag` (Zone 2), you can keep clearing labels as long as there is Zone 2 quota, even when Zone 1 (read) requests have hit their daily limit.
    
    For extra safety, run with `--dry-run` first to see which lowercase labels and how many items would be affected before making changes.
