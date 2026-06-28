"""Compare Python col_values vs Apps Script getColumnValues simulation for each recipe."""
import math
import os
import sys

import gspread
from google.oauth2.service_account import Credentials

TARGET = 600


def connect():
    creds = Credentials.from_service_account_file(
        os.getenv("SHOPPING_LIST_CREDENTIALS"),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(creds)
    wb = client.open_by_key(os.getenv("SHOPPING_LIST_WORKBOOK_ID"))
    return wb.worksheet("Recipes"), wb.worksheet("Ingredients")


def get_column_values_gas(sheet, column, start_row):
    data = sheet.get_all_values()
    last_row = len(data)
    if last_row < start_row:
        return []
    num_rows = last_row - start_row + 1
    end_row = start_row + num_rows - 1
    out = []
    for r in range(start_row - 1, min(end_row, last_row)):
        row = data[r]
        out.append(row[column - 1] if column - 1 < len(row) else "")
    return out


def col_values_py(sheet, column, start_row):
    vals = sheet.col_values(column)
    return vals[start_row - 1 :]


def find_col(headers, recipe_name):
    for j, header in enumerate(headers, start=1):
        if j % 2 == 0:
            continue
        if not header:
            return None
        if header == recipe_name:
            return j
    return None


def calc_recipe(recipe_name, recipes, ingredients, read_col):
    headers = recipes.row_values(1)
    col = find_col(headers, recipe_name)
    if not col:
        return None

    amounts = read_col(recipes, col, 2)
    names = read_col(recipes, col + 1, 2)

    total = 0
    details = []
    for name, amount in zip(names, amounts):
        if not name or str(name).strip() == "":
            break
        amt = float(amount) if amount else 0.0
        cal = float(ingredients.get(name, 0) or 0)
        c = round(amt * cal)
        total += c
        details.append((name, amt, cal, c))

    servings = math.ceil(total / (TARGET + 50)) if total else 0
    per = round(total / servings) if servings else 0
    return {"total": total, "servings": servings, "per": per, "details": details}


def load_ingredients(sheet):
    names = sheet.col_values(1)
    cals = sheet.col_values(2)
    return {n: c for n, c in zip(names, cals) if n}


def main():
    recipes, ingredients_sheet = connect()
    ingredients = load_ingredients(ingredients_sheet)
    headers = recipes.row_values(1)
    recipe_names = [h for j, h in enumerate(headers, start=1) if j % 2 == 1 and h]

    mismatches = 0
    for name in recipe_names:
        py = calc_recipe(name, recipes, ingredients, col_values_py)
        gas = calc_recipe(name, recipes, ingredients, get_column_values_gas)
        ok = py["total"] == gas["total"]
        status = "OK" if ok else "MISMATCH"
        print(f"{name}: [{status}] python={py['total']} gas_sim={gas['total']}")
        if not ok:
            mismatches += 1
            print(f"  py ingredients: {len(py['details'])}, gas ingredients: {len(gas['details'])}")

    print(f"\n{'All recipes match' if mismatches == 0 else f'{mismatches} recipe(s) differ'}")
    return mismatches == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
