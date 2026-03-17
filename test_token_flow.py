# test_token_flow.py
#
# Helper to exercise exchange_code_for_tokens and refresh_tokens.

import json
from pathlib import Path

from ino_setup import (
    load_env,
    ENV_PATH,
    exchange_code_for_tokens,
    refresh_tokens,
)


def test_exchange_code_interactive() -> None:
    if not ENV_PATH.exists():
        print(".env not found. Run ino_setup.py first.")
        return

    env = load_env(ENV_PATH)
    code = input("Paste authorization code to test exchange_code_for_tokens: ").strip()
    if not code:
        print("No code entered; aborting.")
        return

    tokens = exchange_code_for_tokens(env, code)
    print("\nRaw tokens response:")
    print(json.dumps(tokens, indent=2))


def test_refresh_interactive() -> None:
    if not ENV_PATH.exists():
        print(".env not found. Run ino_setup.py first.")
        return

    env = load_env(ENV_PATH)
    tokens = refresh_tokens(env)
    print("\nRaw refresh response:")
    print(json.dumps(tokens, indent=2))


def main() -> None:
    print("Choose test:")
    print("  1) Test exchange_code_for_tokens (auth code → tokens)")
    print("  2) Test refresh_tokens (refresh → new access)")
    choice = input("Enter 1 or 2 (or anything else to quit): ").strip()
    if choice == "1":
        test_exchange_code_interactive()
    elif choice == "2":
        test_refresh_interactive()
    else:
        print("Canceled.")


if __name__ == "__main__":
    main()
