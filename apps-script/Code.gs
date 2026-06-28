/**
 * Shopping List Generator — Google Apps Script
 *
 * Primary way to generate the shopping list (including from iPhone).
 * Automatically runs when you change a meal in Meal_Selection column A.
 *
 * ONE-TIME SETUP
 * 1. Open your spreadsheet → Extensions → Apps Script
 * 2. Paste this file (or use clasp push — see .clasp.json.example)
 * 3. Run generateShoppingList once from the editor and approve permissions
 * 4. onEdit registers automatically (simple trigger)
 *
 * IPHONE VERIFICATION
 * 1. Open the Google Sheets app → Meal_Selection tab
 * 2. Change a meal dropdown in column A
 * 3. Open Next Trip — list should update within a few seconds
 *
 * PC FALLBACK: see main.py in the ShoppingList repo (requires service account env vars)
 */

const TARGET_CALORIES = 600;

function getColumnValues(sheet, column, startRow) {
  const lastRow = sheet.getLastRow();
  if (lastRow < startRow) return [];
  const numRows = lastRow - startRow + 1;
  return sheet.getRange(startRow, column, numRows, 1).getValues().flat();
}

/**
 * Simple trigger: regenerate when a meal is selected on Meal_Selection column A.
 * Ignores edits to columns B–D (written by this script) to avoid infinite loops.
 */
function onEdit(e) {
  if (!e) return;
  const sheet = e.range.getSheet();
  if (sheet.getName() !== 'Meal_Selection') return;
  if (e.range.getColumn() !== 1) return;
  generateShoppingList();
}

