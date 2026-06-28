"""Load Supabase config from environment or .streamlit/secrets.toml."""

from __future__ import annotations

import os
from pathlib import Path


def load_config() -> None:
    secrets_path = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
    if not secrets_path.is_file():
        return

    import tomllib

    with secrets_path.open("rb") as f:
        data = tomllib.load(f)

    for key in (
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "APP_PASSWORD",
        "SUPABASE_DB_PASSWORD",
        "SUPABASE_DB_URL",
        "DATABASE_URL",
        "SUPABASE_ACCESS_TOKEN",
        "SHOPPING_LIST_CREDENTIALS",
        "SHOPPING_LIST_WORKBOOK_ID",
    ):
        val = data.get(key)
        if val and not os.getenv(key):
            os.environ[key] = str(val)
