"""Shopping list and calorie calculations (ported from main.py)."""

from __future__ import annotations

import math
import re
from typing import Iterable

from core.models import (
    GeneratorResult,
    Ingredient,
    MealCalorieResult,
    Recipe,
    ShoppingListRow,
)

TARGET_CALORIES = 600
SERVING_CALORIE_BUFFER = 50

def parse_ingredient_label(label: str) -> tuple[str, str]:
    """Parse 'apple cider vinegar (Tbsp)' into name and unit."""
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", label.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return label.strip(), ""


def build_ingredient_lookup(ingredients: Iterable[Ingredient]) -> dict[int, Ingredient]:
    return {ing.id: ing for ing in ingredients}


def build_display_name_lookup(ingredients: Iterable[Ingredient]) -> dict[str, Ingredient]:
    lookup: dict[str, Ingredient] = {}
    for ing in ingredients:
        lookup[ing.display_name] = ing
    return lookup


def generate_shopping_list(
    ingredients: list[Ingredient],
    recipes: list[Recipe],
    meal_recipe_ids: list[int],
    other_item_names: list[str],
    target_calories: int = TARGET_CALORIES,
) -> GeneratorResult:
    ingredient_by_id = build_ingredient_lookup(ingredients)
    recipe_by_id = {r.id: r for r in recipes}

    errors: list[str] = []
    shopping_amounts: dict[int, float] = {}
    meal_results: list[MealCalorieResult] = []

    for position, recipe_id in enumerate(meal_recipe_ids, start=1):
        recipe = recipe_by_id.get(recipe_id)
        if not recipe:
            errors.append(f'FAILED TO FIND RECIPE id={recipe_id} at position {position}!')
            continue

        recipe_calories = 0

        for line in recipe.ingredients:
            ingredient = ingredient_by_id.get(line.ingredient_id)
            if not ingredient:
                errors.append(
                    f'Could not find ingredient id={line.ingredient_id} in "{recipe.name}". '
                    f'Defaulting to 0 calories.'
                )
                continue

            amount = float(line.amount)
            if amount == 0:
                errors.append(f'NO AMOUNT LISTED FOR "{ingredient.display_name}" in "{recipe.name}"')

            if line.ingredient_id in shopping_amounts:
                shopping_amounts[line.ingredient_id] += amount
            else:
                shopping_amounts[line.ingredient_id] = amount

            recipe_calories += round(amount * float(ingredient.calories_per_unit))

        divisor = target_calories + SERVING_CALORIE_BUFFER
        number_of_servings = math.ceil(recipe_calories / divisor) if recipe_calories > 0 else 0
        calories_per_serving = (
            round(recipe_calories / number_of_servings) if number_of_servings else 0
        )

        meal_results.append(
            MealCalorieResult(
                position=position,
                recipe_name=recipe.name,
                total_calories=recipe_calories,
                servings=number_of_servings,
                calories_per_serving=calories_per_serving,
            )
        )

    rows: list[ShoppingListRow] = []
    for ingredient_id, amount in shopping_amounts.items():
        ingredient = ingredient_by_id[ingredient_id]
        rows.append(
            ShoppingListRow(
                amount=amount,
                display_name=ingredient.display_name,
                location=getattr(ingredient, "location", "") or "",
            )
        )

    rows.sort(key=lambda r: r.display_name.lower())

    for name in other_item_names:
        if not name or not str(name).strip():
            break
        rows.append(
            ShoppingListRow(
                amount=0,
                display_name=str(name).strip(),
                is_other=True,
            )
        )

    return GeneratorResult(meals=meal_results, shopping_list=rows, errors=errors)
