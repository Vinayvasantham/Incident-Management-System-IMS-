from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.models.domain import RCA, Signal
from app.services.incident_service import IncidentService
from app.storage.memory import InMemoryDashboardCache, InMemoryIncidentRepository, InMemorySignalStore


class AppState:
    service: IncidentService | None = None


state = AppState()


class SignalIn(BaseModel):
    component_id: str
    component_type: str
    message: str
    severity_hint: str | None = None
    source: str = "synthetic"
    observed_at: datetime | None = None
    payload: dict = Field(default_factory=dict)


class RCAIn(BaseModel):
    start_time: datetime
    end_time: datetime
    root_cause_category: str
    fix_applied: str
    prevention_steps: str


class TokenBucketLimiter:
    def __init__(self, capacity: int = 120, refill_per_second: float = 20.0) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.tokens = float(capacity)
        self.last_refill = datetime.now(timezone.utc).timestamp()
        self._lock = asyncio.Lock()

    async def allow(self) -> bool:
        async with self._lock:
            now = datetime.now(timezone.utc).timestamp()
            elapsed = now - self.last_refill
            self.last_refill = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_second)
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


limiter = TokenBucketLimiter(
    capacity=int(os.getenv("IMS_RATE_LIMIT_CAPACITY", "50000")),
    refill_per_second=float(os.getenv("IMS_RATE_LIMIT_REFILL_PER_SEC", "20000")),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    repository = InMemoryIncidentRepository()
    signal_store = InMemorySignalStore()
    cache = InMemoryDashboardCache()
    service = IncidentService(repository, signal_store, cache)
    await service.start()
    state.service = service
    try:
        yield
    finally:
        await service.stop()
        state.service = None


app = FastAPI(title="IMS Backend", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_service() -> IncidentService:
    if state.service is None:
        raise RuntimeError("Service is not ready")
    return state.service


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/ingest") and not await limiter.allow():
        return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": "Rate limit exceeded"})
    response = await call_next(request)
    return response


@app.get("/health")
async def health(service: Annotated[IncidentService, Depends(get_service)]):
    return await service.health()


@app.post("/ingest")
async def ingest(payload: SignalIn, service: Annotated[IncidentService, Depends(get_service)]):
    signal = Signal(
        component_id=payload.component_id,
        component_type=payload.component_type,
        message=payload.message,
        severity_hint=payload.severity_hint,
        source=payload.source,
        observed_at=payload.observed_at or datetime.now(timezone.utc),
        payload=payload.payload,
    )
    return await service.ingest(signal)


@app.get("/incidents")
async def list_incidents(service: Annotated[IncidentService, Depends(get_service)]):
    return await service.list_active_incidents()


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, service: Annotated[IncidentService, Depends(get_service)]):
    item = await service.get_incident(incident_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return item


@app.post("/incidents/{incident_id}/rca")
async def close_incident(incident_id: str, payload: RCAIn, service: Annotated[IncidentService, Depends(get_service)]):
    rca = RCA(
        start_time=payload.start_time,
        end_time=payload.end_time,
        root_cause_category=payload.root_cause_category,
        fix_applied=payload.fix_applied,
        prevention_steps=payload.prevention_steps,
    )
    try:
        return await service.submit_rca(incident_id, rca)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError:
        raise HTTPException(status_code=404, detail="Incident not found")


@app.get("/timeline")
async def timeline(service: Annotated[IncidentService, Depends(get_service)]):
    return await service.timeline()
