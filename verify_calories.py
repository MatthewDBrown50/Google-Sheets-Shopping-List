"""Verify Meal_Selection calorie columns against independent calculation."""
import math
import os
import re
import gspread
from google.oauth2.service_account import Credentials

TARGET_CALORIES = 600


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
    return {
        "meal_selection": wb.worksheet("Meal_Selection"),
        "recipes": wb.worksheet("Recipes"),
        "ingredients": wb.worksheet("Ingredients"),
        "errors": wb.worksheet("Error Reporting"),
    }


def load_ingredients(ingredients_sheet):
    names = ingredients_sheet.col_values(1)
    cals = ingredients_sheet.col_values(2)
    return {n: float(c) if c else 0.0 for n, c in zip(names, cals) if n}


def find_recipe_col(recipe_name, recipe_headers):
    for j, header in enumerate(recipe_headers, start=1):
        if j % 2 == 0:
            continue
        if header == "":
            return None, f"blank header at column {j}"
        if header == recipe_name:
            return j, None
    return None, "recipe not found"


def calc_recipe_calories(recipe_name, recipes_sheet, ingredients_dict):
    headers = recipes_sheet.row_values(1)
    col, err = find_recipe_col(recipe_name, headers)
    if err:
        return None, err, []

    amounts = recipes_sheet.col_values(col)[1:]
    names = recipes_sheet.col_values(col + 1)[1:]

    total = 0
    breakdown = []
    for name, amount in zip(names, amounts):
        if not name:
            break
        amt = float(amount) if amount else 0.0
        cal_per = ingredients_dict.get(name, 0.0)
        contrib = round(amt * cal_per)
        total += contrib
        breakdown.append((name, amt, cal_per, contrib))

    servings = math.ceil(total / (TARGET_CALORIES + 50)) if total > 0 else 0
    per_serving = round(total / servings) if servings else 0
    return {
        "total": total,
        "servings": servings,
        "per_serving": per_serving,
    }, None, breakdown


def parse_meal_selection_cell(value, kind):
    if not value:
        return None
    s = str(value)
    if kind == "total":
        m = re.search(r"Total calories in recipe:\s*(\d+)", s)
    elif kind == "servings":
        m = re.search(r"Servings:\s*(\d+)", s)
    elif kind == "per_serving":
        m = re.search(r"Calories per serving:\s*(\d+)", s)
    else:
        return None
    return int(m.group(1)) if m else None


def verify(sheets):
    ingredients = load_ingredients(sheets["ingredients"])
    rows = sheets["meal_selection"].get_all_values()
    issues = []
    results = []

    for i, row in enumerate(rows, start=1):
        recipe = row[0] if row else ""
        if not recipe:
            break

        expected, err, breakdown = calc_recipe_calories(
            recipe, sheets["recipes"], ingredients
        )
        if err:
            issues.append(f"Row {i} ({recipe}): {err}")
            continue

        actual_total = parse_meal_selection_cell(row[1] if len(row) > 1 else "", "total")
        actual_servings = parse_meal_selection_cell(row[2] if len(row) > 2 else "", "servings")
        actual_per = parse_meal_selection_cell(row[3] if len(row) > 3 else "", "per_serving")

        row_ok = True
        mismatches = []
        for label, exp, act in [
            ("total", expected["total"], actual_total),
            ("servings", expected["servings"], actual_servings),
            ("per_serving", expected["per_serving"], actual_per),
        ]:
            if act is None:
                mismatches.append(f"{label}: sheet empty, expected {exp}")
                row_ok = False
            elif exp != act:
                mismatches.append(f"{label}: sheet={act}, expected={exp}")
                row_ok = False

        results.append({
            "row": i,
            "recipe": recipe,
            "expected": expected,
            "actual": {"total": actual_total, "servings": actual_servings, "per_serving": actual_per},
            "ok": row_ok,
            "breakdown": breakdown,
            "mismatches": mismatches,
        })
        if mismatches:
            issues.extend([f"Row {i} ({recipe}): {m}" for m in mismatches])

    return results, issues


def print_report(results, issues):
    print("=" * 60)
    print("MEAL_SELECTION CALORIE VERIFICATION")
    print("=" * 60)
    for r in results:
        status = "OK" if r["ok"] else "MISMATCH"
        print(f"\nRow {r['row']}: {r['recipe']} [{status}]")
        e = r["expected"]
        a = r["actual"]
        print(f"  Expected: total={e['total']}, servings={e['servings']}, per_serving={e['per_serving']}")
        print(f"  Sheet:    total={a['total']}, servings={a['servings']}, per_serving={a['per_serving']}")
        if r["breakdown"]:
            print("  Breakdown:")
            for name, amt, cal, contrib in r["breakdown"][:8]:
                print(f"    {amt} x {name} @ {cal}/unit => {contrib}")
            if len(r["breakdown"]) > 8:
                print(f"    ... +{len(r['breakdown']) - 8} more ingredients")
        for m in r["mismatches"]:
            print(f"  !! {m}")

    print("\n" + "=" * 60)
    if issues:
        print(f"FAILED: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("PASSED: All rows match expected calculations")
    print("=" * 60)
    return len(issues) == 0


def list_recipes(sheets):
    headers = sheets["recipes"].row_values(1)
    return [h for j, h in enumerate(headers, start=1) if j % 2 == 1 and h]


if __name__ == "__main__":
    import sys

    sheets = connect()
    if len(sys.argv) > 1 and sys.argv[1] == "list-recipes":
        for name in list_recipes(sheets):
            print(name)
        sys.exit(0)

    results, issues = verify(sheets)
    ok = print_report(results, issues)
    sys.exit(0 if ok else 1)
