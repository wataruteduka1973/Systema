# Seller action UI checks (Phase 4C)

Use an isolated SQLite database and an authenticated test owner. Do not refresh
synthetic auction URLs against Yahoo. Run `python manage.py verify --feature
seller-priority` for API ownership, refresh failure and persistence coverage.

1. Prepare a loss-risk listing with known costs. Filter by loss risk and click
   its price/cost action. The editor opens with expected price focused, without
   saving. Enter -1 and submit: browser validation blocks it and preserves input.
   Enter a profitable price and save: the item leaves the loss-risk filter and
   the total updates to zero while the selected filter remains unchanged.
2. Prepare a listing whose `missing_cost_fields` includes `shippingCostEstimate`.
   Filter by incomplete costs and click the action. The blank shipping field is
   focused. Fill it and save: the listing is reassessed and leaves that filter.
3. Prepare an ended listing. Its status action opens the management-state select
   without changing it. The editor explains that confirmed sale amounts are not
   yet supported. Public closure must not automatically select sold.
4. Prepare a listing with a manual price and no last observation. Its alert has
   exactly one public refresh button; the generic actions do not duplicate it.
   Refresh success/failure is covered with fixtures in the API suite.
5. A normal listing has no promoted action. Check the layout at 390px width,
   absence of horizontal overflow and browser console errors.

Steps 1–5 were checked locally on 2026-09-09 (refresh dispatch remains covered
by the existing API suite; no live Yahoo request was made for these UI checks).
