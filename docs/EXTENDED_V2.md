# Extended V2 Validation

Extended V2 is an isolated experimental track. It must not overwrite or be
presented as a replacement for the verified Baseline V1 evidence until its
acceptance gate passes.

## Added evidence

- Five benign traffic profiles with two independent sessions per profile.
- Rate-only, model-aware-only, and full detector modes on identical attacks.
- Surrogate fidelity fitted at the exact first throttle or block action.
- Serial service and in-process FastAPI p50/p95 latency, including SQLite logs.

Run a local smoke validation with:

```powershell
python run_validation_v2.py --quick --seeds 42 --epochs 1
```

The default output is `artifacts/validation_extended_v2`. The runner refuses
`artifacts/validation_corrected` and every descendant.

## Acceptance gate

V2 may replace Baseline V1 only when all of the following hold across at least
three independent seeds:

- Full-detector required-attack detection is at least 3/3.
- No tested benign session is throttled or blocked.
- Mean defended final fidelity is no higher than Baseline V1.
- Results reproduce from a clean run and the output manifest matches.
- Latency and residual low-rate/distributed risks are stated explicitly.
