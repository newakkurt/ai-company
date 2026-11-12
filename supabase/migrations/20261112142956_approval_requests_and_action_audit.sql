create table if not exists public.approval_requests (
    approval_id text primary key,
    action text not null,
    scope_json jsonb not null default '{}'::jsonb,
    requested_by text not null,
    status text not null default 'pending'
        check (status in ('pending', 'approved', 'rejected', 'consumed', 'expired')),
    requested_at timestamptz not null default now(),
    expires_at timestamptz not null,
    decided_at timestamptz,
    decided_by text,
    decision_note text,
    consumed_at timestamptz
);

create index if not exists idx_approval_requests_status_created
    on public.approval_requests (status, requested_at desc);
create index if not exists idx_approval_requests_action_status
    on public.approval_requests (action, status);

alter table public.approval_requests enable row level security;
drop policy if exists ai_company_gate on public.approval_requests;
create policy ai_company_gate on public.approval_requests
    for all to anon
    using ((select current_setting('app.ai_company_authorized', true)) = 'true')
    with check ((select current_setting('app.ai_company_authorized', true)) = 'true');

grant select, insert, update on public.approval_requests to anon;
