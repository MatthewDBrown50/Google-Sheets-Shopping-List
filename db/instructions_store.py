"""Local recipe instruction overlay (used until Supabase column is migrated)."""

from __future__ import annotations

import json
from pathlib import Path

INSTRUCTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "recipe_instructions.json"


def load_instruction_overrides() -> dict[str, str]:
    if not INSTRUCTIONS_PATH.is_file():
        return {}
    return json.loads(INSTRUCTIONS_PATH.read_text(encoding="utf-8"))


def save_instruction_override(recipe_name: str, instructions: str) -> None:
    data = load_instruction_overrides()
    clean_name = recipe_name.strip()
    clean_text = instructions.strip()
    if clean_text:
        data[clean_name] = clean_text
    else:
        data.pop(clean_name, None)
    INSTRUCTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    INSTRUCTIONS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def remove_instruction_override(recipe_name: str) -> None:
    save_instruction_override(recipe_name, "")


def recipe_instructions(recipe) -> str:
    if recipe is None:
        return ""
    stored = getattr(recipe, "instructions", "") or ""
    if stored.strip():
        return stored
    return load_instruction_overrides().get(getattr(recipe, "name", ""), "")
