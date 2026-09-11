# ModelSentry V2.4

V2.4 expands ModelSentry from a short-window prototype into a multi-timescale
evaluation policy. It adds exact replay fingerprints, persistent campaign
tracking, linked-account correlation, expanded benign traffic, four detector
modes, four attack scenarios, latency measurements, and a frozen holdout.

## Accepted holdout result

| Metric | Enhanced V2.4 result |
|---|---:|
| Attack runs detected | 11/12 (91.67%) |
| Benign sessions mitigated | 0/90 |
| Mean final surrogate fidelity | 71.78% +/- 7.94 pp |
| In-process API latency p50 / p95 | 12.93 / 14.84 ms |

V2.4 detected all tested fast adaptive, replay, and distributed runs. It missed
one slow-adaptive run on seed 1618. The result is accepted and reported as-is;
it did not meet the original perfect-detection gate of 12/12.

The live competition path runs Enhanced V2.4 behind FastAPI, drives normal and
extraction profiles through actual HTTP requests, refreshes the dashboard every
0.5 seconds, and shows the first alert with its signals and wall-clock time. See
the [live demo verification](../docs/LIVE_DEMO_VERIFICATION.md).

## Fair improvement comparison

Within the same V2 holdout protocol and traffic, Enhanced V2.4 improved over
the V2 baseline-full detector:

| Metric | Baseline full | Enhanced V2.4 |
|---|---:|---:|
| Attacks detected | 4/12 | 11/12 |
| Benign sessions mitigated | 4/90 | 0/90 |
| Mean final surrogate fidelity | 80.92% | 71.78% |

## Browse V2

- [Accepted holdout results](../docs/V2_HOLDOUT_RESULTS.md)
- [Extended protocol](../docs/EXTENDED_V2.md)
- [Development results](../docs/V2_DEVELOPMENT_RESULTS.md)
- [V1/V2 comparison](../VERSION_COMPARISON.md)
- [Evaluated source snapshot](https://github.com/AT-14/ModelSentry/tree/92a244ee98faa8b1dddf0770849ad4961f7fd79c)

## Verify or reproduce

Download the [frozen V2.4 evidence archive](../modelsentry_v2_holdout.zip), then
verify it directly:

```powershell
python tools/verify_v2_evidence.py modelsentry_v2_holdout.zip
python run_validation_v2.py --quick --seeds 42 --epochs 1 --max-queries 500
```

Use `colab_v2_validation.ipynb` for the full frozen holdout protocol. Source is
shared at the repository root to avoid maintaining duplicate implementations.
