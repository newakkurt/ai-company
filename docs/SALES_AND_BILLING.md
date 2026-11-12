# Sales, BMC payments and product delivery

## Offer and BMC mapping

The five Shop products are BMC Shop Extras, not membership tiers. For these products, configure `BMC_EXTRA_PRODUCT_MAP` in Render. Each key is the Shop item's `extras[].id` from the webhook payload, mapped to one exact product release and USD unit price:

```json
{
  "EXTRA_ID": {
    "product_id": "prd-...",
    "product_code": "netcmd_pro",
    "product_name": "NetCmd PRO",
    "price_usd": "30.00"
  }
}
```

`BMC_PRODUCT_LEVEL_MAP` and the legacy `BMC_PRO_MEMBERSHIP_LEVEL_ID` / `BMC_PRO_PRODUCT_ID` / `BMC_PRO_PRICE_USD` settings remain available for membership tiers only.
## Publish a product before selling it

Generated releases are stored with status `review_required`. They cannot be downloaded by buyers until the owner:
1. Inspects the ZIP and its checksum.
2. Creates a `publish_product` approval scoped to the exact `product_id` and `sha256`.
3. Approves the one-time request.
4. Calls `POST /api/factory/products/{product_id}/publish` with the approval ID.
5. Adds the resulting product ID to the BMC_EXTRA_PRODUCT_MAP.

Full procedure: [Product publishing and delivery](PRODUCT_PUBLISHING_AND_DELIVERY.md).

## Webhook and ledger

Configure:
- `BMC_WEBHOOK_SECRET`
- `BMC_PRODUCT_LEVEL_MAP or the legacy level variables
- `APP_PUBLIC_URL
- BMC webhook endpoint: `https://ai-company-ferd.onrender.com/webhooks/buymeacoffee

The application verifies the raw webhook body using HMAC-SHA256 and the `x-signature-sha256` header. For Shop products, `extra_purchase.created` creates one ledger line and entitlement per mapped Shop item; `extra_purchase.updated` does not create a second sale; `extra_purchase.refunded` revokes the matching entitlement. Membership start creates a financial ledger event; an update is treated as a new payment only when the billing-cycle start changes. Cancellation, pause and refund events update membership access.
Ledger values are provider event amounts and estimated fees; they are not a confirmed payout or bank deposit. The BMC dashboard and bank statement remain the source of truth for settlement.

## Buyer delivery

When a valid live payment maps to an existing product release:
- A product entitlement is created for the BMC subscription.
- If the release is not yet published, the entitlement remains pending; after publication, the owner calls `POST /api/payments/entitlements/{subscription_id}/deliver).
- A random download token is generated; only its SHA-256 hash is stored.
- The download link expires after 7 days and permits up to 5 downloads.
- The download RPC checks token expiry, download count, entitlement status and release publication status.
- If SMTP is configured, the buyer receives a transactional delivery email. Otherwise the owner receives the secure link for manual delivery.
- Refund, cancellation or pause revokes the entitlement.

## Mail delivery configuration

Use a dedicated support mailbox and configure:
- `MAIL_IMAP_HOST`, `MAIL_SMTP_HOST), `MAIL_USER), `MAIL_PASSWORD), `MAIL_FROM)
- Keep `AI_COMPANY_MAIL_MODE=draft) for support auto-replies until sender authentication is verified.
- Transactional purchase delivery uses SMTP configuration independently of the auto-reply mode.

## Required live tests

1. BMC test event (`live_mode=false)) must not create a sale.
2. One controlled live membership must create exactly one payment ledger row and one entitlement.
3. Re-delivery of the same webhook must not create a second entitlement or duplicate email.
4. A pending entitlement must become deliverable after product publication.
5. Expired or exhausted download links must return 404.
6. Refund/cancel/pause must revoke access.
7. Confirm BMC payout and bank credit separately; record fees, FX, tax and settlement references with the accounting provider.

## Current verified state

At the last database inspection, no product release, entitlement or payment ledger entry existed. The code path is implemented and unit-tested on the feature branch; no real paid customer journey has yet been demonstrated.
