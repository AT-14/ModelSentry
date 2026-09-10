# Baseline V1 Validation Results

These are the frozen Baseline V1 results. They remain the gate-qualified
baseline because Extended V2.4 detected 11/12 rather than the 12/12 required by
its original replacement gate. The accepted V2.4 holdout result is documented
in `docs/V2_HOLDOUT_RESULTS.md`.

## Protocol

| Item | Value |
|---|---:|
| Dataset | Fashion-MNIST |
| Victim training images | 40,000 |
| Victim epochs | 8 |
| Seeds | 42, 7, 123 |
| Maximum extraction budget | 5,000 queries |
| Monitoring window and warmup | 50 queries |
| Benign clients tested | 6 |
| Required extraction campaigns | 3 |

## Headline evidence

| Metric | Result |
|---|---:|
| Victim validation accuracy | 90.56% +/- 0.59 pp |
| Required attack detection rate | 3/3 (100%) |
| Benign clients blocked | 0/6 |
| Undefended surrogate fidelity | 83.45% +/- 1.11 pp |
| Defended surrogate fidelity | 71.98% +/- 1.61 pp |
| Mean fidelity reduction | 11.47 +/- 2.67 pp |
| Responses prevented | 4,655 +/- 184 of 5,000 |
| First alert | 337 +/- 184 queries |

The mean first-alert time is 3.37 simulated seconds at 100 requests per second.
Per-seed alerts occurred at queries 154, 336, and 522.

## Baseline and residual gap

The rate-only baseline detected the 100-query-per-second extraction campaign in
all three seeds and did not flag the two tested benign profiles. This means the
current fast-attack experiment does not by itself prove superiority over rate
limiting; ModelSentry adds model-aware evidence, explanations, and graduated
response.

A replay at the normal interactive rate was not blocked by ModelSentry or the
rate-only baseline. Forcing detection in this case caused a benign false positive
in dry-run testing, so the safer policy was retained. Patient low-rate and
distributed attackers are therefore explicit residual risks.

## Historical Baseline V1 claim

> In a controlled three-seed Fashion-MNIST evaluation, ModelSentry detected all
> three high-volume adaptive extraction campaigns without blocking any of six
> simulated legitimate clients. It prevented an average of 4,655 of 5,000
> attacker responses and reduced mean surrogate fidelity from 83.45% to 71.98%.

Do not generalize this claim to production traffic, all extraction methods, or a
guaranteed zero false-positive rate.

## Evidence locations

- `artifacts/validation_corrected/validation_summary.json`
- `artifacts/validation_corrected/per_seed_metrics.csv`
- `artifacts/validation_corrected/multi_seed_fidelity.png`
- `artifacts/validation_corrected/manifest.json`
