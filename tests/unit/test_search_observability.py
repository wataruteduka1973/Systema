from Main.services import search_observability


def test_search_timer_returns_elapsed_whole_milliseconds(monkeypatch):
    readings = iter((1_000_000_000, 1_012_999_999))
    monkeypatch.setattr(search_observability, "perf_counter_ns", lambda: next(readings))

    timer = search_observability.SearchTimer.start()

    assert timer.elapsed_ms() == 12
