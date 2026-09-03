# Systema Agent Guide

## Purpose

Systema is a Django application for Yahoo! Auctions market analysis. Agents should autonomously inspect, implement, verify, and document scoped changes. A change is not complete merely because it runs; correctness, regression safety, and reproducible verification are required.

## Token-Efficient Context Routing (Mandatory)

Token optimization is a project requirement, not an optional preference.

1. Read this file and `docs/PROJECT.md` first.
2. Read only the matching document under `docs/features/`; use `docs/architecture.md` only for cross-cutting or scraper work.
3. Open the feature document's `Related Files` first. Expand with targeted `rg` only when an import, route, API contract, or test proves it necessary.
4. Do not scan the whole repository, load unrelated feature documents, or reread known files by default.
5. Keep one task focused on one theme. Do not mix unrelated cleanup or refactoring.
6. Prefer focused diffs, narrow line ranges, concise failure output, and summaries of successful checks. Do not return full files or full successful logs unless requested.
7. Run `python manage.py verify` or one `--feature` suite during implementation. Run `--full` only once after a roadmap Phase is complete or in CI; a cross-cutting change alone does not require repeated full-suite runs.
8. For a clear request, inspect, implement, self-review, and verify in one pass. Do not add proposal rounds unless a material decision is unresolved.
9. Record durable behavior or architecture decisions in the matching feature document or ADR so future agents do not need chat history.
10. Keep this guide concise. Put detailed feature knowledge in routed documents rather than expanding global instructions.

## Source of Truth

Use the following priority when sources conflict:

1. Current user requirements
2. Requirements and accepted product decisions
3. ADRs and architecture documents
4. Feature, DB, API, and module design documents
5. Approved implementation plans
6. This guide
7. Existing code

Do not silently choose a side when design and implementation materially conflict. Identify the conflict, recommended resolution, reason, and affected scope.

## Project Boundaries

- `Main/views/api.py`: endpoints and request validation
- `Main/views/utils.py`: legacy orchestration; prefer services for new domain logic
- `Main/services/`: application and analysis services
- `Main/domain/`: domain rules and value logic
- `Main/models/`: persisted data and ownership
- `Main/scraping/`: Yahoo retrieval and parsing boundary
- `Main/templates/`, `Main/static/`: Django UI
- `tests/`: unit, integration, and regression coverage
- `System_Config/`: Django settings and routing

Preserve owner scoping for saved searches, scraped results, and watchlists. Keep scraper, parser, normalization, persistence, and analysis responsibilities separate.

## Before and During Implementation

- Inspect the relevant implementation, nearest similar pattern, dependencies, conventions, and test entrypoint before editing.
- Reuse an existing mechanism when it satisfies the requirement; avoid duplicate abstractions and speculative infrastructure.
- For larger changes, maintain a short plan covering purpose, targets, data flow, order, tests, and risks. Keep implementation units small.
- Preserve public API behavior unless the requested change explicitly requires a contract change.
- Avoid unrelated changes, broad refactors, circular dependencies, layer violations, oversized modules, and premature generalization.
- Maintain type safety. Do not hide errors with unsafe casts, swallowed exceptions, disabled lint rules, or deleted tests.
- Never add secrets, credentials, or environment-specific values to source control.
- Do not change migrations or schema without an explicit need and impact assessment.

## Testing and Verification

- Treat implementation and tests as one change. Add or update unit, integration, regression, and UI tests in proportion to risk.
- For bug fixes, prefer: reproduce with a test, identify root cause, fix it, run related tests, then search narrowly for the same pattern.
- Yahoo HTML regressions must use fixtures. Never use bulk live scraping in tests.
- Discover commands from project configuration and CI; do not invent commands or report unexecuted checks as successful.
- Use the available formatter, linter, type checker, tests, build, Django checks, and migration checks appropriate to the change.
- For UI changes, inspect the rendered page when available: layout, interactions, validation, loading/error/empty states, responsiveness, accessibility basics, and console errors.
- Report unavailable checks and the reason. Static validation is not runtime proof.

Common commands:

- Setup: `pip install -r requirements.txt`
- Run: `python manage.py runserver`
- Tests: `pytest -q`
- Django checks: `python manage.py check`
- Static collection: `python manage.py collectstatic`

## Project Skills

Reusable Systema workflows live under `.agents/skills/`:

- `systema-requirement-architecture-review`: use before implementation when requirements, acceptance criteria, contracts, or layer boundaries need review.
- `systema-implementation-tests`: use for scoped implementation and risk-based unit, integration, regression, fixture, or E2E tests.
- `systema-change-review`: use for PR/code review, security and migration checks, CI failure analysis, and documentation synchronization.
- `systema-dependency-maintenance`: use for dependency or GitHub Actions upgrades and compatibility assessment.

Use the smallest set that covers the task. These skills specialize this guide; they do not override user requirements, authorization boundaries, routed feature documents, or `docs/quality/definition-of-done.md`.

## Self Review

Before completion, review the focused diff as a maintainer:

- Architecture: responsibilities and dependencies remain clear.
- Correctness: requirements, edge cases, and error handling are covered.
- Regression: existing behavior and public interfaces remain safe.
- Security: authentication, authorization, ownership, validation, injection, secrets, and disclosure risks are addressed.
- Maintainability: the solution is the simplest adequate approach, with clear names and no unnecessary duplication.
- Scope: no unrelated user changes were overwritten or included.

## Documentation

Update the matching feature document or ADR when behavior, ownership, contracts, constraints, or non-obvious decisions change. Document reusable knowledge such as environment pitfalls and important regression causes; do not record routine work history.

## Stop Conditions

Stop and request direction instead of guessing when the task requires:

- resolving a materially ambiguous requirement or conflicting accepted design;
- a destructive operation or migration with possible data loss;
- a security architecture change;
- an unrequested breaking public API change;
- a new paid service or infrastructure commitment;
- a material design expansion beyond the requested scope.

Report the problem, evidence, options, recommendation, and impact.

## Definition of Done and Report

Complete only when the requested behavior is implemented, relevant tests and checks pass, the focused diff is self-reviewed, and required documentation is updated. If `docs/quality/definition-of-done.md` exists, also satisfy it.

Keep the final report concise:

- Changes
- Verification and tests
- Documentation
- Remaining issues or unexecuted checks (`None` when empty)
