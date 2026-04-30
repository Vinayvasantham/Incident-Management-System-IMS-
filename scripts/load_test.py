from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import suppress

import httpx


@dataclass
class Stats:
    sent: int = 0
    accepted: int = 0
    rate_limited: int = 0
    failed: int = 0


async def post_signal(client: httpx.AsyncClient, api_base: str, idx: int, component_id: str) -> int:
    payload = {
        "component_id": component_id,
        "component_type": "CACHE",
        "message": f"load signal {idx}",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "source": "load-test",
    }
    response = await client.post(f"{api_base}/ingest", json=payload)
    return response.status_code


async def run_load(api_base: str, total: int, concurrency: int, component_id: str) -> dict:
    stats = Stats()
    queue: asyncio.Queue[int] = asyncio.Queue()
    for i in range(total):
        queue.put_nowait(i)

    async with httpx.AsyncClient(timeout=15.0) as client:
        lock = asyncio.Lock()

        async def worker() -> None:
            nonlocal stats
            while True:
                with suppress(asyncio.QueueEmpty):
                    idx = queue.get_nowait()
                    try:
                        status = await post_signal(client, api_base, idx, component_id)
                    except Exception:  # noqa: BLE001
                        status = -1
                    async with lock:
                        stats.sent += 1
                        if status == 200:
                            stats.accepted += 1
                        elif status == 429:
                            stats.rate_limited += 1
                        else:
                            stats.failed += 1
                    queue.task_done()
                    continue
                return

        started = time.perf_counter()
        workers = [asyncio.create_task(worker()) for _ in range(max(1, concurrency))]
        await queue.join()
        await asyncio.gather(*workers)
        duration = time.perf_counter() - started

        incidents = await client.get(f"{api_base}/incidents")
        linked_signals = None
        incident_count = 0
        if incidents.status_code == 200:
            matches = [item for item in incidents.json() if item.get("component_id") == component_id]
            incident_count = len(matches)
            if matches:
                linked_signals = matches[0].get("signal_count")

    return {
        "total_requests": total,
        "concurrency": concurrency,
        "duration_seconds": round(duration, 3),
        "request_throughput_per_sec": round(total / duration, 2) if duration > 0 else None,
        "accepted": stats.accepted,
        "rate_limited": stats.rate_limited,
        "failed": stats.failed,
        "incident_count_for_component": incident_count,
        "linked_signal_count": linked_signals,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="IMS burst load test")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--total", type=int, default=10000)
    parser.add_argument("--concurrency", type=int, default=300)
    parser.add_argument("--component-id", default="CACHE_BURST_LOAD_01")
    args = parser.parse_args()

    result = asyncio.run(run_load(args.api_base, args.total, args.concurrency, args.component_id))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
