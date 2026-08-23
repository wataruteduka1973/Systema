# ADR 0002: Centralize Market Comparison in Target Analysis

## Status

Accepted

## Decision

Market comparison is owned by target analysis rather than being duplicated across closed-market and current-price search screens.

## Reason

Target analysis already combines closed-market statistics, current listings, product condition, buying decisions, and watchlist actions. Keeping comparison there gives users one decision-oriented workflow and reduces duplicated UI and JavaScript.

## Consequences

- Market search remains focused on search, filtering, sorting, and saved data.
- Target analysis returns market statistics and per-item market comparison data.
- Comparison UI changes should start from `docs/features/target-analysis.md`.
