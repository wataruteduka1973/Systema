# UI Design Context

## Direction

- Use a consistent red-gradient hero, white content cards, restrained shadows, and Bootstrap controls.
- Prefer shared navigation and reusable class names over page-specific copies.
- Tables must remain usable on narrow screens through responsive overflow or card presentation.
- Use inline status regions for expected validation and network errors; reserve dialogs for destructive confirmation.

## Core Patterns

- Page background: light neutral gray
- Content card: white, subtle border, rounded corners
- Primary action: red
- Secondary action: outline or neutral
- Destructive action: explicit danger styling and confirmation

## Related Files

- `Main/templates/header.html`
- `Main/templates/footer.html`
- `Main/templates/market_search.html`
- `Main/templates/Deep_Analysis.html`
- `Main/templates/Deep_Analysis_now.html`

Update this document when a reusable visual rule changes. Do not paste full page CSS here.
