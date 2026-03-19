# ino_api.py
# Shared helpers for tags, streams, edit-tag, auth, and rate-limit headers.

import os
import json
import urllib.request
import urllib.parse
import urllib.error
from http.client import HTTPMessage
from typing import Dict, Any, List, Optional, Tuple


TAGS_URL = "https://www.inoreader.com/reader/api/0/tag/list"
STREAM_CONTENTS_BASE = "https://www.inoreader.com/reader/api/0/stream/contents/"
EDIT_TAG_URL = "https://www.inoreader.com/reader/api/0/edit-tag"
TOKEN_URL = "https://www.inoreader.com/oauth2/token"
AUTH_URL = "https://www.inoreader.com/oauth2/auth"


class RateLimitInfo:
    def __init__(self, headers: HTTPMessage) -> None:
        # These really are "str or None"
        self.zone1_limit: Optional[str] = headers.get("X-Reader-Zone1-Limit")
        self.zone1_usage: Optional[str] = headers.get("X-Reader-Zone1-Usage")
        self.zone2_limit: Optional[str] = headers.get("X-Reader-Zone2-Limit")
        self.zone2_usage: Optional[str] = headers.get("X-Reader-Zone2-Usage")
        self.reset_after: Optional[str] = headers.get("X-Reader-Limits-Reset-After")

    def remaining_zone1(self) -> int:
        try:
            return int(self.zone1_limit or "0") - int(self.zone1_usage or "0")
        except ValueError:
            return 0

    def remaining_zone2(self) -> int:
        try:
            return int(self.zone2_limit or "0") - int(self.zone2_usage or "0")
        except ValueError:
            return 0

    def can_afford(self, zone: int, calls: int = 1) -> bool:
        if calls <= 0:
            return True
        if zone == 1:
            return self.remaining_zone1() >= calls
        if zone == 2:
            return self.remaining_zone2() >= calls
        return False

    @staticmethod
    def _format_reset(reset_after: Optional[str]) -> str:
        if not reset_after:
            return "unknown"
        try:
            total = int(reset_after)
        except ValueError:
            return reset_after

        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:d}:{m:02d}:{s:02d}"

    def __str__(self) -> str:
        reset_str = self._format_reset(self.reset_after)
        return (
            f"Zone1: {self.zone1_usage}/{self.zone1_limit}, "
            f"Zone2: {self.zone2_usage}/{self.zone2_limit}, "
            f"resets in {reset_str}"
        )


# ---------- Env helpers ----------


def require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"{key} not set in environment.")
    return val


def optional_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ---------- Token & auth helpers (moved from get_* scripts) ----------


