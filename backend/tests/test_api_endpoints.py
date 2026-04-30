from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok():
    with TestClient(app) as client:
        response = client.get('/health')

        assert response.status_code == 200
        payload = response.json()
        assert payload['status'] == 'ok'
        assert 'queue_depth' in payload
        assert 'overflow_depth' in payload


def test_incident_detail_exposes_raw_signals_and_timeline_updates():
    with TestClient(app) as client:
        first = client.post(
            '/ingest',
            json={
                'component_id': 'CACHE_CLUSTER_01',
                'component_type': 'CACHE',
                'message': 'cache latency spike',
                'observed_at': datetime.now(timezone.utc).isoformat(),
            },
        )
        assert first.status_code == 200

        second = client.post(
            '/ingest',
            json={
                'component_id': 'CACHE_CLUSTER_01',
                'component_type': 'CACHE',
                'message': 'cache latency spike again',
                'observed_at': datetime.now(timezone.utc).isoformat(),
            },
        )
        assert second.status_code == 200

        incidents = client.get('/incidents')
        assert incidents.status_code == 200
        incidents_payload = incidents.json()
        assert len(incidents_payload) == 1
        incident_id = incidents_payload[0]['id']

        detail = client.get(f'/incidents/{incident_id}')
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload['component_id'] == 'CACHE_CLUSTER_01'
        assert len(detail_payload['signals']) == 2

        timeline = client.get('/timeline')
        assert timeline.status_code == 200
        assert len(timeline.json()) >= 1
