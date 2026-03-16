# InoreaderExportTool

Tool for backing up data from Inoreader.

## Setup

1. Create and activate a virtual env (optional).
2. Install dependencies (if any) with `uv sync` or `pip install -r requirements.txt`.
3. Put your Inoreader `tags_table.html` into `exported_from_ino/`.
4. Run `python fetch_ino_tags.py`, then `python ino_tags_to_bookmarks.py`.


## Current tools

### fetch_ino_tags.py

Fetches per-tag RSS/JSON exports from Inoreader’s “Tags” page HTML and writes them to disk.

**Input**

- `exported_from_ino/tags_table.html`
  - HTML snippet copied from Inoreader’s Tag Preferences table
  - Obtained by:
    1. Open Inoreader in your browser
    2. Go to Preferences → Tags (or the page that lists your tags with RSS/JSON links)
    3. Use devtools to select and copy the relevant `<table>` HTML into `exported_from_ino/tags_table.html`

**Output**

- Per-tag exports in:

  - `output/ino_tag_exports/<tag>.xml`
  - `output/ino_tag_exports/<tag>.json`

- OPML skeleton:

  - `output/ino_tag_exports/inoreader-tags.opml`

**Config (env variables)**

- `INO_RAW_EXPORT_DIR` (default: `exported_from_ino`)
- `INO_OUTPUT_DIR` (default: `output`)
- `INO_TAG_BASE_URL` (optional; base URL used in the generated OPML)

---

### ino_tags_to_bookmarks.py

Converts the per-tag RSS exports into a Netscape-style bookmarks HTML file, grouped by tag.

**Input**

- Per-tag RSS files produced by `fetch_ino_tags.py`:

  - `output/ino_tag_exports/*.xml`

**Output**

- Bookmark HTML:

  - `output/bookmarks_ino_tags.html`

This can be imported into browsers or bookmark tools that understand Netscape bookmark format.

**Config (env variables)**

- `INO_RAW_EXPORT_DIR` (currently unused here, but kept for consistency)
- `INO_OUTPUT_DIR` (default: `output`)
