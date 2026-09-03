---
name: systema-implementation-tests
description: Implement scoped Systema changes using project coding standards and risk-based tests. Use when adding or changing Django, domain, service, parser, API, persistence, or UI behavior and generating unit, integration, regression, fixture, or E2E coverage.
---

# Systema Implementation Tests

Route context through `AGENTS.md` and `docs/PROJECT.md`, then one matching feature document and its `Related Files`. Inspect the nearest working pattern before creating a new abstraction.

Implement the smallest complete behavior slice. Preserve public API/DB compatibility and owner scoping unless the request explicitly changes them. Keep validation, service, domain, model, scraper, and UI responsibilities in the project boundaries documented by `AGENTS.md`. Use the configured Python 3.13, Ruff, Black, mypy, pytest markers, and coverage settings from `pyproject.toml`; do not invent parallel conventions.

Select tests from the risk:

- `tests/unit/`: pure domain rules, normalization, calculations, and fixture-based parser cases;
- `tests/integration/`: Django views, DB behavior, API contracts, CSRF/authentication, and cross-user ownership denial;
- regression test: every reproduced bug, at the lowest layer that proves the cause;
- `tests/e2e/`: only when browser or running-application behavior cannot be established below that layer.

Cover meaningful valid, boundary, invalid, empty, and failure cases. For Yahoo HTML behavior, use representative files under `tests/fixtures/yahoo/`; never make bulk live requests in tests. Do not add assertions that only mirror implementation details.

During implementation run `python manage.py verify` or the matching `python manage.py verify --feature <name>`. Use `--full` only at a roadmap Phase boundary or when explicitly requested. If a UI changes, also inspect the rendered behavior, validation/error/empty states, primary viewports, accessibility basics, and console errors when a browser is available.

Before declaring completion, apply `docs/quality/definition-of-done.md`. Report commands actually executed and mark unavailable evidence as `NOT VERIFIED` with the reason.
