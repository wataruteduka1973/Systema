"""
E2E test configuration for async/sync context handling with pytest-playwright and pytest-django.
"""

import asyncio

import pytest

# Configure asyncio event loop policy for Windows
# Use ProactorEventLoopPolicy to support subprocess
if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def db_for_e2e(transactional_db):
    """
    Fixture for E2E tests that need transactional database access.

    This ensures that:
    1. Database access is available in E2E tests
    2. Transactions are handled properly
    3. Async/sync context conflicts are avoided
    """
    return transactional_db
