create table if not exists public.product_entitlements (
    entitlement_id text primary key,
    event_id text not null unique,
    subscription_id text not null unique,
    product_id text not null references public.product_releases(product_id),
    buyer_email text,
    buyer_name text,
    status text not null default 'active'
        check (status in ('active','paused','cancelled','refunded','revoked')),
    delivery_status text not null default 'pending'
        check (delivery_status in ('pending','sent','manual_required','failed')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    delivered_at timestamptz
);
create index if not exists idx_product_entitlements_buyer
    on public.product_entitlements (buyer_email, created_at desc);

create table if not exists public.product_download_tokens (
    token_hash text primary key check (length(token_hash) = 64),
    entitlement_id text not null unique references public.product_entitlements(entitlement_id),
    expires_at timestamptz not null,
    max_downloads integer not null default 5 check (max_downloads between 1 and 20),
    download_count integer not null default 0 check (download_count >= 0),
    status text not null default 'active' check (status in ('active','revoked')),
    created_at timestamptz not null default now(),
    last_downloaded_at timestamptz
);

alter table public.product_entitlements enable row level security;
drop policy if exists ai_company_gate on public.product_entitlements;
create policy ai_company_gate on public.product_entitlements
    for all to anon
    using ((select current_setting('app.ai_company_authorized', true)) = 'true')
    with check ((select current_setting('app.ai_company_authorized', true)) = 'true');
grant select, insert, update on public.product_entitlements to anon;

alter table public.product_download_tokens enable row level security;
drop policy if exists ai_company_gate on public.product_download_tokens;
create policy ai_company_gate on public.product_download_tokens
    for all to anon
    using ((select current_setting('app.ai_company_authorized', true)) = 'true')
    with check ((select current_setting('app.ai_company_authorized', true)) = 'true');
grant select, insert, update on public.product_download_tokens to anon;

create or replace function public.consume_product_download(p_token_hash text)
returns jsonb
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_token public.product_download_tokens%rowtype;
    v_entitlement public.product_entitlements%rowtype;
    v_product public.product_releases%rowtype;
begin
    if current_setting('app.ai_company_authorized', true) is distinct from 'true' then
        raise exception 'not authorized';
    end if;
    select * into v_token from public.product_download_tokens
     where token_hash = p_token_hash for update;
    if not found or v_token.status <> 'active'
       or v_token.expires_at <= now()
       or v_token.download_count >= v_token.max_downloads then
        return null;
    end if;
    select * into v_entitlement from public.product_entitlements
     where entitlement_id = v_token.entitlement_id for update;
    if not found or v_entitlement.status <> 'active' then
        return null;
    end if;
    select * into v_product from public.product_releases
     where product_id = v_entitlement.product_id
       and release_status = 'approved_for_sale';
    if not found then
        return null;
    end if;
    update public.product_download_tokens
       set download_count = download_count + 1, last_downloaded_at = now()
     where token_hash = p_token_hash;
    return jsonb_build_object(
        'product_id', v_product.product_id, 'name', v_product.name,
        'version', v_product.version, 'artifact_base64', v_product.artifact_base64,
        'sha256', v_product.sha256, 'artifact_bytes', v_product.artifact_bytes
    );
end;
$$;
revoke all on function public.consume_product_download(text) from public;
grant execute on function public.consume_product_download(text) to anon;
