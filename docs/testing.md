# Testing

## Test structure

- `tests/unit/`: 外部I/Oを使用しないドメイン・パーサーの単体テスト
- `tests/integration/`: Django、DB、API契約の結合テスト
- `tests/e2e/`: 起動済みアプリケーションを対象にするE2Eテスト
- `tests/fixtures/yahoo/`: representative HTML fixtures for external HTML changes

## Run tests

```bash
pytest -q
```

Coverageを含むCI相当の実行:

```bash
coverage run -m pytest
coverage report
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
