# Architecture

## System overview

This project is a Django-based Yahoo! Auction market analysis tool. It fetches auction data, stores search results in SQLite, and exposes JSON endpoints for search, market analysis, and pricing insights.

## Main components

- `Main/views/api.py`: HTTP entrypoints for client requests
- `Main/views/utils.py`: scraping, parsing, database write/read, and analysis logic
- `Main/models/`: persisted search history and scraped item records
- `Main/templates/` and `Main/static/`: UI assets used by the Django views
- `System_Config/settings.py`: project configuration and logging

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
- Data analysis uses NumPy and scikit-learn.
- SQLite is the default database backend.

## AI-agent-friendly boundaries

For maintainability, treat the flow as:

- HTTP client / fetch layer
- parser / normalization layer
- domain analysis layer
- database repository layer
- API response layer

This project keeps the existing Django layout, but the scraper/parser boundary should remain as isolated as practical.
