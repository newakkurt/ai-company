# NetCmd PRO — Buy Me a Coffee checkout and agent activation

This integration keeps the current $0 hosting setup. It does not require a paid Render plan or a new database.

## Public pages

- Storefront: https://ai-company-ferd.onrender.com/
- Agent console: https://ai-company-ferd.onrender.com/admin
- Checkout redirect: https://ai-company-ferd.onrender.com/checkout
- Buy Me a Coffee webhook endpoint: https://ai-company-ferd.onrender.com/webhooks/buymeacoffee

The checkout redirect uses `BMC_PRO_CHECKOUT_URL`. Until that variable contains the exact NetCmd PRO membership checkout URL, it falls back to the creator page. The creator page itself is not proof that the $69/month tier is configured.

## Configure the paid membership in Buy Me a Coffee

1. In the creator dashboard, create or verify one monthly membership level named **NetCmd PRO**.
2. Set the price to **USD 69 per month**.
3. Copy its numeric membership level ID from the membership-level details or dashboard URL.
4. Copy the exact public checkout URL for this level.
5. Open **Integrations → New webhook**.
6. Set the endpoint to the webhook URL above.
7. Subscribe to `membership.started`, `membership.updated`, `membership.cancelled`, and `membership.paused`.
8. Save the webhook and copy its Signing Secret. Do not send the secret in chat or put it in GitHub.

## Configure Render environment variables

In Render → ai-company → Environment, add these variables without replacing the existing environment:

- `BMC_WEBHOOK_SECRET`: the webhook Signing Secret from Buy Me a Coffee
- `BMC_PRO_MEMBERSHIP_LEVEL_ID`: the numeric ID for the NetCmd PRO $69/month level
- `BMC_PRO_PRICE_USD`: `69`
- `BMC_PRO_CHECKOUT_URL`: the exact NetCmd PRO membership checkout URL

Save changes and let Render redeploy. The webhook deliberately ignores test events and any membership with a different level ID, currency, or amount.

## What happens after a valid live payment

1. The endpoint verifies the raw request body using HMAC-SHA256 and the webhook signing secret.
2. The event ID is stored to make repeated deliveries idempotent.
3. The subscription is recorded in Supabase.
4. A stable onboarding task is created for that subscription and assigned to all 14 roles.
5. The analysis worker runs the specialist roles and CEO synthesis in analysis-only mode.
6. Outputs appear in the internal Agent Console at `/admin`.

Cancellation and pause events update the membership status. No device credentials are collected, and no network configuration changes, deployments, external messages, or spending are executed by the agents.

## End-to-end test before announcing paid launch

- [ ] The public checkout URL opens the exact NetCmd PRO $69/month membership.
- [ ] Render has all four variables above configured.
- [ ] Buy Me a Coffee sends a dashboard test event and the endpoint acknowledges it. Test events do not activate a customer.
- [ ] Complete one permitted live test purchase/refund if the seller account and payment provider allow it.
- [ ] Confirm one membership row, one payment event, one onboarding task, 14 assignments, and agent outputs in Supabase/Agent Console.
- [ ] Confirm cancellation and pause events update membership status.
- [ ] Publish seller identity, privacy, tax/invoice, cancellation and refund terms before promoting the checkout publicly.

## Current launch boundary

The source code and database schema support this flow, but the integration is **not live until the seller creates the exact $69 membership level, configures the webhook, and adds the signing secret and level ID to Render**. Do not advertise that paid activation has passed until the end-to-end test is complete.
