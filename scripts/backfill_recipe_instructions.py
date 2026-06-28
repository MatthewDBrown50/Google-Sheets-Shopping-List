"""Import recipe instructions from Google Sheets into Supabase (no full re-migration)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gspread
from google.oauth2.service_account import Credentials

from core.sheets import parse_recipe_columns
from db.client import get_client
from db.config import load_config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def sheets_client():
    creds = Credentials.from_service_account_file(
        os.environ["SHOPPING_LIST_CREDENTIALS"],
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def backfill():
    load_config()
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("Set SUPABASE_URL and SUPABASE_KEY in the environment or .streamlit/secrets.toml")
        sys.exit(1)
    if not os.getenv("SHOPPING_LIST_CREDENTIALS") or not os.getenv("SHOPPING_LIST_WORKBOOK_ID"):
        print("Set SHOPPING_LIST_CREDENTIALS and SHOPPING_LIST_WORKBOOK_ID for Sheets access.")
        sys.exit(1)

    sb = get_client()
    recipes_sheet = sheets_client().open_by_key(os.environ["SHOPPING_LIST_WORKBOOK_ID"]).worksheet(
        "Recipes"
    )
    headers = recipes_sheet.row_values(1)

    updated = 0
    for j, header in enumerate(headers, start=1):
        if j % 2 == 0 or not header:
            continue

        amounts = recipes_sheet.col_values(j)[1:]
        ing_names = recipes_sheet.col_values(j + 1)[1:]
        _, instructions = parse_recipe_columns(amounts, ing_names)
        if not instructions:
            continue

        result = (
            sb.table("recipes")
            .update({"instructions": instructions})
            .eq("name", header)
            .execute()
        )
        if result.data:
            updated += 1
            print(f"  Updated instructions for {header!r} ({len(instructions)} chars)")

    print(f"Backfill complete. Updated {updated} recipe(s).")


if __name__ == "__main__":
    backfill()
