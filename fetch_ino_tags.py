#!/usr/bin/env python3
import os
import pathlib
import re
import time
import urllib.request

# Directories
RAW_EXPORT_DIR = os.getenv("INO_RAW_EXPORT_DIR", "exported_from_ino")
OUTPUT_DIR = os.getenv("INO_OUTPUT_DIR", "output")
TAGS_HTML = os.path.join(RAW_EXPORT_DIR, "tags_table.html")
TAG_EXPORT_DIR = os.path.join(OUTPUT_DIR, "ino_tag_exports")
DELAY_SECONDS = 1.0  # be gentle to Inoreader

os.makedirs(TAG_EXPORT_DIR, exist_ok=True)

print(f"Reading tags table from: {TAGS_HTML}")
print(f"Writing tag exports to:  {TAG_EXPORT_DIR}")

html = pathlib.Path(TAGS_HTML).read_text(encoding="utf-8", errors="ignore")

# Split into rows that look like tag rows
row_re = re.compile(
    r'<tr[^>]*?id="preferences_folders_tr_(\d+)"[^>]*>(.*?)</tr>',
    re.DOTALL | re.IGNORECASE,
)

name_re = re.compile(
    r"dialog\('folder_info_dialog',\{folder_id:\s*(\d+)\}\)\">([^<]+)</a>",
    re.IGNORECASE,
)

rss_re = re.compile(
    r'href="(https://www\.inoreader\.com/stream/user/[^"]+/tag/[^"]+)"[^>]*>RSS<',
    re.IGNORECASE,
)

json_re = re.compile(
    r'href="(https://www\.inoreader\.com/stream/user/[^"]+/tag/[^"]+/view/json)"[^>]*>JSON<',
    re.IGNORECASE,
)

tags = []

for m in row_re.finditer(html):
    folder_id = m.group(1)
    row_html = m.group(2)

    # Tag name
    nm = name_re.search(row_html)
    if not nm:
        continue
    tag_name = nm.group(2).strip()

    # RSS / JSON links
    rm = rss_re.search(row_html)
    jm = json_re.search(row_html)
    if not (rm and jm):
        continue

    rss_url = rm.group(1)
    json_url = jm.group(1)
    tags.append((tag_name, rss_url, json_url))

print(f"Found {len(tags)} tags")

def safe_name(s: str) -> str:
    s = s.strip().lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9._-]", "_", s)

for tag_name, rss_url, json_url in tags:
    base = safe_name(tag_name) or "tag"
    rss_path = pathlib.Path(TAG_EXPORT_DIR) / f"{base}.xml"
    json_path = pathlib.Path(TAG_EXPORT_DIR) / f"{base}.json"

    print(f"\nTag: {tag_name}")
    print(f"  RSS  -> {rss_path}")
    print(f"  JSON -> {json_path}")

    for url, path in ((rss_url, rss_path), (json_url, json_path)):
        if path.exists():
            print(f"    Skipping {path.name} (already exists)")
            continue
        try:
            print(f"    Downloading {url}")
            with urllib.request.urlopen(url) as resp:
                data = resp.read()
            path.write_bytes(data)
            time.sleep(DELAY_SECONDS)
        except Exception as e:
            print(f"    ERROR fetching {url}: {e}")

# Optional OPML skeleton
opml_path = pathlib.Path(TAG_EXPORT_DIR) / "inoreader-tags.opml"
# Placeholder base URL; adjust locally to wherever you host the XMLs
BASE_URL = os.getenv("INO_TAG_BASE_URL", "https://example.com/feeds/ino-tags")

with opml_path.open("w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<opml version="1.0">\n  <body>\n')
    f.write('    <outline text="Ino Exports" title="Ino Exports">\n')
    for tag_name, _, _ in tags:
        base = safe_name(tag_name)
        xml_url = f"{BASE_URL}/{base}.xml"
        f.write(
            f'      <outline text="Tag: {tag_name}" title="Tag: {tag_name}" '
            f'type="rss" xmlUrl="{xml_url}"/>\n'
        )
    f.write("    </outline>\n  </body>\n</opml>\n")

print(f"\nSaved OPML to {opml_path}")
print("After you upload the XMLs, set INO_TAG_BASE_URL or edit BASE_URL to match their real URL.")
