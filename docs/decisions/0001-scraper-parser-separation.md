# Scraper and parser separation

## Context

Yahoo! Auction page layouts can change without warning. The current project mixes network access, HTML scraping, normalization, and analysis in a small number of utility functions. That makes it harder for AI agents and maintainers to isolate the problem when a site structure changes.

## Decision

Keep the existing Django application structure, but make the Yahoo-specific fetch and parsing responsibilities explicit through a dedicated scraper module. The parser will own HTML extraction and normalization, while the API layer remains responsible for request validation and response shaping.

## Consequences

- Better isolation of external HTML breakage
- Easier regression detection via fixture-based parser tests
- Lower context cost for future AI agents working on Yahoo-specific changes
- Minimal behaviour change to the rest of the application

Tradeoff: the project does not fully re-architect the system beyond the necessary separation point, but this keeps the change safe and focused.
