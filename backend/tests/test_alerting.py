from __future__ import annotations

from app.models.domain import Severity
from app.services.alerting import AlertingStrategyFactory


def test_alerting_strategy_maps_component_types_to_severity():
    severity, alert = AlertingStrategyFactory.for_component("RDBMS").resolve("RDBMS", "RDBMS_01")
    assert severity == Severity.P0
    assert alert.startswith("P0")

    severity, alert = AlertingStrategyFactory.for_component("CACHE").resolve("CACHE", "CACHE_01")
    assert severity == Severity.P2
    assert alert.startswith("P2")
