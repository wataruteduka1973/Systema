# UI Design Context

## Direction

- Every page uses the calm beige palette of the header, footer and top page.
  - `static/CSS/theme.css` is loaded by `base.html` after page styles. It defines the `--systema-*`
    variables and remaps Bootstrap's colour tokens and button classes.
  - Base colours: background `#f7f2ea`, surfaces `#fdfaf6`, borders `#ddd3c5`, text `#362f28`.
  - Accents: coral `#c2532c` for primary and links, teal `#2f8f78` for success, gold `#a9823f` for
    warning, muted red `#b0412e` for danger.
  - Page heroes (`.hero-section`, `.market-hero`) are a quiet beige band with dark Shippori Mincho
    headings. The top page hero (`.hero-top`) keeps its own layout.
  - The top page additionally uses Zen Kaku Gothic New body text (`static/CSS/start-menu.css`).
  - New page styles use the variables or Bootstrap classes, not new hard-coded saturated colours.
    Product photos keep a white backdrop.
- Prefer shared navigation and reusable class names over page-specific copies.
- Tables must remain usable on narrow screens through responsive overflow or card presentation.
- Use inline status regions for expected validation and network errors; reserve dialogs for destructive confirmation.

## Core Patterns

- Page background: beige (`--systema-bg`)
- Content card: warm off-white (`--systema-surface`), subtle border, rounded corners
- Primary action: coral (`.btn-primary`, remapped by `theme.css`)
- Secondary action: outline or neutral
- Destructive action: explicit danger styling and confirmation

## Page Layout

- Every page extends `base.html`, or `base_with_footer.html` when it shows the footer. Do not write
  `<html>`, `<head>`, `<body>`, the Bootstrap CSS/JS tags, or the viewport meta in a page template.
- Blocks: `title`, `extra_head` (page fonts and styles), `body_attrs`, `content`, `scripts` (page scripts;
  they run after the Bootstrap bundle and `Feedback.js`).
- `header.html` and `footer.html` are markup-only fragments. Their styles are `static/CSS/header.css` and
  `static/CSS/footer.css`, loaded after `extra_head` so page styles keep the cascade order they had when
  the styles were inline. `footer.css` sets `body`/`main` flex rules, so it loads only with the footer.
- Reusable page sections live in `templates/partials/` and are added with `{% include %}`; they are
  markup-only like the header and footer.
- `?embedded=1` pages (market search tabs) render without header and footer; the base handles this.
- `tests/integration/test_page_layout.py` renders every page and fails on a second document, a missing
  shared asset (including `theme.css`), or a page script that uses `alert()` / `document.write()`.

## Feedback Messages

- Use `window.SystemaFeedback` (`static/JS/Feedback.js`): `warning` for input problems, `error` for
  failures (stays until closed), `success`/`info` for completion (closes after a few seconds).
- Messages appear in a fixed region and never shift the layout or replace the page; form input and
  results stay in place. Text is set with `textContent`.
- For fetch calls, check `response.ok` before treating a response as success:
  `if (!response.ok) throw await SystemaFeedback.responseError(response, '更新に失敗しました');`
  and `.catch(error => SystemaFeedback.errorFrom(error, '更新に失敗しました'))` show the server's
  JSON `error` message when there is one.
- `confirm()` remains only for destructive confirmation.

## Guide Screenshots

The guide (`introduction.html`) shows `Main/static/jpg/*_screen.jpg` (2560 x 1230, top-left anchored in
the cards). Regenerate them after a visual change instead of editing images by hand:

```bash
GUIDE_SCREENSHOT_DIR=Main/static/jpg DB_ENGINE=sqlite python -m pytest -m e2e tests/e2e/test_guide_screenshots.py
```

The script is skipped unless `GUIDE_SCREENSHOT_DIR` is set. It serves generated sample listings through
the HTTP fetch boundary (no Yahoo access, generic product names, generated SVG product images) and
captures each page below its hero, with the results visible.

## Related Files

- `Main/templates/base.html`, `Main/static/CSS/theme.css`
- `Main/templates/introduction.html`, `tests/e2e/test_guide_screenshots.py`
- `Main/templates/base_with_footer.html`
- `Main/static/JS/Feedback.js`
- `Main/templates/header.html`
- `Main/templates/footer.html`
- `Main/templates/market_search.html`
- `Main/templates/Deep_Analysis.html`
- `Main/templates/Deep_Analysis_now.html`

Update this document when a reusable visual rule changes. Do not paste full page CSS here.
