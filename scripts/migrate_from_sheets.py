"""One-time import from Google Sheets into Supabase."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gspread
from google.oauth2.service_account import Credentials

from core.generator import parse_ingredient_label
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


def migrate():
    load_config()
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        print("Set SUPABASE_URL and SUPABASE_KEY in the environment or .streamlit/secrets.toml")
        sys.exit(1)
    if not os.getenv("SHOPPING_LIST_CREDENTIALS") or not os.getenv("SHOPPING_LIST_WORKBOOK_ID"):
        print("Set SHOPPING_LIST_CREDENTIALS and SHOPPING_LIST_WORKBOOK_ID for Sheets access.")
        sys.exit(1)

    sb = get_client()
    gc = sheets_client()
    wb = gc.open_by_key(os.environ["SHOPPING_LIST_WORKBOOK_ID"])

    ingredients_sheet = wb.worksheet("Ingredients")
    recipes_sheet = wb.worksheet("Recipes")
    meal_sheet = wb.worksheet("Meal_Selection")
    next_trip_sheet = wb.worksheet("Next Trip")

    # Clear existing data (child tables first)
    sb.table("meal_selection").delete().neq("position", -1).execute()
    sb.table("other_items").delete().neq("position", -1).execute()
    sb.table("recipe_ingredients").delete().neq("id", -1).execute()
    sb.table("recipes").delete().neq("id", -1).execute()
    sb.table("ingredients").delete().neq("id", -1).execute()

    # --- Ingredients ---
    names = ingredients_sheet.col_values(1)
    calories = ingredients_sheet.col_values(2)

    display_to_id: dict[str, int] = {}
    for raw_name, cal in zip(names, calories):
        if not raw_name:
            continue
        name, unit = parse_ingredient_label(raw_name)
        row = (
            sb.table("ingredients")
            .insert(
                {
                    "name": name,
                    "unit": unit,
                    "calories_per_unit": float(cal) if cal else 0,
                }
            )
            .execute()
            .data[0]
        )
        display_to_id[raw_name] = int(row["id"])

    print(f"Imported {len(display_to_id)} ingredients.")

    # --- Recipes ---
    headers = recipes_sheet.row_values(1)
    recipe_name_to_id: dict[str, int] = {}

    for j, header in enumerate(headers, start=1):
        if j % 2 == 0 or not header:
            continue

        amounts = recipes_sheet.col_values(j)[1:]
        ing_names = recipes_sheet.col_values(j + 1)[1:]
        ingredient_rows, instructions = parse_recipe_columns(amounts, ing_names)

        recipe_row = (
            sb.table("recipes")
            .insert({"name": header, "instructions": instructions})
            .execute()
            .data[0]
        )
        recipe_id = int(recipe_row["id"])
        recipe_name_to_id[header] = recipe_id

        for ing_name, amount in ingredient_rows:
            if ing_name not in display_to_id:
                print(f"  Warning: unknown ingredient {ing_name!r} in {header}, skipping.")
                continue
            sb.table("recipe_ingredients").insert(
                {
                    "recipe_id": recipe_id,
                    "ingredient_id": display_to_id[ing_name],
                    "amount": float(amount) if amount else 0,
                }
            ).execute()

    print(f"Imported {len(recipe_name_to_id)} recipes.")

    # --- Meal selection ---
    meal_names = meal_sheet.col_values(1)
    for i, meal_name in enumerate(meal_names, start=1):
        if not meal_name:
            break
        if meal_name not in recipe_name_to_id:
            print(f"  Warning: meal {meal_name!r} not found in recipes, skipping.")
            continue
        sb.table("meal_selection").insert(
            {"position": i, "recipe_id": recipe_name_to_id[meal_name]}
        ).execute()

    print(f"Imported meal selection ({len([m for m in meal_names if m])} rows).")

    # --- Other items (Next Trip col D) ---
    other = next_trip_sheet.col_values(4)[1:]
    pos = 0
    for item in other:
        if not item:
            break
        pos += 1
        sb.table("other_items").insert({"position": pos, "name": item}).execute()

    print(f"Imported {pos} other items.")
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
