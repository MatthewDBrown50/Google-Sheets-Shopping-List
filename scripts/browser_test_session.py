"""Verify login and tab persist across browser refresh."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    secrets = tomllib.load((ROOT / ".streamlit" / "secrets.toml").open("rb"))
    password = secrets["APP_PASSWORD"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:8501?tab=recipes", wait_until="networkidle", timeout=60000)

        page.get_by_role("textbox", name="Password").fill(password)
        page.get_by_role("button", name="Log in").click()
        page.wait_for_timeout(4000)

        if page.get_by_role("textbox", name="Password").count():
            print("LOGIN_FAILED")
            browser.close()
            return 1

        if "recipes" not in page.url.lower():
            print("TAB_PARAM_MISSING", page.url)
        if "Recipes" not in page.inner_text("body"):
            print("RECIPES_PAGE_MISSING")

        page.reload(wait_until="networkidle")
        page.wait_for_timeout(4000)

        if page.get_by_role("textbox", name="Password").count():
            print("AUTH_NOT_PERSISTED")
            browser.close()
            return 1

        if "tab=recipes" not in page.url:
            print("TAB_NOT_PERSISTED", page.url)
            browser.close()
            return 2

        print("OK", page.url)
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
