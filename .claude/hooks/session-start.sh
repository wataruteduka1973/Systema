#!/bin/bash
# Cloud session setup: install Python dependencies and make bare `pytest`,
# `ruff`, `black`, and `mypy` resolve to the interpreter that has Django.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

python -m pip install -q -r requirements.txt -r requirements-dev.txt

# requirements-dev.txt pins Playwright 1.56.0, which matches the Chromium
# revision (1194) preinstalled under /opt/pw-browsers; do not run `playwright install`.

# The image may ship standalone tool installs (e.g. ~/.local/bin/pytest) that run
# on an isolated interpreter without project dependencies. Prefer the scripts
# directory of the interpreter used above.
scripts_dir="$(python -c 'import sysconfig; print(sysconfig.get_path("scripts"))')"
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$scripts_dir:\$PATH\"" >> "$CLAUDE_ENV_FILE"
  # PostgreSQL is not available in cloud sessions; use the explicit SQLite fallback.
  echo 'export DB_ENGINE="${DB_ENGINE:-sqlite}"' >> "$CLAUDE_ENV_FILE"
fi
