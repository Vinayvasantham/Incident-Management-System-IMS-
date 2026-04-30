from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.domain import IncidentStatus, RCA, Signal
from app.services.incident_service import IncidentService
from app.storage.memory import InMemoryDashboardCache, InMemoryIncidentRepository, InMemorySignalStore


@pytest.mark.asyncio
async def test_debouncing_links_signals_to_single_incident():
    repository = InMemoryIncidentRepository()
    signal_store = InMemorySignalStore()
    cache = InMemoryDashboardCache()
    service = IncidentService(repository, signal_store, cache, debounce_window_seconds=10)

    signal_one = Signal(component_id="CACHE_CLUSTER_01", component_type="CACHE", message="latency spike", observed_at=datetime.now(timezone.utc))
    signal_two = Signal(
        component_id="CACHE_CLUSTER_01",
        component_type="CACHE",
        message="latency spike again",
        observed_at=signal_one.observed_at + timedelta(seconds=3),
    )

    await service.ingest(signal_one)
    await service.ingest(signal_two)
    await service.start(worker_count=1)
    await service._queue.join()
    await service.stop()

    incidents = await service.list_active_incidents()
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["signal_count"] == 2

    detailed = await service.get_incident(incident["id"])
    assert detailed is not None
    assert len(detailed["signals"]) == 2


@pytest.mark.asyncio
async def test_rca_required_before_closing():
    repository = InMemoryIncidentRepository()
    signal_store = InMemorySignalStore()
    cache = InMemoryDashboardCache()
    service = IncidentService(repository, signal_store, cache)

    signal = Signal(component_id="RDBMS_PRIMARY", component_type="RDBMS", message="database offline")
    await service.ingest(signal)
    await service.start(worker_count=1)
    await service._queue.join()
    await service.stop()

    incident = (await service.list_active_incidents())[0]
    with pytest.raises(ValueError, match="RCA is required"):
        await service.submit_rca(
            incident["id"],
            RCA(
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
                root_cause_category="",
                fix_applied="",
                prevention_steps="",
            ),
        )

    still_open = await service.get_incident(incident["id"])
    assert still_open is not None
    assert still_open["status"] == IncidentStatus.OPEN.value


@pytest.mark.asyncio
async def test_close_with_complete_rca_sets_mttr_and_status():
    repository = InMemoryIncidentRepository()
    signal_store = InMemorySignalStore()
    cache = InMemoryDashboardCache()
    service = IncidentService(repository, signal_store, cache)

    signal = Signal(component_id="MCP_HOST_02", component_type="MCP_HOST", message="host unavailable")
    await service.ingest(signal)
    await service.start(worker_count=1)
    await service._queue.join()
    await service.stop()

    incident = (await service.list_active_incidents())[0]
    start = signal.observed_at
    end = start + timedelta(minutes=14)
    closed = await service.submit_rca(
        incident["id"],
        RCA(
            start_time=start,
            end_time=end,
            root_cause_category="Upstream Dependency",
            fix_applied="Restarted host",
            prevention_steps="Add alerting automation",
        ),
    )

    assert closed["status"] == IncidentStatus.CLOSED.value
    assert closed["mttr_minutes"] == 14.0


@pytest.mark.asyncio
async def test_throughput_metrics_loop_prints_progress(monkeypatch, capsys):
    repository = InMemoryIncidentRepository()
    signal_store = InMemorySignalStore()
    cache = InMemoryDashboardCache()
    service = IncidentService(repository, signal_store, cache)

    service._running = True
    service._processed_signals = 25
    service._last_reported = 5

    async def stop_after_first_sleep(delay: float) -> None:
        service._running = False

    monkeypatch.setattr("app.services.incident_service.asyncio.sleep", stop_after_first_sleep)

    await service._metrics_loop()

    output = capsys.readouterr().out
    assert "throughput=4.00 signals/sec" in output
