# Accounts and Ownership

## Purpose

Provide authentication, profile management, and owner isolation for searches and watchlists.

## Related Files

- `Main/views/accounts.py`
- `Main/templates/accounts/`
- `Main/templates/registration/`
- `Main/services/ownership.py`
- `Main/models/searchrun.py`
- `Main/models/watchitem.py`
- `tests/integration/test_auth.py`
- `tests/integration/test_security.py`

## Rules

- Authenticated data belongs to the user.
- Anonymous data belongs to the session and may be claimed after login.
- Do not expose developer/admin navigation to ordinary users.
