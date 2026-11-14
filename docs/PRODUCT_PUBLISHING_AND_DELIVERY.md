# Product publishing and paid delivery

Generated product releases remain `review_required`. They are not purchasable or downloadable until the owner publishes the exact artifact.

## Repair and offline runtime QA\n\nIf the stored artifact fails ZIP integrity checks, first run the guarded **Rebuild ConfigGuard Lite Release Artifact** workflow: [open rebuild workflow](https://github.com/newakkurt/ai-company/actions/workflows/rebuild-configguard-release.yml). It rebuilds the package from the reviewed repository source, verifies the ZIP locally, and replaces only the artifact bytes, byte count, checksum and manifest for the exact ConfigGuard Lite release while its status remains `review_required`. It cannot publish, create payment records, or grant entitlements. After a successful rebuild, run the manual GitHub Actions workflow **Offline Product Release QA**: [open workflow](https://github.com/newakkurt/ai-company/actions/workflows/product-offline-qa.yml). Select the exact `product_id` (the current ConfigGuard Lite release is `prd-1cdfbb2727ef`) and choose **Run workflow**. The workflow retrieves the stored artifact from Supabase, verifies its byte count and SHA-256, checks archive paths and source for unsafe patterns, then runs the package tests in an isolated Docker container with networking disabled. It does not modify `release_status`, create an approval, publish, or grant downloads. Review the complete successful run before continuing.\n\n## Publish a release

1. Read the product's `product_id` and `sha256` from `GET /api/factory/products/{product_id}`.
2. Create an approval request with action `publish_product` and scope exactly:
   `{"product_id":"...","sha256":"..."}`.
3. Approve the request through `POST /api/approvals/{approval_id}/decision`.
4. Call `POST /api/factory/products/{product_id}/publish` with the approved `approval_id`.

The approval is one-time and bound to that exact artifact checksum.

## Map Buy Me a Coffee Shop items

If the BMC products are listed under Shop, set `BMC_EXTRA_PRODUCT_MAP` in Render. Keys are the item IDs in the webhook's `data.extras[].id`; values map each shop item to a published release and exact USD unit price:

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

Also configure `BMC_WEBHOOK_SECRET` and `APP_PUBLIC_URL`. A recurring PRO membership needs the actual `BMC_PRO_MEMBERSHIP_LEVEL_ID`; `BMC_PRODUCT_LEVEL_MAP` is for additional membership-tier mappings. A one-time coffee/support payment must not grant recurring PRO access.

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
