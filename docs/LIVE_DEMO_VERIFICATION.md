# Live HTTP Demo Verification

The competition demo path uses the Enhanced V2.4 monitor behind the real
FastAPI endpoint. Client timestamps are never accepted; alert time is measured
with the server clock and the traffic command's monotonic wall clock.

## Verified sequence

The following sequence was run twice against a fresh local API process:

```powershell
python serve_api.py --reset-db --require-checkpoint --demo-reset-token modelsentry-demo
python run_live_traffic.py all
python run_live_traffic.py all
```

| Check | First run | Second run |
|---|---:|---:|
| Unique normal HTTP requests | 75 | 75 |
| Normal throttle/block actions | 0 | 0 |
| Extraction alert query | 102 | 102 |
| Wall-clock time to alert | 0.99 seconds | 1.12 seconds |
| Trigger | Repeated-query ratio above 20% | Repeated-query ratio above 20% |
| Malformed request | HTTP 422; API healthy | HTTP 422; API healthy |

Wall-clock time varies by machine. The deterministic correctness target is the
query-102 alert: a diverse 50-image pool begins repeating, crosses the long-term
20% replay threshold, and satisfies three confirmation windows. The dashboard
refreshes every 0.5 seconds and reads the same WAL-enabled SQLite event stream.

This live smoke check demonstrates the required user-visible flow. It is not a
replacement for the frozen three-seed holdout evidence in
`docs/V2_HOLDOUT_RESULTS.md`.
