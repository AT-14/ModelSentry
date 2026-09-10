# Accepted V2.4 Holdout Results

These are the final accepted Extended V2.4 results. The run used the frozen
source revision `92a244ee98faa8b1dddf0770849ad4961f7fd79c` and untouched seeds
314, 2718, and 1618. All 88 files listed by the manifest passed SHA-256
verification.

## Protocol

| Item | Value |
|---|---:|
| Dataset | Fashion-MNIST |
| Victim training images | 40,000 |
| Victim epochs | 8 |
| Holdout seeds | 314, 2718, 1618 |
| Detector modes | Rate-only, model-aware, full, enhanced |
| Attack scenarios per mode | Fast adaptive, slow adaptive, replay, distributed |
| Benign sessions per mode | 90 across three seeds |

## Headline evidence

| Metric | Enhanced V2.4 result |
|---|---:|
| Victim validation accuracy | 90.39% +/- 0.35 pp |
| Attack runs detected | 11/12 (91.67%) |
| Benign sessions mitigated | 0/90 |
| Mean final surrogate fidelity | 71.78% +/- 7.94 pp |
| Service latency p50 / p95 | 7.30 / 8.45 ms |
| In-process API latency p50 / p95 | 12.93 / 14.84 ms |

Enhanced V2.4 detected every fast adaptive, replay, and distributed run. It
detected two of three slow-adaptive runs. The missed run used seed 1618, reached
84.02% final surrogate fidelity after 2,000 answered queries, and remained in
monitoring rather than mitigation.

## Mode comparison

| Mode | Attacks detected | Benign sessions mitigated | Mean final fidelity |
|---|---:|---:|---:|
| Rate-only | 3/12 | 18/90 | 77.48% |
| Model-aware | 2/12 | 2/90 | 82.68% |
| Baseline full | 4/12 | 4/90 | 80.92% |
| Enhanced V2.4 | 11/12 | 0/90 | 71.78% |

## Acceptance record

The team accepts V2.4 as the final extended evaluation result and will report it
without hiding the missed slow-adaptive run. V2.4 did not meet the original
perfect-detection replacement gate of 12/12, so Baseline V1 remains the
gate-qualified baseline rather than being retroactively displaced.

Approved V2.4 claim:

> In a controlled three-seed Fashion-MNIST holdout evaluation, Enhanced
> ModelSentry V2.4 detected 11 of 12 extraction runs, including all tested fast,
> replay, and distributed runs, while mitigating none of 90 simulated benign
> sessions. Mean final surrogate fidelity was 71.78%. One slow-adaptive run was
> not detected.

Do not generalize this result to production traffic, guaranteed detection, or a
guaranteed zero false-positive rate.

## Evidence

- Local archive: `modelsentry_v2_holdout.zip`
- Archive SHA-256: `9ec0f0334116344142ba2feecf31eb15ce0834c164c83f7bf75b97e3be2ebcf5`
- Extracted directory: `artifacts/validation_extended_v2_holdout`
- Manifest: `artifacts/validation_extended_v2_holdout/manifest_v2.json`
- Summary: `artifacts/validation_extended_v2_holdout/validation_summary_v2.json`

Verify either the downloaded ZIP or extracted directory with:

```powershell
python tools/verify_v2_evidence.py "$HOME\Downloads\modelsentry_v2_holdout.zip"
python tools/verify_v2_evidence.py artifacts/validation_extended_v2_holdout
```
