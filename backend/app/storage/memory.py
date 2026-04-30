from __future__ import annotations

import asyncio
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from typing import Any

from app.models.domain import Incident, RCA, Severity, Signal


class InMemorySignalStore:
    def __init__(self) -> None:
        self._signals: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def append(self, incident_id: str, signal: Signal) -> None:
        async with self._lock:
            document = asdict(signal)
            document["incident_id"] = incident_id
            document["observed_at"] = signal.observed_at.isoformat()
            self._signals.append(document)

    async def list_by_incident(self, incident_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            return [deepcopy(item) for item in self._signals if item["incident_id"] == incident_id]


class InMemoryDashboardCache:
    def __init__(self) -> None:
        self._incidents: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def upsert_incident(self, incident: Incident) -> None:
        async with self._lock:
            self._incidents[incident.id] = self._serialize(incident)

    async def delete_incident(self, incident_id: str) -> None:
        async with self._lock:
            self._incidents.pop(incident_id, None)

    async def list_active_incidents(self) -> list[dict[str, Any]]:
        async with self._lock:
            active = [item for item in self._incidents.values() if item["status"] != "CLOSED"]
            return sorted(
                active,
                key=lambda item: (
                    item["severity_rank"],
                    -datetime.fromisoformat(item["last_signal_at"]).timestamp(),
                ),
            )

    async def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        async with self._lock:
            item = self._incidents.get(incident_id)
            return deepcopy(item) if item else None

    def _serialize(self, incident: Incident) -> dict[str, Any]:
        severity_rank = {Severity.P0.value: 0, Severity.P1.value: 1, Severity.P2.value: 2, Severity.P3.value: 3}[incident.severity.value]
        return {
            "id": incident.id,
            "component_id": incident.component_id,
            "component_type": incident.component_type,
            "severity": incident.severity.value,
            "severity_rank": severity_rank,
            "alert_type": incident.alert_type,
            "status": incident.status.value,
            "first_signal_at": incident.first_signal_at.isoformat(),
            "last_signal_at": incident.last_signal_at.isoformat(),
            "signal_count": incident.signal_count,
            "mttr_minutes": incident.mttr_minutes,
            "rca": asdict(incident.rca) if incident.rca else None,
        }


class InMemoryIncidentRepository:
    def __init__(self) -> None:
        self._incidents: dict[str, Incident] = {}
        self._lock = asyncio.Lock()
        self._aggregates: dict[tuple[str, str], int] = defaultdict(int)

    async def create(self, incident: Incident) -> Incident:
        async with self._lock:
            self._incidents[incident.id] = incident
            return incident

    async def get(self, incident_id: str) -> Incident | None:
        async with self._lock:
            return self._incidents.get(incident_id)

    async def list_active(self) -> list[Incident]:
        async with self._lock:
            return [incident for incident in self._incidents.values() if incident.status.value != "CLOSED"]

    async def append_signal(self, incident_id: str, signal: Signal) -> None:
        async with self._lock:
            incident = self._incidents[incident_id]
            incident.signal_count += 1
            incident.last_signal_at = signal.observed_at
            bucket = signal.observed_at.replace(second=(signal.observed_at.second // 60) * 60, microsecond=0)
            self._aggregates[(incident.component_id, bucket.isoformat())] += 1

    async def transition(self, incident_id: str, next_status: str, rca: RCA | None = None) -> Incident:
        async with self._lock:
            incident = self._incidents[incident_id]
            incident.transition(type(incident.status)(next_status), rca)
            return incident

    async def aggregates(self) -> list[dict[str, Any]]:
        async with self._lock:
            return [
                {"component_id": component_id, "bucket_start": bucket, "signal_count": count}
                for (component_id, bucket), count in sorted(self._aggregates.items())
            ]
