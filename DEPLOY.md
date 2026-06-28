# Deploy: Streamlit Community Cloud + Supabase

The primary app is **`app.py`** (Streamlit + Supabase). Legacy Google Sheets tooling (`main.py`, `apps-script/`) is kept for reference only.

## 1. Supabase (database)

Already set up for this project. If starting fresh:

1. Create a free project at [supabase.com](https://supabase.com).
2. Run [`db/schema.sql`](db/schema.sql) in the **SQL Editor** (includes `recipes.instructions`).
3. Copy from **Project Settings → API**:
   - **Project URL** → `SUPABASE_URL`
   - **Publishable** (or legacy **anon**) key → `SUPABASE_KEY`

## 2. Migrate from Google Sheets (one time, optional)

Only needed to import from an existing workbook:

```powershell
cd c:\Users\yoshi\PycharmProjects\ShoppingList
$env:SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
$env:SUPABASE_KEY = "your-key"
$env:SHOPPING_LIST_CREDENTIALS = "path\to\credentials.json"
$env:SHOPPING_LIST_WORKBOOK_ID = "1eAY-S8deVCH1i3RAfgVajw3c55CtqP0Y3r9RQ9irTzs"
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\migrate_from_sheets.py
```

To backfill recipe instructions only:

```powershell
.\.venv\Scripts\python.exe scripts\setup_recipe_instructions.py
```

## 3. Run locally

Create [`.streamlit/secrets.toml`](.streamlit/secrets.toml) (gitignored):

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY = "your-publishable-or-anon-key"
APP_PASSWORD = "your-chosen-password"
```

Optional (schema migrations from your PC only):

```toml
SUPABASE_DB_PASSWORD = "your-database-password"
SHOPPING_LIST_CREDENTIALS = "path\to\credentials.json"
SHOPPING_LIST_WORKBOOK_ID = "your-workbook-id"
```

```powershell
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\streamlit run app.py
```

Open http://localhost:8501

## 4. Deploy to Streamlit Community Cloud

1. **Commit and push** this repo to GitHub (public repo required on free tier).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **Create app**.
3. Repository: your fork/repo, branch: `master` (or `main`), main file: **`app.py`**.
4. **Advanced settings → Secrets**:

```toml
SUPABASE_URL = "https://hocehuebhntykignmjis.supabase.co"
SUPABASE_KEY = "your-publishable-or-anon-key"
APP_PASSWORD = "your-chosen-password"
```

Do **not** put database passwords or Google credentials in Streamlit Cloud secrets.

5. Deploy. Your URL will be `https://<app-name>.streamlit.app`.

Theme (dark) and layout are in [`.streamlit/config.toml`](.streamlit/config.toml) and deploy automatically.

## 5. iPhone / daily use

1. Open the Streamlit URL in **Safari**.
2. Log in with `APP_PASSWORD` (Enter key works on the login form).
3. **Share → Add to Home Screen** for quick access.
4. **Meal Selection** — pick meals and save.
5. **Next Trip** — shopping list; tap a row to cross items off (persists until you change meals or log out).
6. **Ingredients** / **Recipes** — edit catalog and instructions in the app.

## Notes

- Never commit `.streamlit/secrets.toml`, service account JSON, or `.clasp.json`.
- Free tier sleeps after inactivity; first load may take a few seconds.
- Crossed-off items on Next Trip are stored in the browser session (cookie + session state), not in Supabase.
- Recipe instructions live in Supabase (`recipes.instructions`); `data/recipe_instructions.json` is a local fallback only.
