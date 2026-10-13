# Market Analysis (相場分析)

## Purpose

One page (`/taskle/Deep_Analysis`, header "相場分析") for a keyword's market: owner-scoped saved
closed-auction data and the 30-day prediction. It replaced the separate 情報分析 and 相場予想 pages,
whose price-trend charts overlapped.

## Behavior

- The keyword comes from one of two tabs:
  - 検索履歴から選ぶ: a saved keyword. 保存データを分析 shows summary cards and condition statistics
    from the latest stored run without contacting Yahoo. 相場データの更新 / 削除 work as before.
  - 新しいキーワード: free input plus popular-word buttons.
- 相場予想を表示 (either tab) calls `prediction_market`, which fetches closed auctions live. Stored rows
  keep only the search day, not each auction's end date, so stored data alone cannot draw daily
  trends or a forecast. Adding an end-date column is a possible future change (schema migration;
  old rows would have no date). The fetch only runs on the button, never on keyword selection.
- The prediction section (daily median, 14-day rolling median, 30-day forecast and interval, and
  backtest) replaces the former per-update median/IQR chart. `get_market_data` still returns
  `analysis.timeSeries` for API compatibility; the page no longer draws it.
- After a new-keyword prediction, このキーワードを保存 stores the keyword through
  `update_market_data` (one closed search), switches to the history tab with it selected, and shows
  its stored summary. It is hidden when the keyword is already saved.
- Switching tabs by hand clears the shown results. `?source=new` opens the new-keyword tab, and
  `?source=new&keyword=…` (market search's 相場分析で予想を見る) also runs that prediction once;
  `/taskle/Yahuoku_prediction` redirects there so old links keep working.

Word cloud and duplicated price-distribution charts are not part of this feature.

## Related Files

- `Main/templates/Deep_Analysis.html`
- `Main/static/JS/Deep_Analysis.js` (tabs, stored analysis, save/update/delete)
- `Main/static/JS/MarketPrediction.js` (prediction rendering, shared `window.SystemaPrediction`)
- `Main/views/urls.py` (`Deep_Analysis`, `Yahuoku_prediction` redirect)
- `Main/views/utils.py` (`get_market_data_logic`, `prediction_market_logic`)
- `Main/services/time_series_analysis.py`
- `Main/services/market_statistics.py`
- `tests/e2e/test_market_analysis_browser.py`
- `tests/integration/test_page_layout.py`
- `tests/integration/test_api.py`

## Verification

Use stored owner-linked fixtures and a monkeypatched `scrape_data`. Verify both tabs, saving a new
keyword, the redirect, empty datasets, summary cards, and condition statistics.
