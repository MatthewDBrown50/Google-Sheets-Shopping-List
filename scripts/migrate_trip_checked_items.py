"""Create trip_checked_items table in Supabase (one-time migration)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.client import get_client
from db.config import load_config

PROJECT_REF = "hocehuebhntykignmjis"

MIGRATION_SQL = """
create table if not exists trip_checked_items (
  item_key text not null primary key,
  updated_at timestamptz not null default now()
);
alter table trip_checked_items enable row level security;
do $$
begin
  if not exists (
    select 1 from pg_policies
    where tablename = 'trip_checked_items'
      and policyname = 'Allow all on trip_checked_items'
  ) then
    create policy "Allow all on trip_checked_items"
      on trip_checked_items for all using (true) with check (true);
  end if;
end $$;
NOTIFY pgrst, 'reload schema';
"""


def _load_secrets() -> dict[str, str]:
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.is_file():
        return {}
    import tomllib

    with secrets_path.open("rb") as f:
        return {k: str(v) for k, v in tomllib.load(f).items() if v is not None}


def _run_sql(password: str) -> None:
    import psycopg2

    conn = psycopg2.connect(
        host=f"db.{PROJECT_REF}.supabase.co",
        port=5432,
        dbname="postgres",
        user="postgres",
        password=password,
        sslmode="require",
        connect_timeout=10,
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(MIGRATION_SQL)
    finally:
        conn.close()


def migrate() -> None:
    load_config()
    sb = get_client()
    try:
        sb.table("trip_checked_items").select("item_key").limit(1).execute()
        print("trip_checked_items table already exists.")
        return
    except Exception:
        pass

    secrets = _load_secrets()
    password = os.getenv("SUPABASE_DB_PASSWORD") or secrets.get("SUPABASE_DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "Set SUPABASE_DB_PASSWORD in .streamlit/secrets.toml or run the SQL in DEPLOY.md manually."
        )

    print("Creating trip_checked_items table...")
    _run_sql(password)
    for attempt in range(5):
        time.sleep(2)
        try:
            sb.table("trip_checked_items").select("item_key").limit(1).execute()
            print("Migration complete.")
            return
        except Exception as exc:
            if attempt == 4:
                raise RuntimeError(
                    f"Table created but API cache not ready: {exc}. Wait a minute and retry."
                ) from exc


if __name__ == "__main__":
    migrate()
