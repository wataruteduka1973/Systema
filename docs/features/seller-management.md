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

## Phase 3B Behavior

- The same management page has a separate seller-listing section: manual URL registration, optional owned inventory selection, CRUD, status filter, and pagination (20 default, 100 maximum).
- Only canonical `https://auctions.yahoo.co.jp/jp/auction/<auctionId>` URLs are stored; tracking queries/fragments are removed. Alternate hosts, credentials, non-HTTPS schemes, nonstandard ports and non-item paths are rejected. The URL and inventory relationship are immutable after registration; a relisted URL is a new record.
- Inventory acquisition cost is copied at creation, not dynamically joined. Subsequent listing cost edits do not rewrite existing snapshots. Deleting inventory retains the listing and its copied costs; deleting a listing removes its snapshots, not inventory.
- User inputs: name, condition, note, acquisition cost, shipping/packaging/other estimates, fee rate, target profit, manual market median, optional expected sale price, and management status. Fee rate accepts at most five decimal places. Money is integer yen, 0 through 1 trillion. Unknown payload fields (including credentials and calculated profit) are rejected.
- The displayed market median is explicitly manual, not an automatic market search. Price selection is explicit expected price, otherwise latest observed current price, otherwise a positive manual median. Without a price, profit is unknown rather than a fabricated zero-price result.
- Each successful manual refresh retrieves one public page using the shared HTTPS allowlisted, no-redirect, response-size-limited HTTP boundary (15-second timeout, no automatic retry). It updates public title, prices, bids, start/end timestamps, and observed status; user costs, median, expected price, note and target are preserved.
- Parser contract: `__NEXT_DATA__.props.pageProps.initialState.item.detail.item`, matching `auctionId`, `price`, `bids`, timezone-aware `endTime`, and `status`. Optional `initPrice`, `bidorbuy`, and `startTime` are captured. Missing/invalid required fields, wrong item IDs, login pages or unsupported shapes fail closed; recommendation entries are never substituted. The fixture is reduced synthetic data matching the observed public schema, with no seller identity or token fields.
- `draft/active/ended` follow the public observation on refresh. `sold/cancelled/relist` are explicit manual decisions and are preserved. Public closure never implies a confirmed sale. Inventory lifecycle is managed independently; a listing cannot automatically mark stock sold.
- Refresh has a separate user cache rate limit (10 requests / 60 seconds, `SELLER_REFRESH_RATE_LIMIT` / `SELLER_REFRESH_RATE_WINDOW_SECONDS` Django settings). With a process-local cache this is per process; deployment needs a shared cache for multi-worker enforcement.
- Ownership is checked before I/O and again under a row lock before persistence. A concurrent edit/refresh causes 409; deletion or ownership loss causes 404. No transaction spans external I/O. Observation and snapshot commit together, or neither does. Fetch/parse failures leave prior observations and history untouched.
- Every accepted refresh creates one timestamped snapshot, including unchanged prices (a new observation). Unique `(seller_listing, observed_at)` rejects a duplicate timestamp; racing requests cannot overwrite a newer result. There is no background polling or batch scraping.
- Snapshots retain price, bids, remaining seconds, manual median, expected price, fee, signed profit, observation status, and the exact cost/rate/price-source/target inputs. History is newest first with pagination and price/bid/profit deltas within the displayed page. Profit changes may reflect changed assumptions, not only market prices.

## Deferred to Later Phases

- Yahoo credentials, cookies, access tokens, or automated listing actions
- Automatic market matching, sell-through risk, advanced scenario simulations and recommendations
- Persisted sale outcomes and confirmed-profit analytics (Phase 7)

## Related Files

- `Main/models/inventoryitem.py`
- `Main/domain/profitability.py`
- `Main/services/inventory.py`
- `Main/views/api.py`
- `Main/views/urls.py`
- `Main/templates/seller_management.html`
- `Main/static/JS/InventoryManagement.js`
- `Main/migrations/0016_inventory_phase3a.py`
- `Main/models/sellerlisting.py`
- `Main/domain/seller_listing.py`
- `Main/services/seller_listings.py`
- `Main/scraping/seller_listing.py`
- `Main/infrastructure/http.py`
- `Main/static/JS/SellerListings.js`
- `Main/migrations/0017_seller_listing_phase3b.py`
- `tests/unit/test_seller_listing.py`
- `tests/integration/test_seller_listings.py`
- `tests/fixtures/yahoo/seller_detail_active.html`
- `tests/fixtures/yahoo/seller_detail_ended.html`
- `tests/unit/test_profitability.py`
- `tests/integration/test_inventory.py`

## Verification

Run `python manage.py verify --feature inventory`. Verify login enforcement, owner isolation, idempotent watch conversion, server-side acquisition-cost use, invalid inputs, empty/filter states, and the rendered inventory workflow.

For seller workflows run `python manage.py verify --feature seller-management`. Include negative ownership and CSRF tests, invalid URLs/money/credentials, copy-on-create costs, stale refresh rejection, atomic rollback, immutable history, rate limits, and synthetic active/ended/parser-failure fixtures. A live page check is separate evidence and never part of automated tests.

Local verification on 2026-09-03: seller feature suite passed; one public page was parsed successfully (not a guarantee for all Yahoo listing types). Isolated SQLite browser checks covered login, empty/list states, registration from inventory, fee edits, refresh and two observations, duplicate errors, no console errors on the successful workflow, and 390px mobile width. After the legacy formatting/type cleanup, repository-wide Black, mypy, Ruff, the 231-test suite, Django/migration checks, documentation build, JavaScript syntax check, and diff check passed locally. Production DB migration, PostgreSQL concurrency, and GitHub CI remain separate evidence.

## Phase 3C acquisition assumptions

Inventory and seller views display the immutable purchase decision copied from a watch candidate. Inventory simulation preloads these assumptions and uses the actual saved acquisition cost. Seller creation copies known estimates, target, expected sale price and separate acquisition shipping before explicit overrides. Unknown inherited expenses suppress profit until explicitly entered; blank UI fields expose them. Original purchase assumptions and existing seller observations never change when defaults or current costs change. Seller history displays unknown fee/profit and unknown deltas without coercing null to zero. See `target-analysis.md` Phase 3C and the API/DB Phase 3C contracts for routing and migration impact.

## Phase 4 direction: seller support

Further feature work is centered on `/taskle/seller-management`; the user profile is not expanded with comparison or purchase-support panels. Seller support will prioritize a concise next-action view for each listing: refresh public information, complete missing cost inputs, review loss/target status, check ending and bidding signals, and enter a confirmed sale result when available. Existing purchase-budget data is read-only context for seller work and is not expanded into additional buyer guidance. Automatic Yahoo listing changes, credentials, cookies, and purchase actions remain out of scope.
