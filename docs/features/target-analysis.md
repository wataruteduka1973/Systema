# Target Analysis

## Purpose

Compare current listings with the closed-auction market and identify buying opportunities.

## Behavior

- Searches closed and current data for one keyword.
- Calculates the closed-price median and market statistics.
- Adds market difference, condition, and buying-decision data to current items.
- Allows two to four current items to be compared side by side.
- Owns the Systema watchlist workflow.
- Keeps owner-scoped watch decisions as notes, priorities, and lifecycle states without allowing observation refreshes to overwrite them.
- Records price, bid, remaining-time, and condition snapshots on registration and meaningful observation changes.
- Shows price-history analysis including observation count, trend, minimum/maximum price, bid change, and market-median discount; one observation is reported as insufficient data rather than a trend.
- Separates active, purchased, skipped, ended, and archived buying candidates with status and priority filters.
- Uses one integrated form for keyword and all target-analysis criteria.
- The keyword is the saved condition's display name; the UI does not ask for a separate title.
- The related-feature links, criteria, action, and frequent-word aid share one card.
- Submitting the form by button or Enter starts the same target-analysis flow and shows a loading state until completion.
- Authenticated users can inspect, edit, delete, and rerun their owner-scoped saved conditions without leaving target analysis; rerun results refresh the median and recommendation table in place.
- Authenticated users automatically save the complete criteria and execute it as a saved search, so the same displayed result remains available on the profile; the keyword is the default name, and an existing same-named condition is updated instead of duplicated.
- Profile creation and rerun use the same complete target-analysis criteria contract without involving market search.
- Saved-search execution persists the exact displayed recommendation result for profile-page revisits.

## Related Files

- `Main/templates/Deep_Analysis_now.html`
- `Main/static/JS/Deep_Analysis_now.js`
- `Main/static/JS/MarketComparison.js`
- `Main/views/utils.py` (`complex_market_data_logic`)
- `Main/services/market_statistics.py`
- `Main/domain/buying_opportunity.py`
- `Main/services/watchlist.py`
- `Main/services/watchlist_analysis.py`
- `Main/models/watchitem.py`
- `Main/migrations/0015_watchlist_phase2.py`
- `tests/integration/test_api.py`
- `tests/unit/test_watchlist_analysis.py`
- `tests/unit/test_buying_opportunity.py`
- `tests/unit/test_market_statistics.py`

## Product Decision

Market comparison is centralized here. See `docs/decisions/0002-centralize-market-comparison.md`.

## Verification

Use mocked scraper results or fixtures. Verify market statistics, comparison labels, buying decisions, unknown remaining time, watchlist ownership, user-managed-field preservation, snapshot creation, history analysis, and insufficient-data behavior.

## Phase 3C purchase decisions

Authenticated watch rows provide a purchase-budget editor and reusable private cost settings. Empty costs mean unknown; zero must be entered explicitly. The editor supports manual sale price with evidence note or an owned retained closed-search median, and shows references, evidence count, observation time and unknown sale period. Existing buying labels remain price-comparison labels.

Saving calculates target-profit purchase limit and expected profit on the server, retaining the exact observation and assumptions. A later template change has no effect on saved decisions. Purchase conversion copies the last decision and locks further edits; changed actual acquisition price is used by the inventory simulator without rewriting the original judgment. Read-only rendering of original decisions is shared with inventory and seller pages. No automatic purchase, alert, or live evidence retrieval is added.

Related files: `Main/domain/purchase_budget.py`, `Main/services/purchase_budget.py`, `Main/models/purchasebudget.py`, `Main/static/JS/PurchaseBudget.js`, `Main/migrations/0018_purchase_budget_phase3c.py`, `tests/unit/test_purchase_budget.py`, `tests/integration/test_purchase_budget.py`.

Verification: `python manage.py verify --feature purchase-budget`. Include unknown/zero, rounding, negative profit, limits, ownership/CSRF, evidence-copy retention, default changes, idempotent conversion, and seller unknown-cost propagation.
