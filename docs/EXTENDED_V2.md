# Extended V2 Validation

Extended V2 is an isolated experimental track. It must not overwrite or be
presented as a replacement for the verified Baseline V1 evidence until its
acceptance gate passes.

## Added evidence

- Five benign traffic profiles with six sessions per profile: 30 independent
  sessions per detector mode. Five sessions contain 500 queries specifically to
  exercise long-horizon detection rules.
- Rate-only, model-aware-only, baseline-full, and enhanced detector modes on
  identical attacks.
- Four extraction scenarios: fast adaptive, slow adaptive, limited-pool replay,
  and a distributed attack rotating across five client identities.
- Surrogate fidelity fitted at the exact first throttle or block action.
- Serial service and in-process FastAPI p50/p95 latency, including SQLite logs.

Fast adaptive extraction uses the configured maximum query budget. Slow, replay,
and distributed scenarios are capped at 2,000 queries to keep the expanded
four-mode protocol tractable. Quick mode naturally remains capped at 1,000.

Enhanced v2.4 keeps short-window model-aware decisions as telemetry and enforces
only after orthogonal confirmation: twice the calibrated maximum rate, exact
request repetition, three linked accounts, persistent multi-signal evidence, or
a boundary-heavy campaign of at least 400 queries.

Run a local smoke validation with:

```powershell
python run_validation_v2.py --quick --seeds 42 --epochs 1 --max-queries 500
```

The smoke-only cap shortens local verification. Omit `--max-queries` from the
submission-quality protocol.

For a focused baseline-versus-enhanced development run:

```powershell
python run_validation_v2.py --quick --seeds 42 --epochs 1 `
  --max-queries 500 --modes full enhanced
```

Resume completed seeds only when every effective protocol setting matches:

```powershell
python run_validation_v2.py --quick --seeds 42 7 123 --epochs 1 --resume
```

Reuse externally trained checkpoints with:

```powershell
python run_validation_v2.py --seeds 314 2718 1618 --epochs 8 `
  --checkpoint-source artifacts/checkpoints_full
```

The default output is `artifacts/validation_extended_v2`. The runner refuses
`artifacts/validation_corrected` and every descendant.

## Acceptance gate

V2 may replace Baseline V1 only when all of the following hold across at least
three independent seeds:

- Enhanced-detector required-attack detection is 12/12 across four scenarios and
  three untouched holdout seeds.
- No tested benign session is throttled or blocked across at least 30 sessions
  per detector mode.
- Mean defended final fidelity is no higher than Baseline V1.
- Results reproduce from a clean run and the output manifest matches.
- Latency and residual low-rate/distributed risks are stated explicitly.
