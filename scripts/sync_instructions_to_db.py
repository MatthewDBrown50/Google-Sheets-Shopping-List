"""Sync local recipe instructions to Supabase and reload PostgREST schema cache."""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
import tomllib
from postgrest.exceptions import APIError

from db.client import get_client
from db.config import load_config
from db.instructions_store import load_instruction_overrides

PROJECT_REF = "hocehuebhntykignmjis"


def reload_schema_cache(password: str) -> None:
    conn = psycopg2.connect(
        host=f"db.{PROJECT_REF}.supabase.co",
        port=5432,
        dbname="postgres",
        user="postgres",
        password=password,
        sslmode="require",
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("NOTIFY pgrst, 'reload schema'")
    finally:
        conn.close()


def sync_instructions() -> int:
    load_config()
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    password = tomllib.load(secrets_path.open("rb")).get("SUPABASE_DB_PASSWORD")
    if not password:
        raise RuntimeError("SUPABASE_DB_PASSWORD not found in secrets.toml")

    reload_schema_cache(str(password))
    time.sleep(3)

    sb = get_client()
    updated = 0
    for name, instructions in load_instruction_overrides().items():
        try:
            result = (
                sb.table("recipes")
                .update({"instructions": instructions})
                .eq("name", name)
                .execute()
            )
        except APIError:
            reload_schema_cache(str(password))
            time.sleep(5)
            result = (
                sb.table("recipes")
                .update({"instructions": instructions})
                .eq("name", name)
                .execute()
            )
        if result.data:
            updated += 1
            print(f"  Synced {name!r} ({len(instructions)} chars)")

    return updated


if __name__ == "__main__":
    count = sync_instructions()
    print(f"Sync complete. Updated {count} recipe(s).")
