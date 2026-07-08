"""Verify Next Trip rows stay visible after tap (including post-rerun)."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = sys.argv[1] if len(sys.argv) > 1 else "https://code-bear-shopping-list.streamlit.app/~/+/?tab=trip"


def _login(page, password: str) -> None:
    if page.get_by_role("textbox", name="Password").count():
        page.get_by_role("textbox", name="Password").fill(password)
        page.get_by_role("button", name="Log in").click()
        page.wait_for_timeout(5000)


def _trip_row_stats(page) -> dict:
    return page.evaluate(
        """() => {
        const header = document.querySelector('.trip-table-header');
        if (!header) return { ok: false, reason: 'no header' };
        const headerBox = header.closest('[data-testid="stElementContainer"]');
        const rows = [];
        let afterHeader = false;
        for (const child of headerBox.parentElement.children) {
          if (child === headerBox) { afterHeader = true; continue; }
          if (!afterHeader) continue;
          const btn = child.querySelector('button');
          const p = btn && btn.querySelector('p');
          if (!p) continue;
          const style = getComputedStyle(p);
          rows.push({
            visible: style.visibility !== 'hidden' && style.opacity !== '0',
            structured: p.classList.contains('trip-table-row'),
            text: (p.textContent || '').slice(0, 40),
          });
        }
        return {
          ok: rows.length > 0 && rows.every((r) => r.visible && r.structured),
          count: rows.length,
          rows,
        };
      }"""
    )


def main() -> int:
    secrets = tomllib.load((ROOT / ".streamlit" / "secrets.toml").open("rb"))
    password = secrets["APP_PASSWORD"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(3000)
        _login(page, password)
        page.wait_for_timeout(4000)

        before = _trip_row_stats(page)
        print("BEFORE", before)
        if not before.get("ok"):
            browser.close()
            return 1

        row = page.get_by_role("button").filter(has_text="baby spinach").first
        row.click()
        page.wait_for_timeout(200)
        fast = _trip_row_stats(page)
        print("AFTER_200MS", fast)

        page.wait_for_timeout(3000)
        after = _trip_row_stats(page)
        print("AFTER_3S", after)

        browser.close()
        if not fast.get("ok") or not after.get("ok"):
            return 2
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
