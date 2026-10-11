from Main.management.commands.verify import (
    FEATURE_TESTS,
    check_environment,
    full_quality_commands,
    select_tests,
)


def test_select_tests_maps_market_search_changes_to_feature_suite():
    selected = select_tests(("Main/services/search_observability.py",))
    assert selected == tuple(sorted(FEATURE_TESTS["market-search"]))


def test_select_tests_includes_directly_changed_test():
    selected = select_tests(("tests/unit/test_verify_command.py",))
    assert selected == ("tests/unit/test_verify_command.py",)


def test_select_tests_adds_database_suite_for_schema_changes():
    selected = select_tests(("Main/models/searchrun.py",))
    assert selected == tuple(sorted(FEATURE_TESTS["database"]))


def test_full_quality_commands_match_ci_lint_and_type_check_job():
    commands = dict(full_quality_commands("python"))

    assert commands["ruff"] == ["python", "-m", "ruff", "check", "."]
    assert commands["format"][-3:] == ["Main", "System_Config", "tests"]
    assert commands["mypy"] == ["python", "-m", "mypy"]


def test_check_environment_lets_pytest_use_its_configured_test_settings():
    environ = {"DJANGO_SETTINGS_MODULE": "System_Config.settings", "DB_ENGINE": "sqlite"}

    assert check_environment(environ) == {"DB_ENGINE": "sqlite"}
