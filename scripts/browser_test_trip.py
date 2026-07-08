"""Browser test for Next Trip cross-off behavior on deployed app."""

from __future__ import annotations

import sys
import time
import tomllib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from trip_row_visual import trip_row_button, trip_row_looks_crossed

ARGS = [a for a in sys.argv[1:] if a != "--mobile"]
MOBILE = "--mobile" in sys.argv
URL = ARGS[0] if ARGS else "https://code-bear-shopping-list.streamlit.app/~/+/?tab=trip"


def _login(page, password: str) -> bool:
    if page.get_by_role("textbox", name="Password").count():
        page.get_by_role("textbox", name="Password").fill(password)
        page.get_by_role("button", name="Log in").click()
        page.wait_for_timeout(5000)
    return page.get_by_role("textbox", name="Password").count() == 0


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

        row = trip_row_button(page, r"baby spinach")
        if row.count() < 1:
            print("FAIL: trip row not found")
            browser.close()
            return 2

        t0 = time.perf_counter()
        row.click()
        page.wait_for_timeout(120)
        visual_fast = trip_row_looks_crossed(row)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"VISUAL_FAST={visual_fast} elapsed_ms={elapsed_ms}")

        page.wait_for_timeout(3000)
        stored = trip_checked.fetch_trip_checked_items(sb)
        print(f"SUPABASE_AFTER_CLICK={sorted(stored)}")
        visible = page.evaluate(
            """() => {
            const header = document.querySelector('.trip-table-header');
            const headerBox = header.closest('[data-testid="stElementContainer"]');
            let afterHeader = false;
            for (const child of headerBox.parentElement.children) {
              if (child === headerBox) { afterHeader = true; continue; }
              if (!afterHeader) continue;
              const ing = child.querySelector('.trip-ing');
              if (ing && ing.textContent.includes('baby spinach')) {
                const style = getComputedStyle(ing);
                return {
                  ok: ing.textContent.trim().length > 0
                    && style.visibility !== 'hidden'
                    && style.opacity !== '0',
                  text: ing.textContent,
                };
              }
            }
            return { ok: false, reason: 'row not found' };
          }"""
        )
        print(f"ROW_VISIBLE_AFTER_RERUN={visible}")
        if not visible.get("ok"):
            print("FAIL: clicked row disappeared after rerun")
            browser.close()
            return 6
        if not visual_fast:
            print("FAIL: not visually crossed within 120ms")
            browser.close()
            return 3
        if elapsed_ms > 400:
            print("FAIL: visual update slower than 400ms")
            browser.close()
            return 3
        if "baby spinach (ounce)" not in stored:
            print("FAIL: not saved to Supabase")
            browser.close()
            return 4

        row.click()
        page.wait_for_timeout(120)
        if trip_row_looks_crossed(row):
            print("FAIL: still crossed after uncross tap")
            browser.close()
            return 5

        print("OK")
        browser.close()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
