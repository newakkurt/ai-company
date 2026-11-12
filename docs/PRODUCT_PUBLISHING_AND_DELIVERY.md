# Product publishing and paid delivery

Generated product releases remain `review_required`. They are not purchasable or downloadable until the owner publishes the exact artifact.

## Publish a release

1. Read the product's `product_id` and `sha256` from `GET /api/factory/products/{product_id}`.
2. Create an approval request with action `publish_product` and scope exactly:
   `{"product_id":"...","sha256":"..."}`.
3. Approve the request through `POST /api/approvals/{approval_id}/decision`.
4. Call `POST /api/factory/products/{product_id}/publish` with the approved `approval_id`.

The approval is one-time and bound to that exact artifact checksum.

## Map Buy Me a Coffee Shop items

For Shop Extras, set `BMC_EXTRA_PRODUCT_MAP` in Render. Keys are the item IDs in the webhook's `data.extras[].id`; values map each shop item to a published release and exact USD unit price:

```json
{
  "LEVEL_ID": {
    "product_id": "prd-...",
    "product_code": "netcmd_pro",
    "product_name": "NetCmd PRO",
    "price_usd": "30.00"
  }
}
```

Also configure `BMC_WEBHOOK_SECRET` and `APP_PUBLIC_URL`. `BMC_PRODUCT_LEVEL_MAP` remains available only for membership-tier sales; it is not the Shop Extras map.

## Delivery behavior

- A verified live `extra_purchase.created` event is mapped by each `extras[].id` and recorded in the payment ledger. Membership events remain supported separately.
- A payment creates an entitlement as long as the mapped product release exists. If the release is not yet published, the entitlement remains pending rather than being lost.
- Only a product with status `approved_for_sale` receives a download token.
- After publishing a previously pending release, the owner can call `POST /api/payments/entitlements/{subscription_id}/deliver` to finish delivery.
- The system creates a random download token; only its SHA-256 hash is stored.
- The link expires after 7 days and allows up to 5 downloads.
- Refund, cancellation or pause revokes the entitlement.
- If SMTP is configured, a transactional delivery email is sent. Otherwise the owner receives the secure link through the configured notifier for manual delivery.
- Repeated webhook events do not create duplicate entitlements or send duplicate delivery emails.

This does not verify BMC payout settlement or issue invoices/tax documents; those remain separate finance and accounting steps.
