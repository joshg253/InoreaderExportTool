import os
import json
import urllib.request
import urllib.error

TAGS_URL = "https://www.inoreader.com/reader/api/0/tag/list"

def fetch_tags_and_limits(access_token: str):
    req = urllib.request.Request(
        TAGS_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            headers = resp.headers
    except urllib.error.HTTPError as e:
        print("HTTP error:", e.code, e.reason)
        err_body = e.read().decode("utf-8", errors="replace")
        print("Response body:", err_body)
        return None, None

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("Could not parse JSON; raw response:")
        print(body)
        return None, headers

    return data, headers

def main():
    access_token = os.environ.get("INOREADER_ACCESS_TOKEN")
    if not access_token:
        print("INOREADER_ACCESS_TOKEN not set in environment.")
        return

    data, headers = fetch_tags_and_limits(access_token)
    if data is None or headers is None:
        return

    zone1_limit = headers.get("X-Reader-Zone1-Limit")
    zone1_usage = headers.get("X-Reader-Zone1-Usage")
    zone2_limit = headers.get("X-Reader-Zone2-Limit")
    zone2_usage = headers.get("X-Reader-Zone2-Usage")
    reset_after = headers.get("X-Reader-Limits-Reset-After")

    print("Rate limits:")
    print(f"  Zone1: {zone1_usage}/{zone1_limit}")
    print(f"  Zone2: {zone2_usage}/{zone2_limit}")
    print(f"  Resets in: {reset_after} seconds")

    tags = data.get("tags", [])
    label_tags = [t for t in tags if "/label/" in t.get("id", "")]

    # Sort by label name (part after /label/)
    label_tags.sort(key=lambda t: t["id"].split("/label/")[1].lower())

    print("\nLabel tags:")
    for t in label_tags:
        full_id = t["id"]
        label = full_id.split("/label/")[1]
        print(f"  {label}  ({full_id})")

if __name__ == "__main__":
    main()
