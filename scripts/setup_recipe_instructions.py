"""Add recipes.instructions column (if needed) and import from Google Sheets."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gspread
from google.oauth2.service_account import Credentials
from postgrest.exceptions import APIError

from core.sheets import parse_recipe_columns
from db.client import get_client
from db.config import load_config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

PROJECT_REF = "hocehuebhntykignmjis"
ADD_COLUMN_SQL = (
    "alter table recipes add column if not exists instructions text not null default '';"
)


def _load_secrets() -> dict[str, str]:
    load_config()
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    data: dict[str, str] = {}
    if secrets_path.is_file():
        import tomllib

        with secrets_path.open("rb") as f:
            raw = tomllib.load(f)
        data = {k: str(v) for k, v in raw.items() if v is not None}
    return data


def _db_password_candidates(secrets: dict[str, str]) -> list[str]:
    placeholders = {"your-database-password", "YOUR-PASSWORD", "[YOUR-PASSWORD]"}
    candidates: list[str] = []
    for key in (
        "SUPABASE_DB_PASSWORD",
        "DATABASE_URL",
        "SUPABASE_DB_URL",
        "POSTGRES_PASSWORD",
    ):
        val = os.getenv(key) or secrets.get(key)
        if not val or val in placeholders or val in candidates:
            continue
        candidates.append(val)
    return candidates


def _instructions_column_exists(sb) -> bool:
    try:
        sb.table("recipes").select("instructions").limit(1).execute()
        return True
    except APIError as exc:
        if "instructions" in str(exc).lower():
            return False
        raise


def _run_sql_via_psycopg2(password_or_url: str) -> None:
    import psycopg2

    if password_or_url.startswith("postgres"):
        conn = psycopg2.connect(password_or_url)
    else:
        pooler_regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "eu-west-1",
            "eu-central-1",
            "ap-southeast-1",
        ]
        attempts = [(f"db.{PROJECT_REF}.supabase.co", "postgres", 5432)]
        for region in pooler_regions:
            host = f"aws-0-{region}.pooler.supabase.com"
            attempts.append((host, f"postgres.{PROJECT_REF}", 6543))
            attempts.append((host, f"postgres.{PROJECT_REF}", 5432))

        last_error: Exception | None = None
        conn = None
        for host, user, port in attempts:
            try:
                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    dbname="postgres",
                    user=user,
                    password=password_or_url,
                    sslmode="require",
                    connect_timeout=10,
                )
                break
            except Exception as exc:
                last_error = exc
        if conn is None:
            raise RuntimeError(f"Could not connect to Supabase Postgres: {last_error}")

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(ADD_COLUMN_SQL)
                cur.execute("NOTIFY pgrst, 'reload schema'")
    finally:
        conn.close()


def _run_sql_via_management_api(access_token: str) -> None:
    import httpx

    response = httpx.post(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"query": ADD_COLUMN_SQL},
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Supabase Management API query failed ({response.status_code}): {response.text[:300]}"
        )


def ensure_instructions_column(sb) -> None:
    if _instructions_column_exists(sb):
        print("recipes.instructions column already exists.")
        return

    secrets = _load_secrets()
    access_token = os.getenv("SUPABASE_ACCESS_TOKEN") or secrets.get("SUPABASE_ACCESS_TOKEN")
    if access_token:
        print("Adding recipes.instructions via Supabase Management API...")
        _run_sql_via_management_api(access_token)
        if _instructions_column_exists(sb):
            print("Column added.")
            return

    for candidate in _db_password_candidates(secrets):
        print("Adding recipes.instructions via Postgres connection...")
        try:
            _run_sql_via_psycopg2(candidate)
            if _instructions_column_exists(sb):
                print("Column added.")
                return
        except Exception as exc:
            print(f"  Postgres attempt failed: {exc}")

    if not _db_password_candidates(secrets):
        raise RuntimeError(
            "SUPABASE_DB_PASSWORD is missing or still set to the placeholder value. "
            "Copy your database password from Supabase -> Project Settings -> Database."
        )

    raise RuntimeError(
        "Could not add recipes.instructions automatically. "
        "Run this in the Supabase SQL Editor:\n"
        f"  {ADD_COLUMN_SQL}\n"
        "Or add SUPABASE_DB_PASSWORD or SUPABASE_ACCESS_TOKEN to .streamlit/secrets.toml "
        "and rerun this script."
    )


def backfill_from_sheets(sb) -> int:
    from db.instructions_store import load_instruction_overrides, save_instruction_override

    instruction_overrides = load_instruction_overrides()
    if instruction_overrides:
        updated = 0
        for name, instructions in instruction_overrides.items():
            try:
                result = (
                    sb.table("recipes")
                    .update({"instructions": instructions})
                    .eq("name", name)
                    .execute()
                )
                if result.data:
                    updated += 1
                    print(f"  Synced {name!r} ({len(instructions)} chars)")
            except APIError as exc:
                if "instructions" in str(exc).lower():
                    raise
        if updated:
            return updated

    if not os.getenv("SHOPPING_LIST_CREDENTIALS") or not os.getenv("SHOPPING_LIST_WORKBOOK_ID"):
        return 0

    creds = Credentials.from_service_account_file(
        os.environ["SHOPPING_LIST_CREDENTIALS"],
        scopes=SCOPES,
    )
    recipes_sheet = gspread.authorize(creds).open_by_key(
        os.environ["SHOPPING_LIST_WORKBOOK_ID"]
    ).worksheet("Recipes")
    headers = recipes_sheet.row_values(1)

    updated = 0
    for j, header in enumerate(headers, start=1):
        if j % 2 == 0 or not header:
            continue

        amounts = recipes_sheet.col_values(j)[1:]
        ing_names = recipes_sheet.col_values(j + 1)[1:]
        _, instructions = parse_recipe_columns(amounts, ing_names)
        if not instructions:
            continue

        save_instruction_override(header, instructions)
        try:
            result = (
                sb.table("recipes")
                .update({"instructions": instructions})
                .eq("name", header)
                .execute()
            )
            if result.data:
                updated += 1
        except APIError:
            updated += 1
        print(f"  Imported {header!r} ({len(instructions)} chars)")

    return updated


def main() -> None:
    load_config()
    sb = get_client()
    try:
        ensure_instructions_column(sb)
    except RuntimeError as exc:
        print(exc)
        print("Continuing with local instruction import only...")
    updated = backfill_from_sheets(sb)
    print(f"Backfill complete. Updated {updated} recipe(s).")


if __name__ == "__main__":
    main()
