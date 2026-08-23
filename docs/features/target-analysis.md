# Target Analysis

## Purpose

Compare current listings with the closed-auction market and identify buying opportunities.

## Behavior

- Searches closed and current data for one keyword.
- Calculates the closed-price median and market statistics.
- Adds market difference, condition, and buying-decision data to current items.
- Allows two to four current items to be compared side by side.
- Owns the Systema watchlist workflow.

## Related Files

- `Main/templates/Deep_Analysis_now.html`
- `Main/static/JS/Deep_Analysis_now.js`
- `Main/static/JS/MarketComparison.js`
- `Main/views/utils.py` (`complex_market_data_logic`)
- `Main/services/market_statistics.py`
- `Main/domain/buying_opportunity.py`
- `Main/services/watchlist.py`
- `tests/integration/test_api.py`
- `tests/unit/test_buying_opportunity.py`
- `tests/unit/test_market_statistics.py`

## Product Decision

Market comparison is centralized here. See `docs/decisions/0002-centralize-market-comparison.md`.

## Verification

Use mocked scraper results or fixtures. Verify market statistics, comparison labels, buying decisions, unknown remaining time, and watchlist ownership.
