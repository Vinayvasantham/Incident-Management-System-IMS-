from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class RootCauseCategory(str, Enum):
    CONFIGURATION = "Configuration Drift"
    DEPENDENCY = "Upstream Dependency"
    CACHE = "Cache Invalidation"
    CAPACITY = "Capacity Exhaustion"
    NETWORK = "Network Partition"
    CODE = "Code Regression"
    HUMAN = "Human Error"


@dataclass(slots=True)
class RCA:
    start_time: datetime
    end_time: datetime
    root_cause_category: str
    fix_applied: str
    prevention_steps: str

    def is_complete(self) -> bool:
        return all(
            [
                self.start_time.tzinfo is not None,
                self.end_time.tzinfo is not None,
                bool(self.root_cause_category.strip()),
                bool(self.fix_applied.strip()),
                bool(self.prevention_steps.strip()),
                self.end_time >= self.start_time,
            ]
        )

    def mttr_minutes(self) -> float:
        return round((self.end_time - self.start_time).total_seconds() / 60.0, 2)


@dataclass(slots=True)
class Signal:
    component_id: str
    component_type: str
    message: str
    severity_hint: str | None = None
    source: str = "synthetic"
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)
    signal_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(slots=True)
class Incident:
    id: str
    component_id: str
    component_type: str
    severity: Severity
    alert_type: str
    status: IncidentStatus
    first_signal_at: datetime
    last_signal_at: datetime
    signal_count: int = 0
    rca: RCA | None = None
    mttr_minutes: float | None = None

    def can_transition_to(self, next_status: IncidentStatus) -> bool:
        allowed = {
            IncidentStatus.OPEN: {IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED},
            IncidentStatus.INVESTIGATING: {IncidentStatus.RESOLVED, IncidentStatus.CLOSED},
            IncidentStatus.RESOLVED: {IncidentStatus.CLOSED},
            IncidentStatus.CLOSED: set(),
        }
        return next_status in allowed[self.status]

    def transition(self, next_status: IncidentStatus, rca: RCA | None = None) -> None:
        if not self.can_transition_to(next_status):
            raise ValueError(f"Invalid transition from {self.status} to {next_status}")
        if next_status == IncidentStatus.CLOSED:
            if rca is None or not rca.is_complete():
                raise ValueError("RCA is required and must be complete before closing an incident")
            self.rca = rca
            self.mttr_minutes = rca.mttr_minutes()
            self.last_signal_at = rca.end_time
        else:
            self.last_signal_at = datetime.now(timezone.utc)
        self.status = next_status
