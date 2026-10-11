# UI Design Context

## Direction

- Use a consistent red-gradient hero, white content cards, restrained shadows, and Bootstrap controls.
- The top page (`StartMenu.html`, `static/CSS/start-menu.css`) uses a warm palette instead: beige background
  `#f7f2ea`, Shippori Mincho headings and prices, Zen Kaku Gothic New body text, coral/teal/gold accents.
  Other pages keep the red-gradient hero until they are redesigned.
- Prefer shared navigation and reusable class names over page-specific copies.
- Tables must remain usable on narrow screens through responsive overflow or card presentation.
- Use inline status regions for expected validation and network errors; reserve dialogs for destructive confirmation.

## Core Patterns

- Page background: light neutral gray
- Content card: white, subtle border, rounded corners
- Primary action: red
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
  shared asset, or a page script that uses `alert()` / `document.write()`.

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

## Related Files

- `Main/templates/base.html`
- `Main/templates/base_with_footer.html`
- `Main/static/JS/Feedback.js`
- `Main/templates/header.html`
- `Main/templates/footer.html`
- `Main/templates/market_search.html`
- `Main/templates/Deep_Analysis.html`
- `Main/templates/Deep_Analysis_now.html`

Update this document when a reusable visual rule changes. Do not paste full page CSS here.
