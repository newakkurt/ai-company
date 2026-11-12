create table if not exists public.product_releases (
    product_id text primary key,
    name text not null,
    version text not null,
    summary text not null,
    release_status text not null default 'review_required',
    manifest_json jsonb not null default '{}'::jsonb,
    artifact_base64 text not null,
    sha256 text not null check (length(sha256) = 64),
    artifact_bytes integer not null check (artifact_bytes > 0 and artifact_bytes <= 1500000),
    created_at timestamptz not null default now()
);

create index if not exists idx_product_releases_created
    on public.product_releases (created_at desc);

alter table public.product_releases enable row level security;
drop policy if exists ai_company_gate on public.product_releases;
create policy ai_company_gate on public.product_releases
    for all to anon
    using ((select current_setting('app.ai_company_authorized', true)) = 'true')
    with check ((select current_setting('app.ai_company_authorized', true)) = 'true');

grant select, insert, update on public.product_releases to anon;
