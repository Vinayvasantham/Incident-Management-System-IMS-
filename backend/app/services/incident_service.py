from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.models.domain import Incident, IncidentStatus, RCA, Signal
from app.core.retry import retry_async
from app.services.alerting import AlertingStrategyFactory
from app.storage.memory import InMemoryDashboardCache, InMemoryIncidentRepository, InMemorySignalStore


class IncidentService:
    def __init__(
        self,
        repository: InMemoryIncidentRepository,
        signal_store: InMemorySignalStore,
        cache: InMemoryDashboardCache,
        debounce_window_seconds: int = 10,
    ) -> None:
        self.repository = repository
        self.signal_store = signal_store
        self.cache = cache
        self.debounce_window = timedelta(seconds=debounce_window_seconds)
        self._queue: asyncio.Queue[Signal] = asyncio.Queue(maxsize=50000)
        self._overflow: deque[Signal] = deque()
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._active_by_component: dict[str, tuple[str, datetime]] = {}
        self._processed_signals = 0
        self._last_reported = 0
        self._workers: list[asyncio.Task[None]] = []
        self._drain_task: asyncio.Task[None] | None = None
        self._metrics_task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self, worker_count: int = 4) -> None:
        if self._running:
            return
        self._running = True
        self._workers = [asyncio.create_task(self._worker_loop()) for _ in range(worker_count)]
        self._drain_task = asyncio.create_task(self._overflow_drain_loop())
        self._metrics_task = asyncio.create_task(self._metrics_loop())

    async def stop(self) -> None:
        self._running = False
        for task in self._workers:
            task.cancel()
        if self._drain_task:
            self._drain_task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        if self._drain_task:
            await asyncio.gather(self._drain_task, return_exceptions=True)
        if self._metrics_task:
            await asyncio.gather(self._metrics_task, return_exceptions=True)

    async def ingest(self, signal: Signal) -> dict[str, Any]:
        try:
            self._queue.put_nowait(signal)
        except asyncio.QueueFull:
            self._overflow.append(signal)
        return {"accepted": True, "signal_id": signal.signal_id}

    async def list_active_incidents(self) -> list[dict[str, Any]]:
        incidents = await self.repository.list_active()
        severity_rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        ordered = sorted(
            incidents,
            key=lambda incident: (severity_rank[incident.severity.value], -incident.last_signal_at.timestamp()),
        )
        return [self._serialize_incident(incident) for incident in ordered]

    async def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        incident = await self.repository.get(incident_id)
        if incident is None:
            return None
        signals = await self.signal_store.list_by_incident(incident_id)
        payload = self._serialize_incident(incident)
        payload["signals"] = signals
        return payload

    async def submit_rca(self, incident_id: str, rca: RCA) -> dict[str, Any]:
        incident = await self.repository.get(incident_id)
        if incident is None:
            raise KeyError(incident_id)

        # Prevent partial state mutation on invalid closure requests.
        if not rca.is_complete():
            raise ValueError("RCA is required and must be complete before closing an incident")

        if incident.status == IncidentStatus.CLOSED:
            raise ValueError("Incident is already closed")
        if incident.status in {IncidentStatus.OPEN, IncidentStatus.INVESTIGATING}:
            incident.transition(IncidentStatus.RESOLVED)
        incident.transition(IncidentStatus.CLOSED, rca)
        await retry_async(lambda: self.repository.create(incident))
        await retry_async(lambda: self.cache.upsert_incident(incident))
        return self._serialize_incident(incident)

    async def timeline(self) -> list[dict[str, Any]]:
        return await self.repository.aggregates()

    async def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "queue_depth": self._queue.qsize(),
            "overflow_depth": len(self._overflow),
            "processed_signals": self._processed_signals,
        }

    async def _worker_loop(self) -> None:
        while self._running:
            signal = await self._queue.get()
            try:
                await self._process_signal(signal)
                self._processed_signals += 1
            finally:
                self._queue.task_done()

    async def _overflow_drain_loop(self) -> None:
        while self._running:
            while self._overflow and not self._queue.full():
                await self._queue.put(self._overflow.popleft())
            await asyncio.sleep(0.05)

    async def _metrics_loop(self) -> None:
        while self._running:
            await asyncio.sleep(5)
            delta = self._processed_signals - self._last_reported
            self._last_reported = self._processed_signals
            print(f"[IMS] throughput={delta / 5:.2f} signals/sec queue={self._queue.qsize()} overflow={len(self._overflow)}")

    async def _process_signal(self, signal: Signal) -> None:
        lock = self._locks[signal.component_id]
        async with lock:
            now = signal.observed_at
            incident_id, created_at = self._active_by_component.get(signal.component_id, (None, None))
            active_incident = await self.repository.get(incident_id) if incident_id else None
            if active_incident is None or created_at is None or now - created_at > self.debounce_window or active_incident.status == IncidentStatus.CLOSED:
                strategy = AlertingStrategyFactory.for_component(signal.component_type)
                severity, alert_type = strategy.resolve(signal.component_type, signal.component_id)
                incident = Incident(
                    id=str(uuid4()),
                    component_id=signal.component_id,
                    component_type=signal.component_type,
                    severity=severity,
                    alert_type=alert_type,
                    status=IncidentStatus.OPEN,
                    first_signal_at=now,
                    last_signal_at=now,
                    signal_count=0,
                )
                await retry_async(lambda: self.repository.create(incident))
                self._active_by_component[signal.component_id] = (incident.id, now)
                active_incident = incident
            await retry_async(lambda: self.signal_store.append(active_incident.id, signal))
            await retry_async(lambda: self.repository.append_signal(active_incident.id, signal))
            await retry_async(lambda: self.repository.create(active_incident))
            await retry_async(lambda: self.cache.upsert_incident(active_incident))

    def _serialize_incident(self, incident: Incident) -> dict[str, Any]:
        return {
            "id": incident.id,
            "component_id": incident.component_id,
            "component_type": incident.component_type,
            "severity": incident.severity.value,
            "alert_type": incident.alert_type,
            "status": incident.status.value,
            "first_signal_at": incident.first_signal_at.isoformat(),
            "last_signal_at": incident.last_signal_at.isoformat(),
            "signal_count": incident.signal_count,
            "mttr_minutes": incident.mttr_minutes,
            "rca": asdict(incident.rca) if incident.rca else None,
        }
