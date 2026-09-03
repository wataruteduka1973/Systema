# Seller and Inventory Management

## Purpose

Move authenticated users from buying candidates into owned inventory, maintain acquisition facts, and calculate explainable pre-listing profitability without mixing buyer watch items with seller listings.

## Phase 3A Behavior

- The dedicated `/taskle/seller-management` page requires login.
- Users can register inventory manually or convert one of their own active `WatchItem` records.
- Conversion creates one `InventoryItem` transactionally and changes the source watch lifecycle to `purchased`; retries return the existing inventory instead of duplicating it.
- Inventory supports owner-scoped list, detail, update, delete, and status filtering.
- Stored fields include name, condition, category, acquisition cost, acquisition time, lifecycle status, and note.
- Profit simulation trusts the persisted acquisition cost, accepts expected sale price and estimated costs, and recalculates fee, total cost, estimated profit, margin, and break-even price on the server without persisting the simulation.
- Negative estimated profit is valid. Invalid money and fee-rate input is rejected.

## Security and Ownership

- Inventory and conversion APIs require an authenticated Django session and CSRF protection for mutations.
- Every lookup starts from `request.user`; another user's valid ID returns 404.
- Anonymous watch items must first be claimed through the existing login flow before conversion.

## Deferred to Phase 3B and Later

- `SellerListing`, Yahoo public listing-page refresh, listing snapshots, and listing status UI
- Yahoo credentials, cookies, access tokens, or automated listing actions
- Persisted sale outcomes and confirmed-profit analytics

## Related Files

- `Main/models/inventoryitem.py`
- `Main/domain/profitability.py`
- `Main/services/inventory.py`
- `Main/views/api.py`
- `Main/views/urls.py`
- `Main/templates/seller_management.html`
- `Main/static/JS/InventoryManagement.js`
- `Main/migrations/0016_inventory_phase3a.py`
- `tests/unit/test_profitability.py`
- `tests/integration/test_inventory.py`

## Verification

Run `python manage.py verify --feature inventory`. Verify login enforcement, owner isolation, idempotent watch conversion, server-side acquisition-cost use, invalid inputs, empty/filter states, and the rendered inventory workflow.
