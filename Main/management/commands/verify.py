from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

FEATURE_TESTS = {
    "market-search": (
        "tests/unit/test_search_criteria.py",
        "tests/unit/test_search_observability.py",
        "tests/unit/test_market_statistics.py",
        "tests/integration/test_external_search_api.py",
        "tests/integration/test_market_search.py",
    ),
    "accounts": (
        "tests/integration/test_auth.py",
        "tests/integration/test_saved_searches.py",
    ),
    "prediction": (
        "tests/unit/test_time_series_analysis.py",
        "tests/integration/test_api.py",
    ),
    "target-analysis": (
        "tests/unit/test_buying_opportunity.py",
        "tests/unit/test_market_statistics.py",
        "tests/unit/test_watchlist_analysis.py",
        "tests/integration/test_api.py",
    ),
    "inventory": (
        "tests/unit/test_profitability.py",
        "tests/integration/test_inventory.py",
    ),
    "database": (
        "tests/unit/test_database_config.py",
        "tests/integration/test_database_command.py",
        "tests/integration/test_data_migration.py",
    ),
}

PATH_FEATURES = {
    "Main/services/search_criteria.py": "market-search",
    "Main/services/search_observability.py": "market-search",
    "Main/views/api.py": "market-search",
    "Main/views/utils.py": "market-search",
    "Main/static/JS/MarketSearch.js": "market-search",
    "Main/templates/market_search.html": "market-search",
    "Main/views/accounts.py": "accounts",
    "Main/models/savedsearch.py": "accounts",
    "Main/services/saved_searches.py": "accounts",
    "Main/static/JS/SavedSearches.js": "accounts",
    "Main/templates/accounts/profile.html": "accounts",
    "Main/services/time_series_analysis.py": "prediction",
    "Main/models/watchitem.py": "target-analysis",
    "Main/services/watchlist.py": "target-analysis",
    "Main/services/watchlist_analysis.py": "target-analysis",
    "Main/static/JS/Deep_Analysis_now.js": "target-analysis",
    "Main/templates/Deep_Analysis_now.html": "target-analysis",
    "Main/domain/profitability.py": "inventory",
    "Main/models/inventoryitem.py": "inventory",
    "Main/services/inventory.py": "inventory",
    "Main/static/JS/InventoryManagement.js": "inventory",
    "Main/templates/seller_management.html": "inventory",
}


def select_tests(changed_files: Sequence[str]) -> tuple[str, ...]:
    selected: set[str] = set()
    for raw_path in changed_files:
        path = raw_path.replace("\\", "/")
        if path.startswith("tests/") and path.endswith(".py"):
            selected.add(path)
        feature = PATH_FEATURES.get(path)
        if feature:
            selected.update(FEATURE_TESTS[feature])
        if path.startswith("Main/models/") or path.startswith("Main/migrations/"):
            selected.update(FEATURE_TESTS["database"])
    return tuple(sorted(selected))


class Command(BaseCommand):
    help = "Run concise, scope-aware project verification."

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--feature", choices=sorted(FEATURE_TESTS))
        group.add_argument("--full", action="store_true")

    def handle(self, *args, **options):
        if options["full"]:
            tests = ("tests",)
            include_slow = True
            label = "full"
        elif options["feature"]:
            tests = FEATURE_TESTS[options["feature"]]
            include_slow = False
            label = f"feature:{options['feature']}"
        else:
            tests = select_tests(self._changed_files())
            include_slow = False
            label = "quick"

        python_files = self._changed_python_files()
        commands: list[tuple[str, list[str]]] = []
        if python_files:
            commands.append(("ruff", [sys.executable, "-m", "ruff", "check", *python_files]))
            commands.append(("format", [sys.executable, "-m", "black", "--check", *python_files]))
        if tests:
            pytest_command = [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "--maxfail=1",
                "--disable-warnings",
                "--basetemp=.verify-pytest-tmp",
            ]
            if not include_slow:
                pytest_command.extend(("-m", "not slow"))
            pytest_command.extend(tests)
            commands.append(("pytest", pytest_command))
        commands.append(("django", [sys.executable, "manage.py", "check"]))
        if self._schema_changed():
            commands.append(
                (
                    "migrations",
                    [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
                )
            )

        self.stdout.write(f"verify {label}: {len(commands)} checks")
        for name, command in commands:
            self._run(name, command)
        self.stdout.write(self.style.SUCCESS(f"verify {label}: passed"))

    def _run(self, name: str, command: Sequence[str]) -> None:
        result = subprocess.run(
            command,
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            self.stdout.write(self.style.SUCCESS(f"PASS {name}"))
            return

        details = (result.stdout + result.stderr).strip().splitlines()
        concise_details = "\n".join(details[-40:])
        raise CommandError(f"FAIL {name}\n{concise_details}")

    @staticmethod
    def _git_output(*args: str) -> tuple[str, ...]:
        result = subprocess.run(
            ("git", "-c", f"safe.directory={Path.cwd()}", *args),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise CommandError("Git差分を取得できません。--featureまたは--fullを指定してください。")
        return tuple(line.strip() for line in result.stdout.splitlines() if line.strip())

    def _changed_files(self) -> tuple[str, ...]:
        tracked = self._git_output("diff", "--name-only", "HEAD")
        untracked = self._git_output("ls-files", "--others", "--exclude-standard")
        return tuple(dict.fromkeys((*tracked, *untracked)))

    def _changed_python_files(self) -> tuple[str, ...]:
        source_roots = ("Main/", "System_Config/", "tests/")
        return tuple(
            path
            for path in self._changed_files()
            if path.endswith(".py") and (path.startswith(source_roots) or path == "manage.py")
        )

    def _schema_changed(self) -> bool:
        return any(
            path.startswith("Main/models/") or path.startswith("Main/migrations/")
            for path in self._changed_files()
        )
