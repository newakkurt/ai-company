# Marketing & Growth Operations

## Scope
The AI Company marketing engine creates daily and weekly analysis/draft tasks for NetCmd PRO. It covers:
- SEO: Turkish and English keyword intent, article drafts, metadata, FAQ/schema and internal links.
- LinkedIn: B2B educational posts, carousel outlines and bilingual copy.
- YouTube: weekly long-form scripts, thumbnails, descriptions and Shorts repurposing.
- Instagram: daily carousel/Reel scripts, captions, alt text and hashtags.
- Telegram: daily channel announcement drafts.
- Product visuals: weekly briefs and prompts for hero, square, 4:5, 9:16, LinkedIn and YouTube assets.
- Email: weekly permission-based nurture campaign drafts, subject tests and compliance checklist.
- Conversion: weekly funnel analysis from actual connected/supplied data only.
- Market opportunities: weekly sourced opportunity ranking and a 7-day experiment.

## Runtime
- Dashboard: `/marketing`
- Status: `GET /api/marketing/status`
- Queue: `GET /api/marketing/tasks`
- Task detail/output: `GET /api/marketing/tasks/{task_id}`
- Create a one-off campaign task: `POST /api/marketing/campaign`
- All API endpoints require `Authorization: Bearer AI_COMPANY_API_KEY`.
- Scheduled playbooks are seeded idempotently by the existing scheduler and processed by the existing supervised worker.
- Each task uses the existing specialist agent IDs and persists outputs in the existing task/agent-output store.

## Operating safeguards
- The system produces drafts and analysis; it does not automatically publish, email, buy ads or contact prospects.
- Social publishing integrations must be connected and authorized separately. Current dashboard reports their state rather than pretending a connection exists.
- Email is only for opted-in / otherwise legally eligible recipients, with unsubscribe and KVKK/GDPR/İYS review.
- No fabricated testimonials, customer logos, performance metrics, SEO rankings, analytics or revenue.
- Conversion reports must label missing analytics integrations and never invent a denominator.
- All external factual claims require source URLs and access dates.
- $69/month is the current pricing hypothesis, not proven willingness-to-pay.

## Required deployment checks
1. Confirm Render deployment is live.
2. Check `/api/health` and `/api/marketing/status`.
3. Confirm `AI_COMPANY_AUTO_TASKS=true`, `AI_COMPANY_EMBEDDED_WORKER=true`, Supabase server credentials and at least one model provider key.
4. Confirm the worker is actually running and scheduled task IDs appear once per day/week.
5. Verify agent outputs are persisted.
6. Connect social and analytics providers before enabling real publishing or measuring channel conversion.
