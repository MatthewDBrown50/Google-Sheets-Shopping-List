import os
import sys
import math
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
error_reporting_sheet = client.open_by_key(workbook_id).worksheet('Error Reporting')

##############################################
### GENERATE INGREDIENTS MASTER DICTIONARY ###
##############################################

full_ingredients_list = ingredients_sheet.col_values(1)
ingredients_calories_list = ingredients_sheet.col_values(2)
ingredients_master_dictionary = dict(zip(full_ingredients_list, ingredients_calories_list))

#########################################
### GENERATE SHOPPING LIST DICTIONARY ###
#########################################

error_messages = []

shopping_list = {}

# Get recipe names from column A of meal_selection_sheet
recipe_names = meal_selection_sheet.col_values(1)

# Iterate through recipe names
for i, recipe_name in enumerate(recipe_names, start=1):

    recipe_calories = 0

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
            error_messages.append(f'FAILED TO FIND RECIPE "{recipe_name}" IN recipes_sheet at column {j}! Terminating script...')
            sys.exit()

        # If the header value matches the target recipe name, return the column index
        elif header == recipe_name:
            recipe_col_index = j
            break

    # Get all the ingredients (and their amounts) for the recipe from recipes_sheet
    ingredient_amounts = recipes_sheet.col_values(recipe_col_index)[1:]
    ingredient_names = recipes_sheet.col_values(recipe_col_index + 1)[1:]

    # Iterate through the ingredients in the recipe
    for name, amount in zip(ingredient_names, ingredient_amounts):

        ingredient_calories = 0

        # If we've reached a blank ingredient name, break
        if not name:
            break

        # If we can't find an amount for the ingredient, then we probably have an empty field
        if not amount:
            error_messages.append(f'NO AMOUNT LISTED FOR "{name}" in "{recipe_name}"')

        # Add the ingredient (and the amount) to the shopping list
        amount = float(amount)

        if name in shopping_list:
            shopping_list[name] += amount
        else:
            shopping_list[name] = amount

        # Retrieve the calories for this ingredient from the ingredients master dictionary
        if name in ingredients_master_dictionary:
            ingredient_calories = ingredients_master_dictionary[name]
        else:
            error_messages.append(f'Could not find ingredient "{name}" in the ingredients master dictionary that was '
                                  f'generated from the "Ingredients" worksheet. Defaulting to 0 calories for this '
                                  f'ingredient.')

        # Add the calories for this ingredient (in the called for amount) to recipe_calories
        recipe_calories += round(amount * float(ingredient_calories))

    # Add the total calories for the recipe to column B in meal_selection_sheet
    meal_selection_sheet.update_cell(i,2, f'Total calories in recipe: {recipe_calories}')

    # Portion into servings of no more than 450 calories and report servings count in column C of meal_selection_sheet
    number_of_servings = math.ceil(recipe_calories/450)
    meal_selection_sheet.update_cell(i,3, f'Servings: {number_of_servings}')

    # Report calories per serving in Column D of meal_selection_sheet
    calories_per_serving = round(recipe_calories/number_of_servings)
    meal_selection_sheet.update_cell(i,4, f'Calories per serving: {calories_per_serving}')

#################################
### REPLACE LIST IN WORKSHEET ###
#################################

# Clear previous list from sheet
next_trip_sheet.batch_clear(["A:B"])

# Convert shopping_list dict into rows for the sheet
rows = [[amount, name] for name, amount in shopping_list.items()]

# Sort by ingredient name
rows.sort(key=lambda x: x[1])

# Write headers
next_trip_sheet.update(
    range_name='A1:B1',
    values=[['Amt', 'Ingredient']]
)

# Write data starting at A2
if rows:
    next_trip_sheet.update(
        range_name=f'A2:B{len(rows) + 1}',
        values=rows
    )

################################################
### ADD 'OTHER ITEMS' TO THE END OF THE LIST ###
################################################

other_things_list = next_trip_sheet.col_values(4)[1:]

next_empty_cell = len(rows) + 2

for other_thing in other_things_list:
    if not other_thing:
        break

    next_trip_sheet.update_cell(next_empty_cell, 2, other_thing)
    next_empty_cell += 1

##############################################
### REPORT ERRORS TO error_reporting_sheet ###
##############################################

error_reporting_sheet.clear()

for i in range(len(error_messages)):
    error_reporting_sheet.update_cell(i+1, 1, error_messages[i])



