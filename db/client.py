"""Supabase data access layer."""

from __future__ import annotations

import os
from typing import Any

from postgrest.exceptions import APIError
from supabase import Client, create_client

from db.config import load_config
from db.instructions_store import load_instruction_overrides, save_instruction_override
from core.models import Ingredient, Recipe, RecipeIngredient


def get_client() -> Client:
    load_config()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_KEY environment variables (or Streamlit secrets)."
        )
    return create_client(url, key)


def _ingredient_from_row(row: dict[str, Any]) -> Ingredient:
    return Ingredient(
        id=int(row["id"]),
        name=row["name"],
        unit=row.get("unit") or "",
        calories_per_unit=float(row.get("calories_per_unit") or 0),
        location=row.get("location") or "",
    )


def fetch_ingredients(client: Client) -> list[Ingredient]:
    rows = client.table("ingredients").select("*").order("name").execute().data or []
    return [_ingredient_from_row(r) for r in rows]


def fetch_recipes(client: Client) -> list[Recipe]:
    recipe_rows = client.table("recipes").select("*").order("name").execute().data or []
    instruction_overrides = load_instruction_overrides()
    line_rows = (
        client.table("recipe_ingredients").select("recipe_id, ingredient_id, amount").execute().data
        or []
    )
    lines_by_recipe: dict[int, list[RecipeIngredient]] = {}
    for row in line_rows:
        rid = int(row["recipe_id"])
        lines_by_recipe.setdefault(rid, []).append(
            RecipeIngredient(ingredient_id=int(row["ingredient_id"]), amount=float(row["amount"]))
        )

    recipes: list[Recipe] = []
    for r in recipe_rows:
        name = r["name"]
        instructions = (r.get("instructions") or "").strip() or instruction_overrides.get(name, "")
        recipes.append(
            Recipe(
                id=int(r["id"]),
                name=name,
                instructions=instructions,
                ingredients=lines_by_recipe.get(int(r["id"]), []),
            )
        )
    return recipes


def fetch_meal_selection(client: Client) -> list[int]:
    rows = (
        client.table("meal_selection").select("recipe_id").order("position").execute().data or []
    )
    return [int(r["recipe_id"]) for r in rows]


def fetch_other_items(client: Client) -> list[str]:
    rows = client.table("other_items").select("name").order("position").execute().data or []
    return [r["name"] for r in rows]


def save_meal_selection(client: Client, recipe_ids: list[int]) -> None:
    client.table("meal_selection").delete().neq("position", -1).execute()
    if not recipe_ids:
        return
    client.table("meal_selection").insert(
        [{"position": i + 1, "recipe_id": rid} for i, rid in enumerate(recipe_ids)]
    ).execute()


def save_other_items(client: Client, names: list[str]) -> None:
    client.table("other_items").delete().neq("position", -1).execute()
    cleaned = [n.strip() for n in names if n and str(n).strip()]
    if not cleaned:
        return
    client.table("other_items").insert(
        [{"position": i + 1, "name": name} for i, name in enumerate(cleaned)]
    ).execute()


def fetch_recipe_names(client: Client) -> list[tuple[int, str]]:
    rows = client.table("recipes").select("id, name").order("name").execute().data or []
    return [(int(r["id"]), r["name"]) for r in rows]


def create_ingredient(
    client: Client,
    name: str,
    unit: str,
    calories_per_unit: float,
    location: str = "",
) -> int:
    row = (
        client.table("ingredients")
        .insert(
            {
                "name": name.strip(),
                "unit": unit.strip(),
                "location": location.strip(),
                "calories_per_unit": calories_per_unit,
            }
        )
        .execute()
        .data[0]
    )
    return int(row["id"])


def update_ingredient(
    client: Client,
    ingredient_id: int,
    name: str,
    unit: str,
    calories_per_unit: float,
    location: str = "",
) -> None:
    client.table("ingredients").update(
        {
            "name": name.strip(),
            "unit": unit.strip(),
            "location": location.strip(),
            "calories_per_unit": calories_per_unit,
        }
    ).eq("id", ingredient_id).execute()


def delete_ingredient(client: Client, ingredient_id: int) -> None:
    client.table("ingredients").delete().eq("id", ingredient_id).execute()


def _recipe_payload(name: str, instructions: str) -> dict[str, str]:
    payload = {"name": name.strip()}
    if instructions.strip():
        payload["instructions"] = instructions.strip()
    return payload


def _save_recipe_instructions(
    client: Client,
    recipe_id: int,
    recipe_name: str,
    instructions: str,
) -> None:
    save_instruction_override(recipe_name, instructions)
    try:
        client.table("recipes").update(
            {"instructions": instructions.strip()}
        ).eq("id", recipe_id).execute()
    except APIError:
        pass


def create_recipe(
    client: Client,
    name: str,
    lines: list[RecipeIngredient],
    instructions: str = "",
) -> int:
    clean_name = name.strip()
    clean_instructions = instructions.strip()
    try:
        row = (
            client.table("recipes")
            .insert(_recipe_payload(clean_name, clean_instructions))
            .execute()
            .data[0]
        )
    except APIError:
        row = client.table("recipes").insert({"name": clean_name}).execute().data[0]
    recipe_id = int(row["id"])
    _save_recipe_instructions(client, recipe_id, clean_name, clean_instructions)
    _replace_recipe_ingredients(client, recipe_id, lines)
    return recipe_id


def update_recipe(
    client: Client,
    recipe_id: int,
    name: str,
    lines: list[RecipeIngredient],
    instructions: str = "",
) -> None:
    clean_name = name.strip()
    clean_instructions = instructions.strip()
    try:
        client.table("recipes").update(
            _recipe_payload(clean_name, clean_instructions)
        ).eq("id", recipe_id).execute()
    except APIError:
        client.table("recipes").update({"name": clean_name}).eq("id", recipe_id).execute()
    _save_recipe_instructions(client, recipe_id, clean_name, clean_instructions)
    _replace_recipe_ingredients(client, recipe_id, lines)


def delete_recipe(client: Client, recipe_id: int) -> None:
    client.table("recipes").delete().eq("id", recipe_id).execute()


def _replace_recipe_ingredients(
    client: Client,
    recipe_id: int,
    lines: list[RecipeIngredient],
) -> None:
    client.table("recipe_ingredients").delete().eq("recipe_id", recipe_id).execute()
    merged: dict[int, float] = {}
    for line in lines:
        if line.amount <= 0:
            continue
        merged[line.ingredient_id] = merged.get(line.ingredient_id, 0) + line.amount
    if not merged:
        return
    client.table("recipe_ingredients").insert(
        [
            {"recipe_id": recipe_id, "ingredient_id": iid, "amount": amount}
            for iid, amount in merged.items()
        ]
    ).execute()
