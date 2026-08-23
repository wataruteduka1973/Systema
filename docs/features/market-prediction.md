# Market Prediction and Backtest

## Purpose

Predict the 30-day market price from closed auctions and show historical forecast accuracy.

## Behavior

- Uses daily medians from the preceding 90 days for the current forecast.
- Backtests past cutoffs using only data available at each cutoff.
- Compares predictions with the median observed around each 30-day target date.
- Reports MAE, MAPE, direction accuracy, interval coverage, and per-window results.
- Shows a clear unavailable state when history is too short.

## Related Files

- `Main/templates/Yahuoku_prediction.html`
- `Main/static/JS/Yahuoku_prediction.js`
- `Main/views/utils.py` (`prediction_market_logic`)
- `Main/services/time_series_analysis.py`
- `tests/unit/test_time_series_analysis.py`
- `tests/integration/test_api.py`

## Verification

Use deterministic dated price fixtures. Verify that target dates follow cutoffs, linear trends produce near-zero error, and short histories return an unavailable result.
