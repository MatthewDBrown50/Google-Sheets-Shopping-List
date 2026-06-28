from dataclasses import dataclass, field


@dataclass
class Ingredient:
    id: int
    name: str
    unit: str
    calories_per_unit: float

    @property
    def display_name(self) -> str:
        if self.unit:
            return f"{self.name} ({self.unit})"
        return self.name


@dataclass
class RecipeIngredient:
    ingredient_id: int
    amount: float


@dataclass
class Recipe:
    id: int
    name: str
    instructions: str = ""
    ingredients: list[RecipeIngredient] = field(default_factory=list)


@dataclass
class MealSelectionRow:
    position: int
    recipe_id: int
    recipe_name: str


@dataclass
class MealCalorieResult:
    position: int
    recipe_name: str
    total_calories: int
    servings: int
    calories_per_serving: int


@dataclass
class ShoppingListRow:
    amount: float
    display_name: str
    is_other: bool = False


@dataclass
class GeneratorResult:
    meals: list[MealCalorieResult]
    shopping_list: list[ShoppingListRow]
    errors: list[str]
