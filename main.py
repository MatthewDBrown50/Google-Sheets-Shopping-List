import os
import sys
import gspread
from google.oauth2.service_account import Credentials

# Use the following command to build to .exe:
    # pyinstaller --onefile main.py

###################################
### AUTHENTICATE GOOGLE ACCOUNT ###
###################################

# Grab path to credentials.json from environmental variable
creds_path = os.getenv("SHOPPING_LIST_CREDENTIALS")

# Define the scope
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load credentials
creds = Credentials.from_service_account_file(
    creds_path,
    scopes=SCOPES
)

# Authorize client
client = gspread.authorize(creds)

######################################
### DEFINE WORKBOOK AND WORKSHEETS ###
######################################

workbook_id = os.getenv("SHOPPING_LIST_WORKBOOK_ID")

next_trip_sheet = client.open_by_key(workbook_id).worksheet('Next Trip')
meal_selection_sheet = client.open_by_key(workbook_id).worksheet('Meal_Selection')
recipes_sheet = client.open_by_key(workbook_id).worksheet('Recipes')
ingredients_sheet = client.open_by_key(workbook_id).worksheet('Ingredients')

##################################
### GENERATE NEW SHOPPING LIST ###
##################################

shopping_list = {}

# Get recipe names from column A of meal_selection_sheet
recipe_names = meal_selection_sheet.col_values(1)

# Iterate through recipe names
for i, recipe_name in enumerate(recipe_names, start=1):

    # If the cell is blank, we've reached the end of the list and can stop iterating
    if not recipe_name:
        break

    recipe_col_index = 0

    recipe_headers = recipes_sheet.row_values(1)

    # Iterate through the column headers in recipes_sheet
    for j, header in enumerate(recipe_headers, start=1):

        # If the column is even, then skip, since even rows are blank due to merged cells
        if j % 2 == 0:
            continue

        # If the column is blank, then we're out of populated columns to search, so report error and terminate script
        if header == "":
            print(f'FAILED TO FIND RECIPE "{recipe_name}" IN recipes_sheet at column {j}! Terminating script...')
            sys.exit()

        # If the header value matches the target recipe name, return the column index
        elif header == recipe_name:
            recipe_col_index = j
            break

    # Get all the ingredients (and their amounts) for the recipe from recipes_sheet
    ingredient_amounts = recipes_sheet.col_values(recipe_col_index)[1:]
    ingredient_names = recipes_sheet.col_values(recipe_col_index + 1)[1:]

    # Add the ingredient amounts to the shopping list
    for name, amount in zip(ingredient_names, ingredient_amounts):
        if not name:
            break

        if not amount:
            print(f'NO AMOUNT LISTED FOR "{name}" in "{recipe_name}"')

        amount = float(amount)

        if name in shopping_list:
            shopping_list[name] += amount
        else:
            shopping_list[name] = amount

#################################
### REPLACE LIST IN WORKSHEET ###
#################################

# Clear previous list from sheet
next_trip_sheet.clear()

# Convert shopping_list dict into rows for the sheet
rows = [[amount, name] for name, amount in shopping_list.items()]

# Sort by ingredient name
rows.sort(key=lambda x: x[1])

# Write headers
next_trip_sheet.update(
    range_name='A1:B1',
    values=[['Amount', 'Ingredient']]
)

# Write data starting at A2
if rows:
    next_trip_sheet.update(
        range_name=f'A2:B{len(rows) + 1}',
        values=rows
    )

