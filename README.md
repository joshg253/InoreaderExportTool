# InoreaderExportTool

Tool for backing up tagged items from Inoreader using the official API and local JSON backups.

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
        - Prompts for `INOREADER_SCOPE` with:
`Scope [Enter=keep, r=read, rw=readwrite, custom=type value]:`
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


## Core tools

### ino_process_tag.py

Fetch items for a single Inoreader label via `stream/contents` and write per-run JSON snapshots.

**Input**

- Env vars from `.env`:
    - `INOREADER_ACCESS_TOKEN` (used at runtime).
- Label name (e.g. `travel`, `android-stuff`).

**Behavior**

- Calls Inoreader’s `stream/contents/user/-/label/<label>` API and pages until done or `max_items`.
- Writes each run to:
    - `output/<label>_<unix_timestamp>.json` (immutable per-run snapshot).
- Optionally updates `state/state.json` with pending item IDs for that label if you have state helpers wired in.

**Usage**

```bash
uv run --env-file .env ino_process_tag.py travel
uv run --env-file .env ino_process_tag.py travel --max-items 5000
```


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


### ino_clear.py

Clear labels from items using the IDs tracked in `state/state.json` (Zone2-only work).

**Input**

- `state/state.json` with per-label `pending_ids`.
- Label name (e.g. `travel`).

**Behavior**

- For the given label, read `pending_ids`, call `edit-tag` to remove the label from each item, and move them to `done_ids` in state.
- Does not fetch from Inoreader; it only uses stored IDs.

**Usage**

```bash
uv run --env-file .env ino_clear.py travel
```


### ino_run_batch.py

Batch driver for multiple labels.

**Behavior**

- Uses Inoreader’s `tag/list` via `ino_api.list_exportable_labels` to discover all labels, then filters to those whose names are entirely lowercase (the “exportable” convention).
- For each lowercase label:
  - Calls `ino_process_tag.run_for_label(label)` to fetch items, update `state/state.json`, and write per-run snapshots into `output/`.
  - Calls `ino_merge_outputs.run_for_label(label)` to roll `output/<label>_*.json` into dated backups and update `backup/<label>.json`.
- Records the label list and rate limits snapshot in `state/labels.json`.
- If run with `--clear-after`, also calls `ino_clear.clear_label_from_state(label)` for each processed label to remove that label from its items after backup.

Example usage:

```bash
uv run --env-file .env ino_run_batch.py
uv run --env-file .env ino_run_batch.py --clear-after
```


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
- `fetch_stream_for_label()` – paged fetch from `stream/contents` for a label.
- `remove_label_from_item()` – call `edit-tag` to remove a label from a single item.
- `remove_label_from_items()` – call `edit-tag` once to remove a label from many items in a batch.


### ino_state.py

State management for label runs (backed by `state/state.json`):

- Tracks, per label:
    - `pending_ids` – items whose label is still applied.
    - `done_ids` – items where the label has been cleared.

Typical helpers:

- `load_state()` / `save_state()` – read/write `state/state.json`.
- `add_pending_ids(state, label, ids)` – add new IDs to `pending_ids` without duplicates.
- `mark_ids_done(state, label, ids)` – move IDs from `pending_ids` to `done_ids`.

Used by `ino_process_tag.py` on fetch and `ino_clear.py` on clear.

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
