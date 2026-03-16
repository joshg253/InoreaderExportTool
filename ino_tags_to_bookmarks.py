#!/usr/bin/env python3
import glob
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from html import escape

RAW_EXPORT_DIR = os.getenv("INO_RAW_EXPORT_DIR", "exported_from_ino")
OUTPUT_DIR = os.getenv("INO_OUTPUT_DIR", "output")
TAG_EXPORT_DIR = os.path.join(OUTPUT_DIR, "ino_tag_exports")

INPUT_GLOB = os.path.join(TAG_EXPORT_DIR, "*.xml")
OUT_PATH = os.path.join(OUTPUT_DIR, "bookmarks_ino_tags.html")

now_ts = int(datetime.now().timestamp())

print(f"Reading RSS exports from: {INPUT_GLOB}")
print(f"Writing bookmarks HTML to: {OUT_PATH}")

def process_rss(path):
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return None, []
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        return None, []

    # Tag name from filename, e.g. ino_tag_exports/bass.xml -> bass
    tag_name = os.path.splitext(os.path.basename(path))[0]

    items = []
    for item in channel.findall("item"):
        link_el = item.find("link")
        title_el = item.find("title")
        if link_el is None or not (link_el.text or "").strip():
            continue
        url = link_el.text.strip()
        title = (title_el.text or url).strip() if title_el is not None else url
        items.append((url, title))
    return tag_name, items

files = sorted(glob.glob(INPUT_GLOB))

all_data = []
for path in files:
    tag, items = process_rss(path)
    if tag and items:
        all_data.append((tag, items))

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write('<!DOCTYPE NETSCAPE-Bookmark-file-1>\n')
    f.write('<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">\n')
    f.write("<TITLE>Inoreader tags export</TITLE>\n")
    f.write("<H1>Inoreader tags export</H1>\n")
    f.write("<DL><p>\n")

    for tag, items in all_data:
        f.write(f'<DT><H3 ADD_DATE="{now_ts}">tag:{escape(tag)}</H3>\n')
        f.write("<DL><p>\n")
        for url, title in items:
            f.write(f'<DT><A HREF="{escape(url)}" ADD_DATE="{now_ts}">{escape(title)}</A>\n')
        f.write("</DL><p>\n")

    f.write("</DL><p>\n")

total_items = sum(len(items) for _, items in all_data)
print(f"Wrote {OUT_PATH} with {total_items} items from {len(all_data)} tags.")
