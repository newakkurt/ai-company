# NetCmd PRO sales and payment operations

## Public offer
- Product: NetCmd PRO / AI Network Copilot
- Price target: USD 69 per month
- Checkout page: https://buymeacoffee.com/sevketkaynar
- Local checkout route: `/checkout`
- Sales page: `/` and `/sales`
- Finance dashboard: `/payments` (requires the server API key to load private data)

The $69 price is a positioning hypothesis, not proven willingness-to-pay. Domotz publicly lists $35 per site/month for network monitoring, while NetCmd PRO is positioned as a narrower, human-reviewed AI audit/coplilot offer rather than continuous monitoring. Validate price through qualified demos, paid conversions, cancellations and refund rates before treating it as market-validated. Sources: https://www.domotz.com/pricing.php

## Buy Me a Coffee setup (owner action required)
1. In Buy Me a Coffee creator dashboard, create/confirm a **monthly membership** specifically named NetCmd PRO at exactly USD 69/month. Do not use one-time Extra items as the subscription product.
2. Copy that membership level ID into Render as `BMC_PRO_MEMBERSHIP_LEVEL_ID`.
3. In Integrations, create a webhook with endpoint:
   `https://ai-company-ferd.onrender.com/webhooks/buymeacoffee`
4. Subscribe to `membership.started`, `membership.updated`, `membership.cancelled`, `membership.paused`, and refund events that the dashboard exposes (for example `donation.refunded`, `extra_purchase.refunded`, `commission_order.refunded`).
5. Copy the webhook Signing Secret into Render as `BMC_WEBHOOK_SECRET`. Never put it in GitHub or a chat message.
6. Send a test event and verify the endpoint delivery is HTTP 200. The test event has `live_mode=false` and is ignored for sales activation.
7. Confirm a real test subscription / low-risk live transaction in BMC before opening paid acquisition.

The application verifies the raw request body using HMAC-SHA256 and the `x-signature-sha256` header. Provider event IDs are used as unique ledger keys; duplicate sale/refund deliveries do not create a second financial ledger entry or repeat the sale notification.

## Render variables
- `BMC_PRO_PRICE_USD=69` (configured)
- `BMC_PRO_CHECKOUT_URL=https://buymeacoffee.com/sevketkaynar` (configured)
- `BMC_PRO_MEMBERSHIP_LEVEL_ID` (must be copied from the actual monthly membership)
- `BMC_WEBHOOK_SECRET` (must be copied from the BMC webhook details)

Do not set a guessed membership ID or webhook secret.

## Financial model
For each matching membership event, the ledger records:
- gross event amount and currency;
- BMC platform fee estimate (5%);
- estimated processing fee (3.4% + USD 0.30, reflecting the published 2.9% + 0.30 baseline plus the published 0.5% subscription surcharge);
- estimated net amount, additionally subtracting a 0.5% payout processing estimate.

These are estimates, not provider statements. International transaction fees, FX, tax, payment method and payout adjustments can change the actual result. Refund events are recorded as negative ledger entries.

BMC creator terms currently describe a 5% platform fee and Stripe payment processing; the help article describes the processing components and payout fee. Always reconcile against the actual BMC transaction and payout statements:
- https://buymeacoffee.com/terms
- https://help.buymeacoffee.com/en/articles/8105744-how-to-calculate-charges-on-your-payment

## Payout vs bank receipt
- A sale webhook is not a bank deposit.
- Record a provider payout only after it appears in BMC payout history.
- Record a bank settlement only after the credit appears in the bank account, using the bank reference/receipt.
- The finance dashboard keeps provider payouts and bank settlements separate and deduplicates a bank reference per payout.
- Monthly reports keep currencies separate.

## Events and notifications
- `membership.started` / `membership.updated`: validate membership level, USD currency, exact configured price and active status; create/refresh membership and a safe onboarding task.
- `membership.cancelled` / `membership.paused`: update membership status and notify the owner.
- `*.refunded`: write a negative financial ledger entry and notify the owner for reconciliation.
- A membership update with a non-active status is not activated and triggers a manual-review notification.
- Notifications use the existing Telegram owner notifier if `TELEGRAM_BOT_TOKEN` and owner chat ID are configured.

BMC's current public webhook docs list membership start/update/cancel/pause and several refund events. They do not guarantee a dedicated membership payment-failed event for every processor failure; inactive membership updates are therefore treated as a warning, not as proof of a specific decline reason.

## Operational verification
1. Open `/readyz` and check service readiness.
2. Open `/payments`, enter the server API key in the browser session, and verify the payment report loads.
3. Use BMC's test event; it must not activate a membership.
4. Verify a real matching membership produces one ledger entry and one owner notification.
5. Redeliver the same provider event; it must not create a second ledger row or sale notification.
6. Cancel/pause the membership and confirm status update.
7. Record payout and bank receipt separately; check monthly report against provider and bank statements.

The app does not automatically initiate refunds or bank transfers. Refunds are executed in the BMC dashboard under provider rules; the webhook records the event and alerts the owner.
