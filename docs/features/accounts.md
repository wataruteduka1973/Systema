# Accounts and Ownership

## Purpose

Provide authentication, profile management, and owner isolation for searches and watchlists.

Saved searches are created and managed on the profile page. Target analysis uses one integrated criteria form, saves it, and executes the saved condition in one action; a same-keyword condition is updated instead of duplicated. The market-search screen keeps its frequent-word input aid and does not expose save/apply controls.

Profile creation uses the keyword as the condition name, immediately runs target analysis, and redirects to the refreshed persisted result.

## Related Files

- `Main/views/accounts.py`
- `Main/templates/accounts/`
- `Main/templates/registration/`
- `Main/services/ownership.py`
- `Main/models/searchrun.py`
- `Main/models/savedsearch.py`
- `Main/services/saved_searches.py`
- `Main/models/watchitem.py`
- `tests/integration/test_auth.py`
- `tests/integration/test_security.py`
- `tests/integration/test_saved_searches.py`

## Rules

- Authenticated data belongs to the user.
- Anonymous data belongs to the session and may be claimed after login.
- Do not expose developer/admin navigation to ordinary users.
- SavedSearch requires login. Every read, update, delete, and run query includes `user=request.user`.
- Running a saved search always uses target analysis through the common `SearchCriteria`, stores `trigger="saved"`, the nullable SavedSearch reference, an immutable criteria snapshot, and the displayed result snapshot.
- Deleting a SavedSearch sets the reference on prior SearchRun rows to null and does not delete their snapshots.
- The profile keeps saved-search latest results separate from manual recent-search history.

## Authentication Security

- Failed login attempts are throttled using hashed IP and IP-plus-username identities. Plain IP addresses and usernames are not stored in throttle records.
- Account-specific failures use progressive temporary blocking; an IP-wide limit remains after a successful login so one valid account cannot reset an attacker's aggregate history.
- Signup and development-only initial-admin setup are rate limited by IP.
- Web initial-admin setup is always disabled in production. Production administrators must be created with Django's `createsuperuser` command.
- Authentication sessions expire when the browser closes and have an eight-hour maximum age by default.
- Django 6.x responses enforce a CSP restricting scripts, styles, forms, frames, objects, and network connections to the application and the explicitly used CDNs.
- Apply `Main.0014_auththrottle` before serving authentication endpoints.
