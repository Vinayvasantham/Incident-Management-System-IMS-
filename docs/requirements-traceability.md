# Requirements Traceability Matrix

This matrix maps each assignment requirement to implementation, automated tests, and runtime validation evidence.

## Functional and Technical Requirements

| Requirement | Implemented | Automated Test Coverage | Runtime Validation | Evidence |
|---|---|---|---|---|
| Async processing in backend | Yes | Yes | Yes | backend/app/services/incident_service.py, backend/tests/test_incident_service.py |
| High-throughput signal ingestion endpoint | Yes | Partial (API flow) | Yes | backend/app/main.py, scripts/load_test.py |
| Debounce logic for same component in 10s window | Yes | Yes | Yes | backend/app/services/incident_service.py, backend/tests/test_incident_service.py |
| Link all raw signals to work item | Yes | Yes | Yes | backend/app/storage/memory.py, backend/tests/test_api_endpoints.py |
| Source of truth with transactional transitions | Yes (in-memory transactional flow) | Yes | Yes | backend/app/services/incident_service.py, backend/tests/test_incident_service.py |
| Hot-path dashboard cache | Yes | Indirect | Yes | backend/app/storage/memory.py, frontend/src/App.tsx |
| Timeseries aggregations | Yes | Yes | Yes | backend/app/storage/memory.py, backend/tests/test_api_endpoints.py |
| Alerting strategy pattern by component type | Yes | Yes | Yes | backend/app/services/alerting.py, backend/tests/test_alerting.py |
| Work item state pattern (OPEN->INVESTIGATING->RESOLVED->CLOSED) | Yes | Yes | Yes | backend/app/models/domain.py, backend/tests/test_incident_service.py |
| Mandatory RCA before CLOSED | Yes | Yes | Yes | backend/app/models/domain.py, backend/tests/test_incident_service.py |
| MTTR calculation | Yes | Yes | Yes | backend/app/models/domain.py, backend/tests/test_incident_service.py |
| Ingestion API rate limiting | Yes | Yes | Yes | backend/app/main.py, backend/tests/test_rate_limit.py |
| Observability /health endpoint | Yes | Yes | Yes | backend/app/main.py, backend/tests/test_api_endpoints.py |
| Throughput metric logging every 5 seconds | Yes | Yes | Yes | backend/app/services/incident_service.py, backend/tests/test_incident_service.py |
| Responsive frontend dashboard | Yes | Yes (UI smoke) | Yes | frontend/src/App.tsx, frontend/src/App.test.tsx |
| Live feed sorted by severity | Yes | Indirect | Yes | frontend/src/App.tsx, backend/app/services/incident_service.py |
| Incident detail with raw signals | Yes | Yes | Yes | frontend/src/App.tsx, backend/tests/test_api_endpoints.py |
| RCA form with date-time/category/fix/prevention fields | Yes | Yes (render) | Yes | frontend/src/App.tsx, frontend/src/App.test.tsx |
| Docker Compose setup | Yes | N/A | Yes | docker-compose.yml |
| Sample failure data/script | Yes | N/A | Yes | scripts/sample_failure_events.json, scripts/seed_failure_stream.py |
| Prompts/spec/plans checked in | Yes | N/A | Yes | prompts/creation-notes.md |

## Bonus Features

| Bonus Item | Status | Evidence |
|---|---|---|
| Security layer (rate limiting) | Implemented | backend/app/main.py |
| Resilience retry layer for writes | Implemented | backend/app/core/retry.py |
| Backpressure handling (bounded queue + overflow) | Implemented | backend/app/services/incident_service.py, docs/backpressure.md |
| Runtime throughput observability | Implemented | backend/app/services/incident_service.py |
| Load testing script and benchmark evidence | Implemented | scripts/load_test.py, README.md |

## Validation Commands Executed

Backend tests:

```bash
cd backend
python -m pytest -q
```

Frontend tests:

```bash
cd frontend
npm test
```

Container runtime:

```bash
docker compose up --build -d
docker compose ps
```

Runtime log evidence:

```bash
docker compose logs backend --tail=120 | grep "[IMS]"
```

## Known Constraint (Honest Disclosure)

The current implementation uses in-memory stores for raw signals, source-of-truth records, cache, and aggregations. This satisfies workflow behavior and testability for the assignment submission, but is not a production deployment of dedicated NoSQL, RDBMS, Redis, and timeseries engines.
