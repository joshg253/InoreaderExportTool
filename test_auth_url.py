# test_auth_url.py
#
# Small helper to exercise build_auth_url from ino_setup.py.

from pathlib import Path

from ino_setup import load_env, build_auth_url, ENV_PATH


def main() -> None:
    if not ENV_PATH.exists():
        print(".env not found. Run ino_setup.py first.")
        return

    env = load_env(ENV_PATH)
    url = build_auth_url(env)

    print("Auth URL built from current .env:")
    print(url)


if __name__ == "__main__":
    main()
