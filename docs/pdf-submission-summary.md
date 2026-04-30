# Submission Summary

**Candidate Name:** Nagavinay  
**Assignment:** Infrastructure / SRE Intern Intern Assignment  
**Project:** Mission-Critical Incident Management System (IMS)

## 1. Objective

Implemented a resilient Incident Management System to ingest high-volume failure signals, mediate incident workflows, enforce mandatory RCA before closure, and provide a responsive dashboard for live operations.

## 2. Delivered Architecture

- Async ingestion pipeline with bounded queue and overflow buffer.
- Debounce policy by `component_id` within a 10-second window.
- Strategy-based alert severity resolution (RDBMS, Cache, Queue, MCP host, default).
- State-driven incident lifecycle transitions: `OPEN -> INVESTIGATING -> RESOLVED -> CLOSED`.
- RCA validation gate before closure and automatic MTTR calculation.
- Separate data concerns for raw signal payloads, structured incident records, dashboard hot-path state, and timeline aggregation.

## 3. Core Functional Coverage

- Live incident feed sorted by severity.
- Incident detail view with linked raw signals.
- RCA form with start/end time, root cause category, fix applied, and prevention steps.
- Health endpoint (`/health`) and runtime throughput logs every 5 seconds.
- Ingestion rate limiting to protect system under load.

Detailed traceability: `docs/requirements-traceability.md`.

## 4. Testing and Validation

Automated test execution:

- Backend: `8 passed` (`pytest`)
- Frontend: `1 passed` (`vitest`)

Runtime container validation:

- Docker Compose build/start successful.
- Backend and frontend reachable on expected ports.
- End-to-end checks verified:
  - Debounce behavior for burst signals.
  - Mandatory RCA rejection on incomplete input.
  - Successful closure with MTTR computation.
  - Timeline aggregation output.
  - Rate limit behavior under stress.
  - Throughput log emission (`[IMS] throughput=...`).

## 5. Performance Evidence

Load-test script: `scripts/load_test.py`

Sample benchmark result on local machine:

```json
{
  "total_requests": 10000,
  "concurrency": 200,
  "duration_seconds": 44.062,
  "request_throughput_per_sec": 226.95,
  "accepted": 10000,
  "rate_limited": 0,
  "failed": 0
}
```

Note: The `10,000 signals/sec` target is architecture-oriented and environment dependent. Local laptop execution demonstrates behavior and resilience, not production cluster ceiling.

## 6. Bonus Features Implemented

- Ingestion API rate limiting.
- Retry wrapper for persistence/cache writes.
- Explicit backpressure handling with bounded queue + overflow drain loop.
- Periodic throughput observability logs.
- Load-testing harness and benchmark documentation.

## 7. Repository Artifacts

- Backend service: `backend/`
- Frontend dashboard: `frontend/`
- Compose setup: `docker-compose.yml`
- Failure simulation data/scripts: `scripts/`
- Architecture/testing/backpressure docs: `docs/`
- Prompt/spec notes: `prompts/`

## 8. Mandatory Submission Fields

- **GitHub Repository Link:** `<PASTE_GITHUB_LINK_HERE>`
- **PDF Filename:** `Full Name - Infrastructure / SRE Intern Intern Assignment.pdf`
- **Submission Email:** `karan.sinha@zeotap.com`
- **Deadline Noted:** `5th May 2026`

## 9. Honest Constraint Disclosure

This submission uses in-memory storage abstractions for the data sinks in order to keep the assignment runnable, testable, and self-contained. The architecture and workflow are designed to map directly to production backing services (NoSQL, RDBMS, cache, timeseries store) when external infra is provisioned.