function generateShoppingList() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const nextTripSheet = ss.getSheetByName('Next Trip');
  const mealSelectionSheet = ss.getSheetByName('Meal_Selection');
  const recipesSheet = ss.getSheetByName('Recipes');
  const ingredientsSheet = ss.getSheetByName('Ingredients');
  const errorReportingSheet = ss.getSheetByName('Error Reporting');

  const errorMessages = [];
  const shoppingList = {};

  // --- Ingredients master dictionaries ---
  const ingredientsLastRow = ingredientsSheet.getLastRow();
  if (ingredientsLastRow < 1) {
    writeErrors(errorReportingSheet, ['Ingredients worksheet is empty.']);
    return;
  }

  const ingredientsData = ingredientsSheet.getRange(1, 1, ingredientsLastRow, 3).getValues();
  const ingredientsMasterDictionary = {};
  const ingredientsCategoryDictionary = {};

  for (let i = 0; i < ingredientsData.length; i++) {
    const name = String(ingredientsData[i][0] || '').trim();
    if (!name) continue;
    ingredientsMasterDictionary[name] = ingredientsData[i][1];
    const category = ingredientsData[i][2];
    ingredientsCategoryDictionary[name] =
      category && String(category).trim() ? String(category).trim() : 'Uncategorized';
  }

  // --- Process selected meals ---
  const recipeNames = mealSelectionSheet.getRange(1, 1, mealSelectionSheet.getLastRow(), 1)
    .getValues()
    .flat();

  const recipeHeaders = recipesSheet.getRange(1, 1, 1, recipesSheet.getLastColumn()).getValues()[0];

  for (let i = 0; i < recipeNames.length; i++) {
    const rowIndex = i + 1;
    const recipeName = recipeNames[i];

    if (!recipeName || String(recipeName).trim() === '') {
      break;
    }

    let recipeColIndex = 0;

    for (let j = 0; j < recipeHeaders.length; j++) {
      const colNum = j + 1;

      if (colNum % 2 === 0) {
        continue;
      }

      const header = recipeHeaders[j];

      if (header === '' || header === null) {
        errorMessages.push(
          'FAILED TO FIND RECIPE "' + recipeName + '" IN recipes_sheet at column ' + colNum + '! Terminating script...'
        );
        writeErrors(errorReportingSheet, errorMessages);
        return;
      }

      if (header === recipeName) {
        recipeColIndex = colNum;
        break;
      }
    }

    if (recipeColIndex === 0) {
      errorMessages.push('FAILED TO FIND RECIPE "' + recipeName + '" IN recipes_sheet!');
      writeErrors(errorReportingSheet, errorMessages);
      return;
    }

    const ingredientAmounts = getColumnValues(recipesSheet, recipeColIndex, 2);
    const ingredientNames = getColumnValues(recipesSheet, recipeColIndex + 1, 2);

    let recipeCalories = 0;

    for (let k = 0; k < ingredientNames.length; k++) {
      const name = ingredientNames[k];
      let amount = ingredientAmounts[k];

      if (!name || String(name).trim() === '') {
        break;
      }

      const nameStr = String(name);

      if (amount === '' || amount === null) {
        errorMessages.push('NO AMOUNT LISTED FOR "' + nameStr + '" in "' + recipeName + '"');
      }

      amount = parseFloat(amount);
      if (isNaN(amount)) {
        amount = 0;
      }

      if (shoppingList[nameStr] !== undefined) {
        shoppingList[nameStr] += amount;
      } else {
        shoppingList[nameStr] = amount;
      }

      let ingredientCalories = 0;
      if (ingredientsMasterDictionary[nameStr] !== undefined) {
        ingredientCalories = parseFloat(ingredientsMasterDictionary[nameStr]) || 0;
      } else {
        errorMessages.push(
          'Could not find ingredient "' + nameStr + '" in the ingredients master dictionary that was ' +
          'generated from the "Ingredients" worksheet. Defaulting to 0 calories for this ingredient.'
        );
      }

      recipeCalories += Math.round(amount * ingredientCalories);
    }

    const numberOfServings = Math.ceil(recipeCalories / (TARGET_CALORIES + 50));
    const caloriesPerServing = Math.round(recipeCalories / numberOfServings);

    mealSelectionSheet.getRange(rowIndex, 2).setValue('Total calories in recipe: ' + recipeCalories);
    mealSelectionSheet.getRange(rowIndex, 3).setValue('Servings: ' + numberOfServings);
    mealSelectionSheet.getRange(rowIndex, 4).setValue('Calories per serving: ' + caloriesPerServing);
  }

  // --- Write Next Trip shopping list ---
  const otherThingsList = getColumnValues(nextTripSheet, 4, 2);

  nextTripSheet.getRange('A:C').clearContent();

  const rows = [];
  for (const name in shoppingList) {
    if (Object.prototype.hasOwnProperty.call(shoppingList, name)) {
      rows.push([
        shoppingList[name],
        name,
        ingredientsCategoryDictionary[name] || 'Uncategorized'
      ]);
    }
  }

  rows.sort(function (a, b) {
    const catCompare = String(a[2]).toLowerCase().localeCompare(String(b[2]).toLowerCase());
    if (catCompare !== 0) return catCompare;
    return String(a[1]).toLowerCase().localeCompare(String(b[1]).toLowerCase());
  });

  nextTripSheet.getRange(1, 1, 1, 3).setValues([['Amt', 'Ingredient', 'Category']]);

  if (rows.length > 0) {
    nextTripSheet.getRange(2, 1, rows.length, 3).setValues(rows);
  }

  // --- Append manual Other items from column D ---
  let nextEmptyCell = rows.length + 2;

  for (let i = 0; i < otherThingsList.length; i++) {
    const otherThing = otherThingsList[i];
    if (!otherThing || String(otherThing).trim() === '') {
      break;
    }

    nextTripSheet.getRange(nextEmptyCell, 2).setValue(otherThing);
    nextTripSheet.getRange(nextEmptyCell, 3).setValue('Other');
    nextEmptyCell++;
  }

  writeErrors(errorReportingSheet, errorMessages);
}

function writeErrors(errorReportingSheet, errorMessages) {
  errorReportingSheet.clear();
  if (errorMessages.length === 0) return;
  const errorRows = errorMessages.map(function (msg) {
    return [msg];
  });
  errorReportingSheet.getRange(1, 1, errorRows.length, 1).setValues(errorRows);
}
