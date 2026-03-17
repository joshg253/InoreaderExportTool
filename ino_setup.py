# ino_setup.py
#
# One-time auth + token setup and later token refresh for Inoreader.

import sys
import urllib.parse
import urllib.request
import json
from pathlib import Path
from typing import Dict

ENV_PATH = Path(".env")
ENV_EXAMPLE_PATH = Path(".env.example")

AUTH_URL = "https://www.inoreader.com/oauth2/auth"
TOKEN_URL = "https://www.inoreader.com/oauth2/token"


def load_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def save_env(path: Path, env: Dict[str, str]) -> None:
    lines = []
    for key, value in env.items():
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Updated {path}")


def ensure_env_file() -> Dict[str, str]:
    if not ENV_PATH.exists():
        if ENV_EXAMPLE_PATH.exists():
            ENV_PATH.write_text(
                ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8"
            )
            print("Created .env from .env.example")
        else:
            print("No .env or .env.example found; creating empty .env")
            ENV_PATH.touch()
    env = load_env(ENV_PATH)

    # Prompt for basics if missing
    def prompt_if_missing(key: str, prompt: str) -> None:
        if not env.get(key):
            val = input(f"{prompt}: ").strip()
            if not val:
                print(f"{key} is required; aborting.")
                sys.exit(1)
            env[key] = val

    prompt_if_missing("INOREADER_CLIENT_ID", "Enter INOREADER_CLIENT_ID")
    prompt_if_missing("INOREADER_CLIENT_SECRET", "Enter INOREADER_CLIENT_SECRET")
    prompt_if_missing("INOREADER_REDIRECT_URI", "Enter INOREADER_REDIRECT_URI")

    # Scope prompt
    current_scope = env.get("INOREADER_SCOPE", "read")
    env["INOREADER_SCOPE"] = prompt_scope(current_scope)

    save_env(ENV_PATH, env)
    return env


def prompt_scope(current: str) -> str:
    print(f"Current INOREADER_SCOPE: {current}")
    raw = input("Scope [Enter=keep, r=read, rw=readwrite, custom=type value]: ").strip()
    if not raw:
        return current
    if raw.lower() == "r":
        return "read"
    if raw.lower() == "rw":
        return "read write"
    return raw


def build_auth_url(env: Dict[str, str]) -> str:
    params = {
        "client_id": env["INOREADER_CLIENT_ID"],
        "redirect_uri": env["INOREADER_REDIRECT_URI"],
        "response_type": "code",
        "scope": env.get("INOREADER_SCOPE", "read"),
        "state": "ino-setup",
    }
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code_for_tokens(env: Dict[str, str], code: str) -> Dict[str, str]:
    data = {
        "code": code,
        "redirect_uri": env["INOREADER_REDIRECT_URI"],
        "client_id": env["INOREADER_CLIENT_ID"],
        "client_secret": env["INOREADER_CLIENT_SECRET"],
        "scope": env.get("INOREADER_SCOPE", "read"),
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
    tokens = json.loads(body)
    return tokens


def refresh_tokens(env: Dict[str, str]) -> Dict[str, str]:
    if "INOREADER_REFRESH_TOKEN" not in env:
        print(
            "No INOREADER_REFRESH_TOKEN in .env; cannot refresh. Run full setup first."
        )
        sys.exit(1)

    # Re-prompt scope in case you want to adjust it
    current_scope = env.get("INOREADER_SCOPE", "read")
    env["INOREADER_SCOPE"] = prompt_scope(current_scope)
    save_env(ENV_PATH, env)

    data = {
        "client_id": env["INOREADER_CLIENT_ID"],
        "client_secret": env["INOREADER_CLIENT_SECRET"],
        "grant_type": "refresh_token",
        "refresh_token": env["INOREADER_REFRESH_TOKEN"],
        # Inoreader examples omit scope here; we can leave it out or include env["INOREADER_SCOPE"] if needed.
    }
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
    tokens = json.loads(body)
    return tokens


def do_full_setup(env: Dict[str, str]) -> None:
    # Ensure we have basics and scope
    env = ensure_env_file()

    # Build and show auth URL
    url = build_auth_url(env)
    print("\nOpen this URL in your browser, authorize the app,")
    print("then copy the 'code' parameter from the redirected URL:\n")
    print(url)
    print()
    code = input("Paste authorization code: ").strip()
    if not code:
        print("No code entered; aborting.")
        sys.exit(1)

    tokens = exchange_code_for_tokens(env, code)
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    if not access_token or not refresh_token:
        print("Did not receive access_token and refresh_token from Inoreader:")
        print(json.dumps(tokens, indent=2))
        sys.exit(1)

    env["INOREADER_ACCESS_TOKEN"] = access_token
    env["INOREADER_REFRESH_TOKEN"] = refresh_token
    save_env(ENV_PATH, env)

    print("\nFull setup complete. Access and refresh tokens saved to .env.")


def do_refresh(env: Dict[str, str]) -> None:
    if not ENV_PATH.exists():
        print(".env does not exist; running full setup instead.")
        do_full_setup({})
        return

    env = load_env(ENV_PATH)
    # Ensure we have client id/secret/redirect
    env = ensure_env_file()  # will re-save if anything missing/changed

    tokens = refresh_tokens(env)
    access_token = tokens.get("access_token")
    new_refresh = tokens.get("refresh_token")

    if not access_token:
        print("Did not receive new access_token from Inoreader:")
        print(json.dumps(tokens, indent=2))
        sys.exit(1)

    env = load_env(ENV_PATH)
    env["INOREADER_ACCESS_TOKEN"] = access_token
    if new_refresh:
        env["INOREADER_REFRESH_TOKEN"] = new_refresh
    save_env(ENV_PATH, env)

    print("\nRefresh complete. New access token saved to .env.")
    if new_refresh:
        print("Refresh token was also updated.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Set up or refresh Inoreader OAuth tokens."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full setup (delete existing .env and start over).",
    )
    args = parser.parse_args()

    if args.full and ENV_PATH.exists():
        backup_path = ENV_PATH.with_suffix(".env.backup")
        ENV_PATH.replace(backup_path)
        print(f"Existing .env moved to {backup_path}")

    if not ENV_PATH.exists() or args.full:
        do_full_setup({})
    else:
        do_refresh({})


if __name__ == "__main__":
    main()
