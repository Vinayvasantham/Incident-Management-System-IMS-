# Backpressure Handling

Backpressure is handled in three layers:

1. The ingestion API uses a token-bucket limiter to reject bursts before they overwhelm the worker queue.
2. The backend queue is bounded, and overflowed signals are temporarily parked in an in-memory deque instead of crashing the request path.
3. Worker tasks drain the overflow buffer back into the queue as capacity returns.

This keeps the public API responsive while preserving burst traffic for later processing. The console throughput logger prints processed signals per second every 5 seconds so you can observe the queue draining in real time.
