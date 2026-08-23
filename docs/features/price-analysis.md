# Stored Price Analysis

## Purpose

Analyze owner-scoped saved closed-auction snapshots over time.

## Output

- Summary metrics
- Median and interquartile-range trend by snapshot
- Market statistics by product condition

Word cloud and duplicated price-distribution charts are not part of this feature.

## Related Files

- `Main/templates/Deep_Analysis.html`
- `Main/static/JS/Deep_Analysis.js`
- `Main/views/utils.py` (`get_market_data_logic`)
- `Main/services/time_series_analysis.py`
- `Main/services/market_statistics.py`
- `tests/unit/test_time_series_analysis.py`
- `tests/integration/test_api.py`

## Verification

Use stored owner-linked fixtures. Verify empty datasets, snapshot history, summary cards, and condition statistics.
