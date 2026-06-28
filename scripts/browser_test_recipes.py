"""Browser smoke test for the Recipes tab."""

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
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=60000)

        page.get_by_role("textbox", name="Password").fill(password)
        page.get_by_role("button", name="Log in").click()
        page.wait_for_timeout(3000)

        page.get_by_role("tab", name="Recipes").click()
        page.wait_for_timeout(4000)

        page.screenshot(path=str(ROOT / "scripts" / "recipes_tab.png"), full_page=True)

        body = page.inner_text("body")
        if any(err in body for err in ("AttributeError", "UnboundLocalError", "StreamlitAPIException", "Traceback")):
            print("ERROR_FOUND")
            for line in body.splitlines():
                if any(x in line for x in ("Error", "Traceback", "File ", "app.py")):
                    print(line)
            browser.close()
            return 1

        # Open recipe dropdown (Recipes tab selectbox is typically the last one)
        selectboxes = page.locator('[data-testid="stSelectbox"]')
        count = selectboxes.count()
        print("selectbox_count", count)
        recipe_box = selectboxes.nth(count - 1)
        recipe_box.click()
        page.wait_for_timeout(500)
        page.get_by_role("option", name="Bean & Broccoli Salad").click()
        page.wait_for_timeout(4000)

        page.screenshot(path=str(ROOT / "scripts" / "recipes_selected.png"), full_page=True)

        body = page.inner_text("body")
        if any(err in body for err in ("AttributeError", "UnboundLocalError", "StreamlitAPIException")):
            print("ERROR_AFTER_SELECT")
            for line in body.splitlines():
                if "Error" in line or "app.py" in line:
                    print(line)
            browser.close()
            return 1

        instructions = page.locator("textarea").last
        value = instructions.input_value()
        print("instructions_length", len(value))
        print("instructions_preview", value[:120].replace("\n", " "))
        browser.close()
        return 0 if value.strip() else 2


if __name__ == "__main__":
    raise SystemExit(main())
