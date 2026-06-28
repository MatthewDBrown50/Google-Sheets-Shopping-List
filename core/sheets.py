"""Helpers for reading recipe data from the Google Sheets Recipes layout."""

from __future__ import annotations


def parse_recipe_columns(
    amounts: list[str | int | float | None],
    ingredient_names: list[str | None],
) -> tuple[list[tuple[str, str]], str]:
    """Split a Recipes-sheet column pair into ingredient rows and instruction text.

    Each recipe uses two columns: amounts (odd) and ingredient names (even).
    Ingredient rows run until the first blank ingredient name; remaining non-empty
    cells in either column are treated as instructions (one paragraph per row).
    """
    max_len = max(len(amounts), len(ingredient_names))
    amounts = list(amounts) + [""] * (max_len - len(amounts))
    ingredient_names = list(ingredient_names) + [""] * (max_len - len(ingredient_names))

    ingredient_rows: list[tuple[str, str]] = []
    instruction_lines: list[str] = []
    past_ingredients = False

    for amount, name in zip(amounts, ingredient_names):
        name_str = str(name).strip() if name is not None else ""
        amount_str = str(amount).strip() if amount is not None else ""

        if not past_ingredients:
            if not name_str:
                past_ingredients = True
                continue
            ingredient_rows.append((name_str, amount_str))
            continue

        line_parts = [part for part in (name_str, amount_str) if part]
        if line_parts:
            instruction_lines.append(" ".join(line_parts))

    return ingredient_rows, "\n".join(instruction_lines).strip()
