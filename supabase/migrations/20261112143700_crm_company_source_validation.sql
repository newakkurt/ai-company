alter table public.crm_companies
    add column if not exists source_validation_status text not null default 'not_checked',
    add column if not exists source_http_status integer,
    add column if not exists source_page_title text,
    add column if not exists source_checked_at timestamptz,
    add column if not exists source_validation_note text;

create index if not exists idx_crm_companies_source_validation
    on public.crm_companies (source_validation_status, updated_at desc);
