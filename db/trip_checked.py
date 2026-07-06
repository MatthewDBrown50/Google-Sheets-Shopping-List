"""Persist crossed-off items on the Next Trip shopping list."""

from __future__ import annotations

from postgrest.exceptions import APIError
from supabase import Client


def fetch_trip_checked_items(client: Client) -> set[str]:
    try:
        rows = client.table("trip_checked_items").select("item_key").execute().data or []
    except APIError:
        return set()
    return {r["item_key"] for r in rows}


def save_trip_checked_items(client: Client, keys: set[str]) -> None:
    try:
        client.table("trip_checked_items").delete().neq("item_key", "").execute()
        if not keys:
            return
        client.table("trip_checked_items").insert(
            [{"item_key": key} for key in sorted(keys)]
        ).execute()
    except APIError:
        pass


def clear_trip_checked_items(client: Client) -> None:
    try:
        client.table("trip_checked_items").delete().neq("item_key", "").execute()
    except APIError:
        pass
