# Project Overview

This project is a Django application for Yahoo! Auction market analysis. It fetches auction data, stores search results in SQLite, and exposes analysis APIs for product trend, current listings, and market prediction.

# Architecture

- `Main/views/api.py`: API endpoints and request validation
- `Main/views/utils.py`: search, scraping, database, and analysis logic
- `Main/models/`: Django models for persisted auction/search data
- `Main/static/` and `Main/templates/`: frontend assets and HTML views
- `tests/`: API and regression tests
- `System_Config/`: Django settings and routing

# Important Rules

- Keep changes minimal and behavior-preserving.
- Prefer targeted edits over large refactors.
- Do not modify DB migrations or schema without explicit reason.
- Do not commit secrets, API keys, or credentials.
- Do not run large external scraping jobs during tests.
- Preserve the existing Django project structure unless a narrow fix requires it.

# Commands

- Setup: `pip install -r requirements.txt`
- Run app: `python manage.py runserver`
- Run tests: `pytest -q`
- Django checks: `python manage.py check`
- Collect static: `python manage.py collectstatic`

# Change Guidelines

- For Yahoo HTML changes, inspect the scraper/parser boundary first.
- Keep scraper, parser, normalization, and database logic separated as much as possible.
- Update the nearest test file when changing request/response behavior.
- Use fixtures for HTML parsing regressions instead of live network calls.

# Testing

- Run the relevant pytest target after code changes.
- Prefer small unit or parser-focused tests for the changed behavior.
- For Yahoo HTML changes, validate fixture-based parsing before broader app checks.

# Do Not

- Do not perform broad refactors without a clear reason.
- Do not change public API response formats silently.
- Do not delete tests to hide regressions.
- Do not add large live scraping loops to the test suite.
- Do not add secrets or environment-specific config into source control.
