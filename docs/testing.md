# Testing

## Test structure

- `tests/api_test.py`: API contract and validation checks
- `tests/test_yahoo_parser.py`: parser and normalization regression checks
- `tests/fixtures/yahoo/`: representative HTML fixtures for external HTML changes

## Run tests

```bash
pytest -q
```

## Fixture strategy

Fixtures should cover representative HTML states such as:

- valid listing
- missing price
- missing bid count
- unexpected item shape
- page structure drift that can break selectors

## Regression guidance

When Yahoo changes its page structure, the failure should be detectable at the parser layer before it reaches the application API.

This keeps the troubleshooting path short:

- fixture fails
- parser logic is inspected
- targeted fix is applied
- targeted test confirms the fix
