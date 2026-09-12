from dataclasses import dataclass

import pytest

from Main.domain.market_listing import MarketListingObservation
from Main.models.searchrun import SearchRun
from Main.services.exceptions import ExternalServiceError
from Main.services.market_search import TargetSearchFailure, execute_target_search
from Main.services.ownership import RequestOwner
from Main.services.search_criteria import SearchCriteria


@dataclass
class Run:
    search_type: str


class Repository:
    def __init__(self):
        self.saved = []
        self.updated = []
        self.snapshot = None

    def save_successful(self, **values):
        run = Run(values["search_type"])
        self.saved.append((run, values))
        return run

    def update_run(self, run, **values):
        self.updated.append((run, values))

    def save_result_snapshot(self, run, snapshot):
        self.snapshot = (run, snapshot)


class Provider:
    marketplace = "test_market"

    def search_closed(self, keyword):
        return [_item("落札カメラ", 20000, "終了")]

    def search_current(self, keyword):
        return [_item("中古カメラ", 10000, "30分")]


def _item(name, price, time):
    return MarketListingObservation(
        marketplace="test_market",
        external_id="item-1",
        name=name,
        price=price,
        start_price=price,
        bidding=2,
        time=time,
        url="https://example.invalid/item-1",
    )


def test_target_search_has_no_http_dependency_and_preserves_result_contract():
    repository = Repository()
    watched = []

    result = execute_target_search(
        criteria=SearchCriteria(keyword="カメラ", search_type=SearchRun.TARGET),
        owner=RequestOwner(user=None, session_key="owner-1"),
        provider=Provider(),
        repository=repository,
        refresh_watch=lambda item, owner: watched.append((item, owner)),
    )

    assert set(result.payload) == {
        "closed_prices",
        "closed_names",
        "medianPrice",
        "marketStatistics",
        "recommend_items",
    }
    assert result.payload["medianPrice"] == 20000
    assert len(result.runs) == 2
    assert [values["search_type"] for _, values in repository.saved] == [
        SearchRun.CLOSED,
        SearchRun.CURRENT,
    ]
    assert repository.saved[0][1]["record_word"] is True
    assert repository.saved[1][1]["record_word"] is False
    assert repository.snapshot[1] == result.payload
    assert len(watched) == 1
    assert watched[0][1].session_key == "owner-1"


def test_target_search_reports_current_failure_after_closed_success():
    class FailingProvider(Provider):
        def search_current(self, keyword):
            raise ExternalServiceError("private")

    repository = Repository()

    with pytest.raises(TargetSearchFailure) as captured:
        execute_target_search(
            criteria=SearchCriteria(keyword="カメラ", search_type=SearchRun.TARGET),
            owner=RequestOwner(user=None, session_key="owner-1"),
            provider=FailingProvider(),
            repository=repository,
            refresh_watch=lambda item, owner: None,
        )

    failure = captured.value
    assert isinstance(failure.cause, ExternalServiceError)
    assert failure.search_type == SearchRun.CURRENT
    assert failure.active_run is None
    assert len(failure.completed_runs) == 1
    assert len(repository.saved) == 1
