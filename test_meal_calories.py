"""Change Meal_Selection, run generator, verify calorie columns."""
import math
import os
import subprocess
import sys
import time

import gspread
from google.oauth2.service_account import Credentials

TARGET_CALORIES = 600
WORKBOOK_ID = os.getenv("SHOPPING_LIST_WORKBOOK_ID")


def connect():
    creds = Credentials.from_service_account_file(
        os.getenv("SHOPPING_LIST_CREDENTIALS"),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(creds)
    wb = client.open_by_key(WORKBOOK_ID)
    return wb.worksheet("Meal_Selection"), wb.worksheet("Recipes")


def get_recipe_names(recipes_sheet):
    headers = recipes_sheet.row_values(1)
    return [h for j, h in enumerate(headers, start=1) if j % 2 == 1 and h]


def read_meals(meal_sheet):
    return meal_sheet.col_values(1)


def set_meals(meal_sheet, recipes):
    meal_sheet.batch_clear(["A1:A20"])
    if recipes:
        meal_sheet.update(
            range_name=f"A1:A{len(recipes)}",
            values=[[r] for r in recipes],
        )


def run_generator():
    result = subprocess.run(
        [sys.executable, "main.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("main.py stderr:", result.stderr)
        print("main.py stdout:", result.stdout)
        result.check_returncode()


def verify_row(meal_sheet, row, recipes_sheet, ingredients_dict):
    recipe = meal_sheet.cell(row, 1).value
    if not recipe:
        return True, "empty"

    headers = recipes_sheet.row_values(1)
    col = None
    for j, header in enumerate(headers, start=1):
        if j % 2 == 0:
            continue
        if header == "":
            return False, "blank recipe header"
        if header == recipe:
            col = j
            break
    if not col:
        return False, f"recipe not found: {recipe}"

    amounts = recipes_sheet.col_values(col)[1:]
    names = recipes_sheet.col_values(col + 1)[1:]

    total = 0
    for name, amount in zip(names, amounts):
        if not name:
            break
        amt = float(amount) if amount else 0.0
        cal = float(ingredients_dict.get(name, 0) or 0)
        total += round(amt * cal)

    servings = math.ceil(total / (TARGET_CALORIES + 50)) if total else 0
    per = round(total / servings) if servings else 0

    b = meal_sheet.cell(row, 2).value or ""
    c = meal_sheet.cell(row, 3).value or ""
    d = meal_sheet.cell(row, 4).value or ""

    ok = (
        str(total) in b
        and str(servings) in c
        and str(per) in d
    )
    detail = f"{recipe}: total={total}, servings={servings}, per={per} | sheet B={b!r} C={c!r} D={d!r}"
    return ok, detail


def load_ingredients(wb):
    sheet = wb.worksheet("Ingredients")
    names = sheet.col_values(1)
    cals = sheet.col_values(2)
    return {n: c for n, c in zip(names, cals) if n}


def main():
    meal_sheet, recipes_sheet = connect()
    wb = meal_sheet.spreadsheet
    ingredients = load_ingredients(wb)
    all_recipes = get_recipe_names(recipes_sheet)
    original = [r for r in read_meals(meal_sheet) if r]

    test_cases = [
        [all_recipes[0]],
        [all_recipes[1], all_recipes[2]],
        all_recipes[:4],
        original,
    ]

    print("Testing meal combinations...")
    failed = 0
    for i, meals in enumerate(test_cases, start=1):
        print(f"\n--- Test {i}: {meals} ---")
        set_meals(meal_sheet, meals)
        time.sleep(12)
        run_generator()
        for row in range(1, len(meals) + 1):
            ok, detail = verify_row(meal_sheet, row, recipes_sheet, ingredients)
            status = "OK" if ok else "FAIL"
            print(f"  Row {row} [{status}]: {detail}")
            if not ok:
                failed += 1

    print(f"\n{'All tests passed' if failed == 0 else f'{failed} test(s) failed'}")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
