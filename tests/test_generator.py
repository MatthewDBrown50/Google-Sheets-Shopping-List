"""Unit tests for core/generator.py (no database required)."""

import math
import unittest

from core.generator import TARGET_CALORIES, SERVING_CALORIE_BUFFER, generate_shopping_list
from core.models import Ingredient, Recipe, RecipeIngredient


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.ingredients = [
            Ingredient(1, "olive oil", "Tbsp", 120),
            Ingredient(2, "carrots", "ct", 25),
            Ingredient(3, "chickpeas", "can", 385),
        ]
        self.recipe_a = Recipe(
            id=10,
            name="Soup A",
            ingredients=[
                RecipeIngredient(1, 2),
                RecipeIngredient(2, 3),
            ],
        )
        self.recipe_b = Recipe(
            id=11,
            name="Soup B",
            ingredients=[
                RecipeIngredient(1, 1),
                RecipeIngredient(3, 1),
            ],
        )

    def test_single_recipe_calories(self):
        result = generate_shopping_list(
            self.ingredients, [self.recipe_a], [10], []
        )
        self.assertEqual(len(result.meals), 1)
        # 2*120 + 3*25 = 240 + 75 = 315
        self.assertEqual(result.meals[0].total_calories, 315)
        self.assertEqual(
            result.meals[0].servings,
            math.ceil(315 / (TARGET_CALORIES + SERVING_CALORIE_BUFFER)),
        )

    def test_aggregates_across_recipes(self):
        result = generate_shopping_list(
            self.ingredients, [self.recipe_a, self.recipe_b], [10, 11], []
        )
        amounts = {r.display_name: r.amount for r in result.shopping_list if not r.is_other}
        self.assertEqual(amounts["olive oil (Tbsp)"], 3)  # 2 + 1
        self.assertEqual(amounts["carrots (ct)"], 3)
        self.assertEqual(amounts["chickpeas (can)"], 1)

    def test_sorts_by_name(self):
        result = generate_shopping_list(
            self.ingredients, [self.recipe_a, self.recipe_b], [10, 11], []
        )
        names = [r.display_name for r in result.shopping_list if not r.is_other]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_other_items_appended(self):
        result = generate_shopping_list(
            self.ingredients, [self.recipe_a], [10], ["paper towels", "soap"]
        )
        others = [r for r in result.shopping_list if r.is_other]
        self.assertEqual(len(others), 2)
        self.assertEqual(others[0].display_name, "paper towels")

    def test_missing_ingredient_reports_error(self):
        bad_recipe = Recipe(
            id=99,
            name="Bad",
            ingredients=[RecipeIngredient(999, 1)],
        )
        result = generate_shopping_list(self.ingredients, [bad_recipe], [99], [])
        self.assertTrue(any("Could not find ingredient" in e for e in result.errors))


if __name__ == "__main__":
    unittest.main()
