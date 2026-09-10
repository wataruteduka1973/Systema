# Systema Project Context

## Purpose

Systema is a Django application that searches Yahoo! Auctions data, stores owner-scoped search snapshots, and supports market, target, watchlist, and price analysis.

## Stack

- Backend: Django, Python
- UI: Django templates, Bootstrap, JavaScript
- Data: PostgreSQL for development and automated tests; SQLite is an explicit local fallback
- Tests: pytest and pytest-django

## Main Areas

| Area | Feature context |
|---|---|
| Unified market search | `docs/features/market-search.md` |
| Target analysis and comparison | `docs/features/target-analysis.md` |
| Stored price analysis | `docs/features/price-analysis.md` |
| Market prediction and backtest | `docs/features/market-prediction.md` |
| Authentication and profile | `docs/features/accounts.md` |
| Notification center | `docs/features/notifications.md` |
| Alert rules | `docs/features/alert-rules.md` |
| Seller and inventory management | `docs/features/seller-management.md` |
| Yahoo scraping | `docs/architecture.md` and parser tests |
| Release feature roadmap | `docs/plans/release-feature-roadmap.md` |
| Planned multi-market search and overseas sourcing | `docs/features/multi-market-sourcing.md` |
| API contracts and migration | `docs/design/api.md` |
| Database schema and migration | `docs/design/database.md` |

## Design Principles

- Keep API validation in `Main/views/api.py` and application logic in services or `Main/views/utils.py`.
- Keep scraper, parser, normalization, and persistence boundaries separate.
- Scope saved searches, scraped results, and watchlists to the request owner.
- Use fixture-based parser tests; never use bulk live scraping in tests.
- Keep UI changes localized and reuse established shared navigation and Bootstrap patterns.
- Keep secrets and environment-specific values out of source control.

## Current Product Decisions

- Market search unifies closed, current, and saved-data search modes.
- Market comparison belongs to target analysis.
- Word cloud and duplicated price-distribution UI are removed.
- Target analysis owns buying-opportunity and watchlist workflows.
- Buyer watch items and seller listings are separate resources.
- Seller support starts with manual listing URL registration and never stores Yahoo credentials.

## Work Routing

Read this file, then one matching feature document. Open only its Related Files initially. Use targeted search to expand the scope when an import, route, API contract, or test proves it necessary.
