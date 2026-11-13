-- Performance follow-up: cover child-side foreign keys and avoid per-row RLS setting evaluation.
-- This migration is idempotent and preserves the existing AI Company gate semantics.

CREATE INDEX IF NOT EXISTS idx_crm_activities_company_id ON public.crm_activities (company_id);
CREATE INDEX IF NOT EXISTS idx_crm_activities_contact_id ON public.crm_activities (contact_id);
CREATE INDEX IF NOT EXISTS idx_crm_contacts_company_id ON public.crm_contacts (company_id);
CREATE INDEX IF NOT EXISTS idx_crm_followups_company_id ON public.crm_followups (company_id);
CREATE INDEX IF NOT EXISTS idx_crm_followups_contact_id ON public.crm_followups (contact_id);
CREATE INDEX IF NOT EXISTS idx_crm_followups_offer_id ON public.crm_followups (offer_id);
CREATE INDEX IF NOT EXISTS idx_crm_offers_company_id ON public.crm_offers (company_id);
CREATE INDEX IF NOT EXISTS idx_crm_offers_contact_id ON public.crm_offers (contact_id);
CREATE INDEX IF NOT EXISTS idx_memberships_task_id ON public.memberships (task_id);
CREATE INDEX IF NOT EXISTS idx_product_entitlements_product_id ON public.product_entitlements (product_id);

DROP POLICY IF EXISTS ai_company_gate ON public.bank_settlements;
CREATE POLICY ai_company_gate ON public.bank_settlements FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.crm_activities;
CREATE POLICY ai_company_gate ON public.crm_activities FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.crm_companies;
CREATE POLICY ai_company_gate ON public.crm_companies FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.crm_contacts;
CREATE POLICY ai_company_gate ON public.crm_contacts FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.crm_followups;
CREATE POLICY ai_company_gate ON public.crm_followups FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.crm_mail_log;
CREATE POLICY ai_company_gate ON public.crm_mail_log FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.crm_offers;
CREATE POLICY ai_company_gate ON public.crm_offers FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.crm_suppressions;
CREATE POLICY ai_company_gate ON public.crm_suppressions FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.memberships;
CREATE POLICY ai_company_gate ON public.memberships FOR ALL TO anon
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.payment_events;
CREATE POLICY ai_company_gate ON public.payment_events FOR ALL TO anon
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.payment_ledger;
CREATE POLICY ai_company_gate ON public.payment_ledger FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');

DROP POLICY IF EXISTS ai_company_gate ON public.provider_payouts;
CREATE POLICY ai_company_gate ON public.provider_payouts FOR ALL TO public
USING ((SELECT current_setting('app.ai_company_authorized', true)) = 'true')
WITH CHECK ((SELECT current_setting('app.ai_company_authorized', true)) = 'true');
