"""Shopping List — Streamlit app (Supabase backend)."""

from __future__ import annotations

import hashlib
import hmac
import os
import threading

import extra_streamlit_components as stx
import streamlit as st
import streamlit.components.v1 as components

from core.generator import generate_shopping_list
from core.models import RecipeIngredient
from db import client as db
from db import trip_checked
from db.instructions_store import recipe_instructions


def format_amount(amount: float) -> str:
    """Format shopping-list amounts: up to 2 decimal places, no trailing zeros."""
    return f"{round(float(amount), 2):.2f}".rstrip("0").rstrip(".")


def _load_trip_crossed(sb, current_keys: set[str]) -> set[str]:
    """Load crossed-off keys from Supabase (source of truth when rendering the trip page)."""
    crossed = trip_checked.fetch_trip_checked_items(sb) & current_keys
    st.session_state.trip_crossed = crossed
    return crossed


def _clear_trip_crossed_state() -> None:
    st.session_state.trip_crossed = set()
    st.session_state.pop("trip_current_keys", None)
    st.session_state.pop("trip_keys_token", None)
    for key in list(st.session_state.keys()):
        if str(key).startswith("trip_row_"):
            del st.session_state[key]


def _save_trip_crossed_async(crossed: set[str]) -> None:
    def _save() -> None:
        try:
            trip_checked.save_trip_checked_items(db.get_client(), crossed)
        except Exception:
            pass

    threading.Thread(target=_save, daemon=True).start()


def _trip_row_btn_key(item_key: str) -> str:
    return "trip_row_" + hashlib.md5(item_key.encode()).hexdigest()


def _on_trip_row_click(item_key: str) -> None:
    current_keys = set(st.session_state.get("trip_current_keys") or ())
    crossed = set(st.session_state.get("trip_crossed") or set())
    if item_key in crossed:
        crossed.discard(item_key)
    else:
        crossed.add(item_key)
    st.session_state.trip_crossed = crossed & current_keys
    _save_trip_crossed_async(set(st.session_state.trip_crossed))


def _mount_trip_instant_click() -> None:
    """Toggle row styles in the parent document on tap (before server rerun)."""
    components.html(
        """
        <script>
        (() => {
          const parent = window.parent;
          if (parent.__tripInstantClick) return;
          parent.__tripInstantClick = true;
          parent.document.addEventListener("click", (event) => {
            const btn = event.target.closest("button");
            if (!btn) return;
            const header = parent.document.querySelector(".trip-table-header");
            if (!header) return;
            const headerBox = header.closest('[data-testid="stElementContainer"]');
            const rowBox = btn.closest('[data-testid="stElementContainer"]');
            if (!headerBox || !rowBox || headerBox.parentElement !== rowBox.parentElement) return;
            let afterHeader = false;
            for (const child of headerBox.parentElement.children) {
              if (child === headerBox) { afterHeader = true; continue; }
              if (!afterHeader) continue;
              if (child !== rowBox) continue;
              const p = btn.querySelector("p") || btn;
              const crossed = btn.getAttribute("kind") !== "primary";
              btn.setAttribute("kind", crossed ? "primary" : "secondary");
              if (crossed) {
                p.style.color = "#ef5350";
                p.style.textDecoration = "line-through";
              } else {
                p.style.color = "#fafafa";
                p.style.textDecoration = "none";
              }
              return;
            }
          }, true);
        })();
        </script>
        """,
        height=0,
        scrolling=False,
    )


@st.fragment
def _trip_list_fragment(table_rows: list[dict[str, str]]) -> None:
    """Trip list in a fragment rerun (fast) with instant client-side styling."""
    _mount_trip_instant_click()
    crossed_off = set(st.session_state.get("trip_crossed") or ())
    st.markdown(
        '<div class="trip-table-header"><span>Amt</span><span>Ingredient</span></div>',
        unsafe_allow_html=True,
    )
    for row in table_rows:
        item_key = row["key"]
        is_crossed = item_key in crossed_off
        label = f"{row['amt']:>4}  {row['ingredient']}".strip()
        st.button(
            label,
            key=_trip_row_btn_key(item_key),
            on_click=_on_trip_row_click,
            args=(item_key,),
            use_container_width=True,
            type="primary" if is_crossed else "secondary",
        )


