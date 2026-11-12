create table if not exists public.mail_send_log (
    message_id text primary key,
    sender_email text not null,
    status text not null default 'reserved'
        check (status in ('reserved', 'sent', 'failed')),
    reserved_at timestamptz not null default now(),
    sent_at timestamptz,
    error_type text
);

create index if not exists idx_mail_send_log_daily
    on public.mail_send_log (reserved_at desc, status, sender_email);

alter table public.mail_send_log enable row level security;
drop policy if exists ai_company_gate on public.mail_send_log;
create policy ai_company_gate on public.mail_send_log
    for all to anon
    using ((select current_setting('app.ai_company_authorized', true)) = 'true')
    with check ((select current_setting('app.ai_company_authorized', true)) = 'true');

grant select, insert, update on public.mail_send_log to anon;