def build_auth_url(
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    scope: str = "read write",
    response_type: str = "code",
) -> str:
    """
    Build the OAuth2 authorization URL for Inoreader.

    Uses INOREADER_CLIENT_ID and INOREADER_REDIRECT_URI from env if not passed.
    """
    client_id = client_id or require_env("INOREADER_CLIENT_ID")
    redirect_uri = redirect_uri or require_env("INOREADER_REDIRECT_URI")

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": response_type,
        "scope": scope,
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code_for_tokens(
    code: str,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    redirect_uri: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Exchange an auth code for access and refresh tokens.

    Uses INOREADER_CLIENT_ID / INOREADER_CLIENT_SECRET / INOREADER_REDIRECT_URI
    from env if not passed explicitly.
    """
    client_id = client_id or require_env("INOREADER_CLIENT_ID")
    client_secret = client_secret or require_env("INOREADER_CLIENT_SECRET")
    redirect_uri = redirect_uri or require_env("INOREADER_REDIRECT_URI")

    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    encoded = urllib.parse.urlencode(data).encode("utf-8")

    req = urllib.request.Request(
        TOKEN_URL,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


# ---------- Core API helpers ----------


def get_access_token() -> str:
    token = os.environ.get("INOREADER_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("INOREADER_ACCESS_TOKEN not set in environment.")
    return token


def api_get(url: str, access_token: str) -> Tuple[str, RateLimitInfo]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        rlim = RateLimitInfo(resp.headers)
    return body, rlim


def api_post(url: str, data: Dict[str, Any], access_token: str) -> RateLimitInfo:
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req) as resp:
        _ = resp.read()
        rlim = RateLimitInfo(resp.headers)
    return rlim


def fetch_tags(access_token: str) -> Tuple[List[Dict[str, Any]], RateLimitInfo]:
    body, rlim = api_get(TAGS_URL, access_token)
    data = json.loads(body)
    tags = data.get("tags", [])
    return tags, rlim


def extract_label_name(tag_id: str) -> Optional[str]:
    # Expecting id like "user/123/label/linux-stuff"
    parts = tag_id.split("/label/")
    if len(parts) != 2:
        return None
    return parts[1]


def is_export_tag(label: str) -> bool:
    # Your convention: tags all lowercase, folders have capitals
    return label == label.lower()


def list_exportable_labels(access_token: str) -> Tuple[List[str], RateLimitInfo]:
    tags, rlim = fetch_tags(access_token)
    labels: List[str] = []
    for t in tags:
        tid = t.get("id", "")
        if "/label/" not in tid:
            continue
        label = extract_label_name(tid)
        if not label:
            continue
        if is_export_tag(label):
            labels.append(label)
    labels.sort()
    return labels, rlim


ZONE1_EXHAUSTED = False


def fetch_stream_for_label(
    label: str,
    access_token: str,
    max_items: int = 5000,
    ot: Optional[int] = None,
    per_page: int = 1000,
) -> Tuple[List[Dict[str, Any]], RateLimitInfo]:
    """
    Fetch items for a given label, paging through stream/contents.
    Uses user/-/label/LABEL so user ID is not needed.

    Returns (items, last_rate_limit_info).
    """
    global ZONE1_EXHAUSTED

    all_items: List[Dict[str, Any]] = []
    continuation: Optional[str] = None
    last_rlim: Optional[RateLimitInfo] = None

    tag_id = f"user/-/label/{label}"

    while True:
        params: Dict[str, Any] = {"n": per_page}
        if continuation:
            params["c"] = continuation
        if ot is not None:
            params["ot"] = ot  # unix timestamp seconds

        url = (
            STREAM_CONTENTS_BASE
            + urllib.parse.quote(tag_id, safe="")
            + "?"
            + urllib.parse.urlencode(params)
        )

        try:
            body, rlim = api_get(url, access_token)
            last_rlim = rlim
        except urllib.error.HTTPError as e:
            print("HTTP error while fetching stream:", e.code, e.reason)
            err_body = e.read().decode("utf-8", errors="replace")
            print("Response body:", err_body)
            if e.code == 429:
                print("Zone1 daily limit reached while fetching stream; stopping early.")
            ZONE1_EXHAUSTED = True
            break

        data = json.loads(body)
        items = data.get("items", [])
        all_items.extend(items)
        print(f"Fetched {len(items)} items for {label}, total {len(all_items)}")

        if len(all_items) >= max_items:
            print(f"Reached max_items={max_items} for {label}, stopping.")
            break

        continuation = data.get("continuation")
        if not continuation:
            print(f"No continuation token for {label}, end of stream.")
            break

    if last_rlim is None:
        # fabricate empty info if nothing fetched
        last_rlim = RateLimitInfo(
            urllib.request.urlopen(urllib.request.Request("about:blank")).headers
        )  # dummy
    return all_items, last_rlim


def remove_label_from_item(
    item_id: str,
    label: str,
    access_token: str,
) -> RateLimitInfo:
    """
    Remove the given label from the item via edit-tag.
    Uses user/-/label/LABEL so you don't hardcode user ID.
    """
    tag_to_remove = f"user/-/label/{label}"
    data = {
        "i": item_id,
        "r": tag_to_remove,
    }
    try:
        rlim = api_post(EDIT_TAG_URL, data, access_token)
    except urllib.error.HTTPError as e:
        print(f"HTTP error while editing tag for item {item_id}:", e.code, e.reason)
        err_body = e.read().decode("utf-8", errors="replace")
        print("Response body:", err_body)
        raise
    return rlim


def remove_label_from_items(
    item_ids: List[str],
    label: str,
    access_token: str,
) -> RateLimitInfo:
    """
    Remove a single label from many items in one edit-tag call.

    Sends one 'r=user/-/label/label' and multiple 'i' parameters.
    """
    if not item_ids:
        # No-op; fabricate an empty-ish RateLimitInfo using about:blank headers
        return RateLimitInfo(
            urllib.request.urlopen(urllib.request.Request("about:blank")).headers
        )

    tag_to_remove = f"user/-/label/{label}"

    # Start with the label to remove
    params: List[Tuple[str, str]] = [("r", tag_to_remove)]

    # Add one 'i' parameter per item ID
    for iid in item_ids:
        params.append(("i", iid))

    encoded = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        EDIT_TAG_URL,
        data=encoded,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            _ = resp.read()
            rlim = RateLimitInfo(resp.headers)
    except urllib.error.HTTPError as e:
        print(
            f"HTTP error while editing tag for {len(item_ids)} items:", e.code, e.reason
        )
        err_body = e.read().decode("utf-8", errors="replace")
        print("Response body:", err_body)
        raise

    return rlim
