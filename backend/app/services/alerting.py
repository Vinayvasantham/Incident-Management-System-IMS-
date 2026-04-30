from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.domain import Severity


class AlertingStrategy(ABC):
    @abstractmethod
    def resolve(self, component_type: str, component_id: str) -> tuple[Severity, str]:
        raise NotImplementedError


class RdbmsAlertingStrategy(AlertingStrategy):
    def resolve(self, component_type: str, component_id: str) -> tuple[Severity, str]:
        return Severity.P0, f"P0: RDBMS incident on {component_id}"


class CacheAlertingStrategy(AlertingStrategy):
    def resolve(self, component_type: str, component_id: str) -> tuple[Severity, str]:
        return Severity.P2, f"P2: Cache degradation on {component_id}"


class QueueAlertingStrategy(AlertingStrategy):
    def resolve(self, component_type: str, component_id: str) -> tuple[Severity, str]:
        return Severity.P1, f"P1: Queue instability on {component_id}"


class MCPAlertingStrategy(AlertingStrategy):
    def resolve(self, component_type: str, component_id: str) -> tuple[Severity, str]:
        return Severity.P1, f"P1: MCP host failure on {component_id}"


class DefaultAlertingStrategy(AlertingStrategy):
    def resolve(self, component_type: str, component_id: str) -> tuple[Severity, str]:
        return Severity.P3, f"P3: Component issue on {component_id}"


class AlertingStrategyFactory:
    @staticmethod
    def for_component(component_type: str) -> AlertingStrategy:
        normalized = component_type.upper()
        if normalized == "RDBMS":
            return RdbmsAlertingStrategy()
        if normalized == "CACHE":
            return CacheAlertingStrategy()
        if normalized == "QUEUE":
            return QueueAlertingStrategy()
        if normalized in {"MCP", "MCP_HOST"}:
            return MCPAlertingStrategy()
        return DefaultAlertingStrategy()
