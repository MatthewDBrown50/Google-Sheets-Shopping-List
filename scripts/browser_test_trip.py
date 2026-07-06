"""Browser test for Next Trip cross-off behavior on deployed app."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from trip_row_visual import trip_row_looks_crossed

ARGS = [a for a in sys.argv[1:] if a != "--mobile"]
MOBILE = "--mobile" in sys.argv
URL = ARGS[0] if ARGS else "https://code-bear-shopping-list.streamlit.app/~/+/?tab=trip"


def _login(page, password: str) -> bool:
    if page.get_by_role("textbox", name="Password").count():
        page.get_by_role("textbox", name="Password").fill(password)
        page.get_by_role("button", name="Log in").click()
        page.wait_for_timeout(5000)
    return page.get_by_role("textbox", name="Password").count() == 0


def _trip_row_button(page, name_pattern: str):
    return page.get_by_role("button", name=re.compile(name_pattern)).first


def main() -> int:
    secrets = tomllib.load((ROOT / ".streamlit" / "secrets.toml").open("rb"))
    password = secrets["APP_PASSWORD"]

    from db.config import load_config
    from db import trip_checked
    from db.client import get_client

    load_config()
    sb = get_client()
    trip_checked.clear_trip_checked_items(sb)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        if MOBILE:
            page.set_viewport_size({"width": 390, "height": 844})
        page.goto(URL, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(3000)

        if not _login(page, password):
            print("FAIL: login")
            browser.close()
            return 1

        if "Next Trip" not in page.inner_text("body"):
            print("FAIL: Next Trip header missing")
            browser.close()
            return 2

        row = _trip_row_button(page, r"baby spinach")
        if not row.count():
            print("FAIL: trip row not found")
            browser.close()
            return 3

        if trip_row_looks_crossed(row):
            print("FAIL: row already crossed before click")
            browser.close()
            return 3

        row.click()
        page.wait_for_timeout(5000)

        row = _trip_row_button(page, r"baby spinach")
        visual_crossed = trip_row_looks_crossed(row)
        stored = trip_checked.fetch_trip_checked_items(sb)
        print(f"VISUAL_AFTER_CLICK={visual_crossed}")
        print(f"SUPABASE_AFTER_CLICK={sorted(stored)}")

        if not visual_crossed:
            print("FAIL: row not visually crossed after click")
            page.screenshot(path=str(ROOT / "trip_test_fail.png"), full_page=True)
            browser.close()
            return 4
        if "baby spinach (ounce)" not in stored:
            print("FAIL: row not saved to Supabase after click")
            browser.close()
            return 5

        row.click()
        page.wait_for_timeout(5000)
        row = _trip_row_button(page, r"baby spinach")
        visual_uncrossed = not trip_row_looks_crossed(row)
        stored = trip_checked.fetch_trip_checked_items(sb)
        print(f"VISUAL_AFTER_UNCROSS={visual_uncrossed}")
        print(f"SUPABASE_AFTER_UNCROSS count={len(stored)}")
        if not visual_uncrossed or stored:
            print("FAIL: row not visually uncrossed after second click")
            browser.close()
            return 6

        # Cross again for persistence checks
        row.click()
        page.wait_for_timeout(4000)

        page.get_by_role("button", name="Meal Selection").click()
        page.wait_for_timeout(3000)
        page.get_by_role("button", name="Next Trip").click()
        page.wait_for_timeout(4000)
        row = _trip_row_button(page, r"baby spinach")
        visual_after_tab = trip_row_looks_crossed(row)
        stored = trip_checked.fetch_trip_checked_items(sb)
        print(f"VISUAL_AFTER_TAB={visual_after_tab}")
        print(f"SUPABASE_AFTER_TAB count={len(stored)}")
        if not visual_after_tab or "baby spinach (ounce)" not in stored:
            print("FAIL: cross lost after tab switch")
            browser.close()
            return 7

        page.reload(wait_until="networkidle")
        page.wait_for_timeout(8000)
        if not _login(page, password):
            print("FAIL: login after reload")
            browser.close()
            return 8
        if "tab=trip" not in page.url:
            page.goto(URL, wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(5000)
        row = _trip_row_button(page, r"baby spinach")
        visual_after_reload = trip_row_looks_crossed(row)
        stored = trip_checked.fetch_trip_checked_items(sb)
        print(f"VISUAL_AFTER_RELOAD={visual_after_reload}")
        print(f"SUPABASE_AFTER_RELOAD count={len(stored)}")
        if not visual_after_reload or "baby spinach (ounce)" not in stored:
            print("FAIL: cross lost after reload")
            browser.close()
            return 9

        print("OK")
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
