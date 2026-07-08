"""Check Next Trip column alignment (Loc/Amt/Ingredient)."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8504/?tab=trip"


def main() -> int:
    secrets = tomllib.load((ROOT / ".streamlit" / "secrets.toml").open("rb"))
    password = secrets["APP_PASSWORD"]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(3000)
        if page.get_by_role("textbox", name="Password").count():
            page.get_by_role("textbox", name="Password").fill(password)
            page.get_by_role("button", name="Log in").click()
            page.wait_for_timeout(5000)

        page.wait_for_timeout(2000)
        aligned = page.evaluate(
            """() => {
            const header = document.querySelector('.trip-table-header');
            if (!header) return { ok: false, reason: 'no header' };
            const headerBox = header.closest('[data-testid="stElementContainer"]');
            const rowBtn = headerBox.parentElement.querySelector(
              '[data-testid="stElementContainer"] ~ [data-testid="stElementContainer"] button'
            );
            if (!rowBtn) return { ok: false, reason: 'no row button' };
            const row = rowBtn.querySelector('p.trip-table-row');
            if (!row) return { ok: false, reason: 'row not structured' };
            const hLoc = header.children[0].getBoundingClientRect();
            const hAmt = header.children[1].getBoundingClientRect();
            const rLoc = row.querySelector('.trip-loc').getBoundingClientRect();
            const rAmt = row.querySelector('.trip-amt').getBoundingClientRect();
            const pStyle = getComputedStyle(row);
            const tol = 2;
            return {
              ok: Math.abs(hLoc.left - rLoc.left) <= tol
                && Math.abs(hAmt.left - rAmt.left) <= tol
                && pStyle.textDecorationLine === 'none',
              hLoc: hLoc.left,
              rLoc: rLoc.left,
              hAmt: hAmt.left,
              rAmt: rAmt.left,
              rowDecoration: pStyle.textDecorationLine,
            };
          }"""
        )
        print("ALIGNMENT_BEFORE", aligned)

        row = page.get_by_role("button").filter(has_text="baby spinach").first
        if row.count():
            row.click()
            page.wait_for_timeout(200)
            aligned_after = page.evaluate(
                """() => {
                const header = document.querySelector('.trip-table-header');
                const headerBox = header.closest('[data-testid="stElementContainer"]');
                const rowBtn = headerBox.parentElement.querySelector(
                  '[data-testid="stElementContainer"] ~ [data-testid="stElementContainer"] button'
                );
                const row = rowBtn.querySelector('p.trip-table-row');
                const hLoc = header.children[0].getBoundingClientRect();
                const hAmt = header.children[1].getBoundingClientRect();
                const rLoc = row.querySelector('.trip-loc').getBoundingClientRect();
                const rAmt = row.querySelector('.trip-amt').getBoundingClientRect();
                const pStyle = getComputedStyle(row);
                const tol = 2;
                return {
                  ok: Math.abs(hLoc.left - rLoc.left) <= tol
                    && Math.abs(hAmt.left - rAmt.left) <= tol
                    && pStyle.textDecorationLine === 'none',
                  rowDecoration: pStyle.textDecorationLine,
                };
              }"""
            )
            print("ALIGNMENT_AFTER_CROSS", aligned_after)
            row.click()
            page.wait_for_timeout(200)
            aligned_uncross = page.evaluate(
                """() => {
                const header = document.querySelector('.trip-table-header');
                const headerBox = header.closest('[data-testid="stElementContainer"]');
                const rowBtn = headerBox.parentElement.querySelector(
                  '[data-testid="stElementContainer"] ~ [data-testid="stElementContainer"] button'
                );
                const row = rowBtn.querySelector('p.trip-table-row');
                const hLoc = header.children[0].getBoundingClientRect();
                const hAmt = header.children[1].getBoundingClientRect();
                const rLoc = row.querySelector('.trip-loc').getBoundingClientRect();
                const rAmt = row.querySelector('.trip-amt').getBoundingClientRect();
                const tol = 2;
                return {
                  ok: Math.abs(hLoc.left - rLoc.left) <= tol
                    && Math.abs(hAmt.left - rAmt.left) <= tol,
                };
              }"""
            )
            print("ALIGNMENT_AFTER_UNCROSS", aligned_uncross)
            if not aligned_after.get("ok") or not aligned_uncross.get("ok"):
                browser.close()
                return 1
        browser.close()
        return 0 if aligned.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
