-- Run this in the Supabase SQL Editor after creating a free project.

create table if not exists ingredients (
  id bigint generated always as identity primary key,
  name text not null,
  unit text not null default '',
  location text not null default '',
  calories_per_unit numeric not null default 0,
  created_at timestamptz not null default now(),
  unique (name, unit)
);

create table if not exists recipes (
  id bigint generated always as identity primary key,
  name text not null unique,
  instructions text not null default '',
  created_at timestamptz not null default now()
);

create table if not exists recipe_ingredients (
  id bigint generated always as identity primary key,
  recipe_id bigint not null references recipes (id) on delete cascade,
  ingredient_id bigint not null references ingredients (id) on delete restrict,
  amount numeric not null default 0,
  unique (recipe_id, ingredient_id)
);

create table if not exists meal_selection (
  position int not null primary key,
  recipe_id bigint not null references recipes (id) on delete cascade
);

create table if not exists other_items (
  position int not null primary key,
  name text not null
);

create table if not exists trip_checked_items (
  item_key text not null primary key,
  updated_at timestamptz not null default now()
);

create index if not exists idx_recipe_ingredients_recipe on recipe_ingredients (recipe_id);
create index if not exists idx_recipe_ingredients_ingredient on recipe_ingredients (ingredient_id);

-- Allow anon key access for solo app (protect with Streamlit password).
alter table ingredients enable row level security;
alter table recipes enable row level security;
alter table recipe_ingredients enable row level security;
alter table meal_selection enable row level security;
alter table other_items enable row level security;
alter table trip_checked_items enable row level security;

create policy "Allow all on ingredients" on ingredients for all using (true) with check (true);
create policy "Allow all on recipes" on recipes for all using (true) with check (true);
create policy "Allow all on recipe_ingredients" on recipe_ingredients for all using (true) with check (true);
create policy "Allow all on meal_selection" on meal_selection for all using (true) with check (true);
create policy "Allow all on other_items" on other_items for all using (true) with check (true);
create policy "Allow all on trip_checked_items" on trip_checked_items for all using (true) with check (true);

-- Run once when upgrading from a schema that included ingredient categories:
-- alter table ingredients drop column if exists category;

-- Run once when upgrading to add recipe instructions:
-- alter table recipes add column if not exists instructions text not null default '';

-- Run once when upgrading to add ingredient store location (Loc on Next Trip):
-- alter table ingredients add column if not exists location text not null default '';

-- Run once when upgrading to persist Next Trip crossed-off items:
-- create table if not exists trip_checked_items (
--   item_key text not null primary key,
--   updated_at timestamptz not null default now()
-- );
-- alter table trip_checked_items enable row level security;
-- create policy "Allow all on trip_checked_items" on trip_checked_items for all using (true) with check (true);
