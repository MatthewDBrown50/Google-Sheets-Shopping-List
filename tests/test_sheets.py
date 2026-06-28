"""Unit tests for core/sheets.py."""

import unittest

from core.sheets import parse_recipe_columns


class ParseRecipeColumnsTests(unittest.TestCase):
    def test_splits_ingredients_and_instructions(self):
        amounts = ["2", "1", "", "Preheat oven to 350.", "Bake 20 minutes."]
        names = [
            "olive oil (Tbsp)",
            "carrots (ct)",
            "",
            "",
            "",
        ]
        rows, instructions = parse_recipe_columns(amounts, names)
        self.assertEqual(
            rows,
            [("olive oil (Tbsp)", "2"), ("carrots (ct)", "1")],
        )
        self.assertEqual(
            instructions,
            "Preheat oven to 350.\nBake 20 minutes.",
        )

    def test_ingredients_only(self):
        rows, instructions = parse_recipe_columns(["1"], ["butter (Tbsp)"])
        self.assertEqual(rows, [("butter (Tbsp)", "1")])
        self.assertEqual(instructions, "")

    def test_pads_uneven_column_lengths(self):
        amounts = ["1"]
        names = ["salt (tsp)", "", "Mix well."]
        rows, instructions = parse_recipe_columns(amounts, names)
        self.assertEqual(rows, [("salt (tsp)", "1")])
        self.assertEqual(instructions, "Mix well.")


if __name__ == "__main__":
    unittest.main()
