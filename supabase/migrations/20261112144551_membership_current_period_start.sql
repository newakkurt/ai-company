alter table public.memberships
    add column if not exists current_period_start timestamptz;
