---
name: systema-change-review
description: Review a Systema diff or failed CI run before completion. Use for code or PR review, security and migration review, GitHub Actions failure analysis, regression assessment, and documentation synchronization.
---

# Systema Change Review

Review the focused diff as evidence. Do not modify code when the user requested review or diagnosis only. Prioritize actionable findings by impact and point to the smallest relevant file/line range. Distinguish confirmed defects from risks that require runtime evidence.

Always check correctness, edge cases, error handling, readability, unnecessary duplication, performance hazards, public API/DB compatibility, unrelated changes, and the applicable items in `docs/quality/definition-of-done.md`.

Apply these branches only when relevant:

- **Security:** authentication, authorization, owner filtering at query/write boundaries, CSRF, input validation, injection, secret/log disclosure, production settings, and unsafe external content. Include negative cross-user tests for owner-scoped resources.
- **Migration/DB:** forward/backward behavior, nullable/backfill/constraint order, indexes for actual query patterns, uniqueness and concurrent writes, table-lock or long-transaction risk, N+1 queries, rollback/data-loss implications, and SQLite/PostgreSQL differences. Never infer that a design table exists without checking migrations/models.
- **CI failure:** read the first meaningful failing job/step, reproduce with the repository command when practical, separate environment/tooling failure from product failure, fix the root cause, then rerun the narrow check. Do not claim GitHub Actions passed from local results.
- **Documentation sync:** update the matching feature document when behavior changes; `docs/design/api.md` for contracts, `docs/design/database.md` for schema/migration decisions, `docs/architecture.md` or an ADR for cross-cutting boundaries, and the roadmap when implementation status changes. Preserve the distinction between implemented, locally verified, and planned.

For reviews, lead with findings ordered by severity; if none, say so and list residual risks or unexecuted checks. For implemented changes, run the focused verification from `docs/testing.md`, inspect `git diff`, use `git diff --check`, and report `NOT VERIFIED` where required evidence is unavailable.
