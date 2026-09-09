# Architecture

## System overview

This project is a Django-based Yahoo! Auction market analysis tool. It fetches auction data, stores search results in SQLite, and exposes JSON endpoints for search, market analysis, and pricing insights.

## Main components

- `Main/views/api.py`: HTTP entrypoints for client requests
- `Main/views/utils.py`: scraping, parsing, database write/read, and analysis logic
- `Main/models/`: persisted search history and scraped item records
- `Main/templates/` and `Main/static/`: UI assets used by the Django views
- `System_Config/settings.py`: project configuration and logging

## Responsibility layers

- `Main/domain/`: 外部I/Oに依存しない値変換・判定ロジック
- `Main/services/`: ユースケースとアプリケーション固有例外
- `Main/infrastructure/`: HTTP、DBなど外部I/Oの実装
- `Main/views/`: HTTP入力とレスポンスへの変換。`accounts.py`は認証、`developer.py`はstaff専用監視画面

既存のDjango app label、migration、importパスを維持するため、現時点ではリポジトリ全体を`src/`へ移していません。まず上記境界へロジックを移し、`views/utils.py`を段階的に薄くする方針です。

商品コンディション分類と状態別相場集計は`Main/domain/product_condition.py`に置き、スクレイピングやDjangoへ依存しない純粋ロジックとしてテストします。相場検索APIは既存の商品項目を維持し、分類項目と`conditionSummary`を追加する形で拡張します。

買い時判定は`Main/domain/buying_opportunity.py`に置き、相場中央値との価格比率、商品状態、残り時間から説明可能な判定結果を生成します。Systema内のウォッチ商品は`WatchItem`へユーザーとURLの組み合わせで保存し、保存・更新・シリアライズは`Main/services/watchlist.py`へ分離します。ターゲット分析で登録済み商品を再取得した場合は、追加時価格を維持したまま現在価格と判定を更新します。

Django標準のユーザー、セッション、パスワード検証を認証基盤に使用します。一般登録と一度限りの初回管理者作成を画面から行い、開発者ダッシュボードは`is_staff`ユーザーだけに制限します。

検索1回を`SearchRun`として記録し、`scraping`の商品行をその配下へ保存します。`SearchRun`、検索ワード履歴、ウォッチ商品は、ログイン時はユーザー、未ログイン時はDjangoセッションキーを所有者とします。履歴APIは現在の所有者で必ず絞り込み、所有者未割当の旧データは通常画面へ表示しません。ログイン・登録時には匿名セッションの検索履歴とウォッチ商品をユーザーへ移管します。

価格統計は`Main/services/market_statistics.py`でpandasを使って集計します。DataFrameやSeriesはサービス内部に閉じ、APIではJSONへ変換した中央値、四分位範囲、標準偏差、変動係数、外れ値候補数、ヒストグラムだけを返します。検索結果の比較UIは`Main/static/JS/MarketComparison.js`を相場検索と現在価格検索で共有します。

時系列集計と短期予測は`Main/services/time_series_analysis.py`へ分離します。IQRで外れ値候補を識別し、日次中央値、14日移動中央値、30日後予測と予測範囲を生成します。従来の予測APIフィールドは維持し、新しい日次推移と品質情報を追加します。

## Data flow

1. Client requests a search or market API.
2. API view validates input and delegates to the utility layer.
3. Scraper fetches Yahoo HTML or database data.
4. Parser extracts normalized item data.
5. Analysis code calculates rankings, trends, and predictions.
6. Results are returned as JSON or saved to the database.

## External dependencies

- Yahoo! Auction pages are scraped over HTTP.
- HTML parsing is done with BeautifulSoup.
- Data analysis uses pandas and NumPy. scikit-learn remains available for other analysis features.
- PostgreSQL is the standard development and test backend. SQLite remains an explicit compatibility fallback.

## AI-agent-friendly boundaries

For maintainability, treat the flow as:

- HTTP client / fetch layer
- parser / normalization layer
- domain analysis layer
- database repository layer
- API response layer

This project keeps the existing Django layout, but the scraper/parser boundary should remain as isolated as practical.

## Release expansion boundaries

将来APIとDBの詳細は`docs/design/api.md`と`docs/design/database.md`を正とします。既存`/taskle/` APIは互換層として維持し、新機能はversioned APIへ追加します。購入候補の`WatchItem`とユーザー自身の`SellerListing`は責務を分け、Yahoo認証情報を保存せず公開出品URLの手動登録から開始します。利益計算はdomain serviceへ集約し、在庫、出品観測、販売実績を分離して、仕入れ時予測と確定利益を比較できる構造にします。

Phase 3Aでは`InventoryItem`をログインユーザー所有とし、`WatchItem`からの変換だけをtransactional serviceで行う。出品前の利益計算は`Main/domain/profitability.py`に置き、HTTP入力やDjangoモデルへ依存させない。クライアントが送る仕入価格や計算済み利益は信用せず、保存済み仕入価格からサーバーで再計算する。

Phase 3Bは`SellerListing`と`SellerListingSnapshot`を追加する。APIは認証・入力と応答、`services/seller_listings.py`は所有者・費用・更新トランザクション、`scraping/seller_listing.py`は公開詳細ページ取得・解析、`domain/seller_listing.py`はURLと金額検証を担当する。HTTPは既存のallowlist・転送拒否・サイズ制限を再利用し、Yahoo認証情報は扱わない。外部通信中はDBトランザクションを保持せず、保存直前に所有者とupdated_atを再確認する。観測値と当時の計算条件を一括保存し、取得失敗や競合は旧データを維持する。出品費用は在庫からコピーするが以後は独立し、過去履歴を現在の費用で再計算しない。
