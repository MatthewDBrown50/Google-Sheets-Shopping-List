"""Browser test for Next Trip cross-off behavior on deployed app."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = sys.argv[1] if len(sys.argv) > 1 else "https://code-bear-shopping-list.streamlit.app/~/+/?tab=trip"


def main() -> int:
    secrets = tomllib.load((ROOT / ".streamlit" / "secrets.toml").open("rb"))
    password = secrets["APP_PASSWORD"]

    sys.path.insert(0, str(ROOT))
    from db.config import load_config
    from db import trip_checked
    from db.client import get_client

    load_config()
    trip_checked.clear_trip_checked_items(get_client())

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(3000)

        if page.get_by_role("textbox", name="Password").count():
            page.get_by_role("textbox", name="Password").fill(password)
            page.get_by_role("button", name="Log in").click()
            page.wait_for_timeout(5000)

        if page.get_by_role("textbox", name="Password").count():
            print("FAIL: login")
            browser.close()
            return 1

        body = page.inner_text("body")
        if "Next Trip" not in body:
            print("FAIL: Next Trip header missing")
            print(body[:500])
            browser.close()
            return 2

        links = page.locator('div[data-testid="stButton"] button')
        count = links.count()
        print(f"ROW_COUNT={count}")
        if count == 0:
            print("FAIL: no trip list rows")
            print(body[:800])
            browser.close()
            return 3

        # Skip header/nav buttons; first trip row is after segmented control + logout
        trip_buttons = page.get_by_role("button", name=re.compile(r"^\s*\d"))
        trip_count = trip_buttons.count()
        print(f"TRIP_ROW_COUNT={trip_count}")
        if trip_count < 1:
            print("FAIL: no trip row buttons")
            browser.close()
            return 3

        first_label = trip_buttons.first.inner_text()
        print(f"FIRST_ROW={first_label!r}")

        trip_buttons.first.click()
        page.wait_for_timeout(4000)
        print(f"URL_AFTER_CLICK={page.url}")

        crossed = page.locator(".trip-row-marker.crossed").count()
        print(f"CROSSED_MARKERS={crossed}")

        sys.path.insert(0, str(ROOT))
        from db.config import load_config
        from db import trip_checked
        from db.client import get_client

        load_config()
        stored = trip_checked.fetch_trip_checked_items(get_client())
        print(f"SUPABASE_AFTER_CLICK count={len(stored)} sample={sorted(stored)[:2]}")

        if crossed < 1 and len(stored) < 1:
            print("FAIL: row not crossed after click")
            browser.close()
            return 4

        # Switch tab and back
        page.get_by_role("button", name="Meal Selection").click()
        page.wait_for_timeout(3000)
        page.get_by_role("button", name="Next Trip").click()
        page.wait_for_timeout(4000)
        crossed_after_tab = page.locator(".trip-row-marker.crossed").count()
        print(f"CROSSED_AFTER_TAB={crossed_after_tab}")
        stored_after_tab = trip_checked.fetch_trip_checked_items(get_client())
        print(f"SUPABASE_AFTER_TAB count={len(stored_after_tab)}")
        if crossed_after_tab < 1 and len(stored_after_tab) < 1:
            print("FAIL: cross lost after tab switch")
            browser.close()
            return 5

        page.reload(wait_until="networkidle")
        page.wait_for_timeout(5000)
        crossed_after_reload = page.locator(".trip-row-marker.crossed").count()
        print(f"CROSSED_AFTER_RELOAD={crossed_after_reload}")
        stored_after_reload = trip_checked.fetch_trip_checked_items(get_client())
        print(f"SUPABASE_AFTER_RELOAD count={len(stored_after_reload)}")
        if crossed_after_reload < 1 and len(stored_after_reload) < 1:
            print("FAIL: cross lost after reload")
            browser.close()
            return 6

        print("OK")
        browser.close()

    # Verify persistence in Supabase when credentials are available.
    try:
        sys.path.insert(0, str(ROOT))
        from db.config import load_config
        from db import trip_checked
        from db.client import get_client

        load_config()
        stored = trip_checked.fetch_trip_checked_items(get_client())
        print(f"SUPABASE_CHECKED={sorted(stored)[:3]}... count={len(stored)}")
    except Exception as exc:
        print(f"SUPABASE_SKIP={exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
