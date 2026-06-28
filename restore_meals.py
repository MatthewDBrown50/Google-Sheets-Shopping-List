"""Restore original Meal_Selection and regenerate."""
import os
import subprocess
import sys

import gspread
from google.oauth2.service_account import Credentials

ORIGINAL_MEALS = [
    "Curry Lentil & Vegetable Soup",
    "Bean & Broccoli Salad",
    "Calabacitas a la Mexicana",
    "Butternut Squash Broccoli Cheddar Chicken Couscous",
]

creds = Credentials.from_service_account_file(
    os.getenv("SHOPPING_LIST_CREDENTIALS"),
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ],
)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.getenv("SHOPPING_LIST_WORKBOOK_ID")).worksheet("Meal_Selection")
sheet.batch_clear(["A1:A20"])
sheet.update(f"A1:A{len(ORIGINAL_MEALS)}", [[m] for m in ORIGINAL_MEALS])
subprocess.run([sys.executable, "main.py"], check=True)
print("Restored original meals and regenerated.")
