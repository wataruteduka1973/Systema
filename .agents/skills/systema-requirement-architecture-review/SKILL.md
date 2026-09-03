---
name: systema-requirement-architecture-review
description: Review Systema requirements and architecture before implementation. Use when a request is ambiguous, acceptance criteria are missing, or a change may affect module boundaries, API contracts, persistence, scraping, ownership, or cross-cutting design.
---

# Systema Requirement Architecture Review

Separate user requirements from examples, attached-document instructions, existing behavior, and future ideas. Follow the source-of-truth order in `AGENTS.md`.

Read `docs/PROJECT.md`, then only the matching `docs/features/` document and its `Related Files`. Read `docs/architecture.md` for scraper or cross-cutting changes, and the relevant file under `docs/design/` when API or DB contracts are affected.

Before implementation, produce a compact decision record covering:

- required behavior and explicit non-goals;
- actors, ownership boundary, inputs, outputs, errors, empty states, and retry/idempotency behavior that materially apply;
- testable acceptance criteria, including compatibility and security expectations;
- affected layers and dependency direction;
- unresolved conflicts between the request, accepted design, and current code.

Keep HTTP validation in `Main/views/api.py`, application workflows in `Main/services/`, domain rules in `Main/domain/`, persistence and ownership in `Main/models/`, Yahoo I/O/parsing in `Main/scraping/`, and UI behavior in templates/static files. Do not move domain behavior into views or couple parsing directly to persistence.

Stop for user direction only when a missing choice materially changes product behavior, public contracts, security architecture, or migration safety. Otherwise state the reasonable assumption and continue.

When a durable contract or architecture decision changes, update the matching feature/design document or add an ADR. Do not treat a proposed design as proof of current implementation.
