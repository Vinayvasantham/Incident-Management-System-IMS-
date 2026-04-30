# Testing

Backend tests cover:

- Debouncing of multiple signals for the same component.
- Mandatory RCA validation before closing an incident.
- MTTR calculation from RCA start and end times.
- Rate limit response behavior.
- Alerting strategy mapping for component types.

Frontend tests cover the dashboard shell and verify the main sections render correctly.

Run tests from the repository root:

```bash
cd backend && pytest
cd ../frontend && npm test
```