def db_error_message(exc: Exception) -> str:
    msg = str(exc).lower()
    if "duplicate" in msg or "unique" in msg:
        if "recipes" in msg or "recipe" in msg and "name" in msg:
            return "A recipe with that name already exists."
        return "An ingredient with that name and unit already exists."
    if "foreign key" in msg or "23503" in msg:
        return "This ingredient is used in one or more recipes. Remove it from recipes first."
    return str(exc)

st.set_page_config(
    page_title="Shopping List",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_CSS = """
<style>
    section[data-testid="stSidebar"] { display: none !important; }
    div[data-testid="stSidebarCollapsedControl"] { display: none !important; }
    button[data-testid="stSidebarCollapseButton"] { display: none !important; }

    /* Borders on field wrappers so rounded corners render cleanly */
    div[data-testid="stTextInput"] [data-baseweb="input"],
    div[data-testid="stNumberInput"] [data-baseweb="input"],
    div[data-testid="stTextArea"] [data-baseweb="textarea"],
    div[data-testid="stTextArea"] [data-baseweb="base-input"] {
        border: 1px solid #757575 !important;
        border-radius: 0.5rem !important;
        overflow: hidden;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextArea"] textarea {
        border: none !important;
        box-shadow: none !important;
    }

    div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
        border: 1px solid #757575 !important;
        border-radius: 0.5rem !important;
    }

    div[data-testid="stDataEditor"] [data-baseweb="input"] {
        border: 1px solid #757575 !important;
        border-radius: 0.25rem !important;
        overflow: hidden;
    }

    div[data-testid="stDataEditor"] input,
    div[data-testid="stDataEditor"] div[contenteditable="true"] {
        border: none !important;
        box-shadow: none !important;
    }

    .trip-table-header {
        display: grid;
        grid-template-columns: 3.25rem 1fr;
        gap: 0.5rem;
        padding: 0.5rem 0;
        border-bottom: 1px solid #757575;
        color: #b0b0b0;
        font-weight: 600;
    }
    div[data-testid="stElementContainer"]:has(.trip-table-header)
        ~ div[data-testid="stElementContainer"] div[data-testid="stButton"] button {
        display: block !important;
        justify-content: start !important;
        text-align: left !important;
        width: 100% !important;
        border: none !important;
        border-bottom: 1px solid #2a2f36 !important;
        border-radius: 0 !important;
        background: transparent !important;
        padding: 0.65rem 0 !important;
        font-weight: 400 !important;
        white-space: pre-wrap !important;
        box-shadow: none !important;
        -webkit-tap-highlight-color: transparent;
    }
    div[data-testid="stElementContainer"]:has(.trip-table-header)
        ~ div[data-testid="stElementContainer"] div[data-testid="stButton"] button p {
        text-align: left !important;
        white-space: pre-wrap !important;
    }
    div[data-testid="stElementContainer"]:has(.trip-table-header)
        ~ div[data-testid="stElementContainer"] div[data-testid="stButton"] button[kind="secondary"] {
        color: #fafafa !important;
    }
    div[data-testid="stElementContainer"]:has(.trip-table-header)
        ~ div[data-testid="stElementContainer"] div[data-testid="stButton"] button[kind="secondary"] p {
        color: #fafafa !important;
    }
    div[data-testid="stElementContainer"]:has(.trip-table-header)
        ~ div[data-testid="stElementContainer"] div[data-testid="stButton"] button[kind="primary"] {
        color: #ef5350 !important;
    }
    div[data-testid="stElementContainer"]:has(.trip-table-header)
        ~ div[data-testid="stElementContainer"] div[data-testid="stButton"] button[kind="primary"] p {
        color: #ef5350 !important;
        text-decoration: line-through !important;
    }
    div[data-testid="stElementContainer"]:has(.trip-table-header)
        ~ div[data-testid="stElementContainer"] div[data-testid="stButton"] button:hover,
    div[data-testid="stElementContainer"]:has(.trip-table-header)
        ~ div[data-testid="stElementContainer"] div[data-testid="stButton"] button:focus {
        background: rgba(255, 255, 255, 0.05) !important;
        border-color: #2a2f36 !important;
    }
</style>
"""


def hide_sidebar() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)


PAGES = (
    ("meals", "Meal Selection", None),
    ("trip", "Next Trip", None),
    ("ingredients", "Ingredients", None),
    ("recipes", "Recipes", None),
)
PAGE_LABELS = [label for _, label, _ in PAGES]
PAGE_KEY_BY_LABEL = {label: key for key, label, _ in PAGES}
PAGE_LABEL_BY_KEY = {key: label for key, label, _ in PAGES}


COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


def _cookie_manager() -> stx.CookieManager:
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(key="shopping_list_auth")
    return st.session_state.cookie_manager


def _auth_token(password: str) -> str:
    return hmac.new(password.encode(), b"shopping-list-v1", hashlib.sha256).hexdigest()


def _restore_auth_from_cookie(expected: str) -> None:
    if st.session_state.get("authenticated"):
        return
    token = _cookie_manager().get("sl_auth")
    if token and token == _auth_token(expected):
        st.session_state.authenticated = True


def _set_auth_cookie(expected: str) -> None:
    _cookie_manager().set(
        "sl_auth",
        _auth_token(expected),
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


def _clear_auth_cookie() -> None:
    _cookie_manager().delete("sl_auth")


def _init_auth_cookies() -> None:
    """Mount CookieManager and wait one rerun for browser cookies to load."""
    _cookie_manager().get_all()
    if not st.session_state.get("cookies_bootstrapped"):
        st.session_state.cookies_bootstrapped = True
        st.rerun()


def render_app_header() -> None:
    _, logout_col = st.columns([6, 1])
    with logout_col:
        if st.button("Log out", use_container_width=True):
            st.session_state.authenticated = False
            _clear_auth_cookie()
            st.rerun()


def _password() -> str | None:
    try:
        return st.secrets.get("APP_PASSWORD") or os.getenv("APP_PASSWORD")
    except (FileNotFoundError, AttributeError):
        return os.getenv("APP_PASSWORD")


def require_auth() -> None:
    expected = _password()
    if not expected:
        st.warning("Set APP_PASSWORD in secrets or environment to protect this app.")
        return

    if st.session_state.get("authenticated"):
        return

    _restore_auth_from_cookie(expected)
    if st.session_state.get("authenticated"):
        return

    st.title("Shopping List")
    with st.form("login_form", clear_on_submit=False):
        entered = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
    if submitted:
        if entered == expected:
            st.session_state.authenticated = True
            _set_auth_cookie(expected)
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


def load_data():
    sb = db.get_client()
    ingredients = db.fetch_ingredients(sb)
    recipes = db.fetch_recipes(sb)
    meal_ids = db.fetch_meal_selection(sb)
    other_items = db.fetch_other_items(sb)
    recipe_options = db.fetch_recipe_names(sb)
    return sb, ingredients, recipes, meal_ids, other_items, recipe_options


def page_meal_selection() -> None:
    st.header("Meal Selection")
    st.caption("Pick meals from the dropdowns below, then tap **Save & regenerate**.")

    sb, ingredients, recipes, meal_ids, other_items, recipe_options = load_data()
    id_to_name = {rid: name for rid, name in recipe_options}
    name_to_id = {name: rid for rid, name in recipe_options}

    if not recipe_options:
        st.info("No recipes yet. Add recipes on the **Recipes** tab.")
        return

    recipe_names = [id_to_name[i] for i in meal_ids if i in id_to_name]
    option_labels = [name for _, name in recipe_options]
    max_slots = max(len(recipe_names) + 2, 6)

    with st.form("meal_selection_form", border=True):
        st.subheader("Selected meals")
        slots: list[str] = []
        for i in range(max_slots):
            default = recipe_names[i] if i < len(recipe_names) else ""
            options = [""] + option_labels
            choice = st.selectbox(
                f"Meal {i + 1}",
                options=options,
                index=options.index(default) if default in options else 0,
                key=f"meal_slot_{i}",
            )
            if choice:
                slots.append(choice)

        st.subheader("Other items (manual)")
        other_text = st.text_area(
            "One item per line (e.g. paper towels)",
            value="\n".join(other_items),
            height=100,
        )

        submitted = st.form_submit_button("Save & regenerate", type="primary", use_container_width=True)

    other_lines = [ln.strip() for ln in other_text.splitlines() if ln.strip()]

    if submitted:
        selected_ids = [name_to_id[n] for n in slots if n in name_to_id]
        db.save_meal_selection(sb, selected_ids)
        db.save_other_items(sb, other_lines)
        trip_checked.clear_trip_checked_items(sb)
        _clear_trip_crossed_state()
        st.success("Saved — shopping list updated.")
        st.rerun()

    preview_ids = [name_to_id[n] for n in recipe_names if n in name_to_id]
    result = generate_shopping_list(ingredients, recipes, preview_ids, other_lines)

    if result.errors:
        with st.expander("Errors", expanded=True):
            for err in result.errors:
                st.warning(err)

    if result.meals:
        st.subheader("Calories")
        st.dataframe(
            [
                {
                    "Meal": m.recipe_name,
                    "Total calories": m.total_calories,
                    "Servings": m.servings,
                    "Calories per serving": m.calories_per_serving,
                }
                for m in result.meals
            ],
            use_container_width=True,
            hide_index=True,
        )


def page_next_trip() -> None:
    st.header("Next Trip")
    st.caption(
        "Shopping list from your saved meal selection. Tap a row to cross it off. "
        "To change meals, use the **Meal Selection** tab."
    )

    sb, ingredients, recipes, meal_ids, other_items, _ = load_data()
    result = generate_shopping_list(ingredients, recipes, meal_ids, other_items)

    if result.errors:
        with st.expander("Errors"):
            for err in result.errors:
                st.warning(err)

    if not result.shopping_list:
        st.info("No meals selected yet. Open the **Meal Selection** tab to choose meals.")
        return

    current_keys = {row.display_name for row in result.shopping_list}
    st.session_state.trip_current_keys = current_keys
    keys_token = frozenset(current_keys)
    if st.session_state.get("trip_keys_token") != keys_token:
        _load_trip_crossed(sb, current_keys)
        st.session_state.trip_keys_token = keys_token

    table_rows = [
        {
            "key": row.display_name,
            "amt": "" if row.is_other else format_amount(row.amount),
            "ingredient": row.display_name,
        }
        for row in result.shopping_list
    ]

    _trip_list_fragment(table_rows)


def page_ingredients() -> None:
    st.header("Ingredients")
    st.caption("Manage the ingredient catalog used by recipes and the shopping list.")

    sb = db.get_client()
    ingredients = db.fetch_ingredients(sb)

    filter_text = st.text_input("Search", placeholder="Filter by name or unit")
    filtered = ingredients
    if filter_text.strip():
        q = filter_text.strip().lower()
        filtered = [
            i
            for i in ingredients
            if q in i.name.lower()
            or q in i.unit.lower()
            or q in i.display_name.lower()
        ]

    st.dataframe(
        [
            {
                "Name": i.name,
                "Unit": i.unit,
                "Calories / unit": i.calories_per_unit,
            }
            for i in filtered
        ],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Add ingredient", expanded=not ingredients):
        with st.form("add_ingredient", clear_on_submit=True):
            name = st.text_input("Name", placeholder="e.g. olive oil")
            unit = st.text_input("Unit", placeholder="e.g. Tbsp")
            calories = st.number_input("Calories per unit", min_value=0.0, step=1.0, value=0.0)
            if st.form_submit_button("Add ingredient", type="primary", use_container_width=True):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    try:
                        db.create_ingredient(sb, name, unit, calories)
                        st.success(f"Added {name.strip()}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(db_error_message(exc))

    if not ingredients:
        return

    with st.expander("Edit or delete ingredient"):
        by_id = {i.id: i for i in ingredients}
        pick = st.selectbox(
            "Select ingredient",
            options=list(by_id),
            format_func=lambda iid: by_id[iid].display_name,
        )
        ing = by_id[pick]

        with st.form("edit_ingredient"):
            name = st.text_input("Name", value=ing.name)
            unit = st.text_input("Unit", value=ing.unit)
            calories = st.number_input(
                "Calories per unit",
                min_value=0.0,
                step=1.0,
                value=float(ing.calories_per_unit),
            )
            if st.form_submit_button("Save changes", type="primary", use_container_width=True):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    try:
                        db.update_ingredient(sb, ing.id, name, unit, calories)
                        st.success("Ingredient updated.")
                        st.rerun()
                    except Exception as exc:
                        st.error(db_error_message(exc))

        if st.button("Delete ingredient", type="secondary", use_container_width=True):
            try:
                db.delete_ingredient(sb, ing.id)
                st.success("Ingredient deleted.")
                st.rerun()
            except Exception as exc:
                st.error(db_error_message(exc))


def page_recipes() -> None:
    st.header("Recipes")
    st.caption("Create and edit recipes, including ingredients and cooking instructions.")

    sb = db.get_client()
    ingredients = db.fetch_ingredients(sb)
    recipes = db.fetch_recipes(sb)

    if not ingredients:
        st.warning("Add ingredients on the **Ingredients** tab before creating recipes.")
        return

    id_to_label = {i.id: i.display_name for i in ingredients}
    label_to_id = {label: iid for iid, label in id_to_label.items()}
    ingredient_labels = sorted(label_to_id.keys(), key=str.lower)

    recipe_names = [r.name for r in recipes]
    pick = st.selectbox("Recipe", options=["— New recipe —"] + recipe_names)
    is_new = pick == "— New recipe —"
    recipe = next((r for r in recipes if r.name == pick), None)
    form_key = f"recipe_{recipe.id if recipe else 'new'}"

    recipe_name = st.text_input(
        "Name",
        value="" if is_new else (recipe.name if recipe else ""),
        key=f"name_{form_key}",
    )
    instructions = st.text_area(
        "Instructions",
        value="" if is_new else recipe_instructions(recipe),
        height=200,
        placeholder="Steps and notes from below the ingredient list in your spreadsheet.",
        key=f"instructions_{form_key}",
    )

    st.subheader("Ingredients")
    line_rows: list[dict[str, object]] = []
    if recipe:
        for line in recipe.ingredients:
            label = id_to_label.get(line.ingredient_id)
            if label:
                line_rows.append({"Ingredient": label, "Amount": line.amount})
    if not line_rows:
        line_rows = [{"Ingredient": ingredient_labels[0], "Amount": 1.0}]

    editor_key = f"recipe_lines_{recipe.id if recipe else 'new'}"
    edited = st.data_editor(
        line_rows,
        column_config={
            "Ingredient": st.column_config.SelectboxColumn(
                "Ingredient",
                options=ingredient_labels,
                required=True,
            ),
            "Amount": st.column_config.NumberColumn(
                "Amount",
                min_value=0.0,
                step=0.25,
                format="%.2f",
            ),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=editor_key,
    )

    save_col, delete_col = st.columns(2)
    with save_col:
        save = st.button("Save recipe", type="primary", use_container_width=True)
    with delete_col:
        delete = not is_new and st.button("Delete recipe", use_container_width=True)

    if save:
        clean_name = recipe_name.strip()
        if not clean_name:
            st.error("Recipe name is required.")
        else:
            lines: list[RecipeIngredient] = []
            for row in edited:
                label = row.get("Ingredient")
                amount = row.get("Amount")
                if not label or amount is None:
                    continue
                iid = label_to_id.get(str(label))
                if iid is not None:
                    lines.append(RecipeIngredient(iid, float(amount)))
            try:
                if is_new:
                    db.create_recipe(sb, clean_name, lines, instructions)
                    st.success(f"Created {clean_name}.")
                else:
                    db.update_recipe(sb, recipe.id, clean_name, lines, instructions)
                    st.success("Recipe saved.")
                st.rerun()
            except Exception as exc:
                st.error(db_error_message(exc))

    if delete and recipe:
        try:
            db.delete_recipe(sb, recipe.id)
            st.success(f"Deleted {recipe.name}.")
            st.rerun()
        except Exception as exc:
            st.error(db_error_message(exc))


def render_navigation() -> str:
    tab_key = st.query_params.get("tab", "meals")
    if tab_key not in PAGE_LABEL_BY_KEY:
        tab_key = "meals"

    selected_label = st.segmented_control(
        "Section",
        options=PAGE_LABELS,
        default=PAGE_LABEL_BY_KEY[tab_key],
        label_visibility="collapsed",
        width="stretch",
    )
    if selected_label is None:
        selected_label = PAGE_LABEL_BY_KEY[tab_key]

    selected_key = PAGE_KEY_BY_LABEL[selected_label]
    if selected_key != tab_key:
        st.query_params["tab"] = selected_key
        st.rerun()
    return selected_key


def main() -> None:
    hide_sidebar()
    _init_auth_cookies()
    require_auth()
    render_app_header()

    tab_key = render_navigation()
    if tab_key == "meals":
        page_meal_selection()
    elif tab_key == "trip":
        page_next_trip()
    elif tab_key == "ingredients":
        page_ingredients()
    else:
        page_recipes()


if __name__ == "__main__":
    main()
