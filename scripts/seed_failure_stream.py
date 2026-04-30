from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

API_BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
EVENTS_PATH = Path(__file__).with_name("sample_failure_events.json")


def main() -> None:
    events = json.loads(EVENTS_PATH.read_text(encoding="utf-8"))
    with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
        for event in events:
            payload = {
                "component_id": event["component_id"],
                "component_type": event["component_type"],
                "message": event["message"],
                "source": event.get("source", "sample-stream"),
                "payload": event.get("payload", {}),
            }
            response = client.post("/ingest", json=payload)
            response.raise_for_status()
    print(f"Seeded {len(events)} events into {API_BASE}")


if __name__ == "__main__":
    main()
