# ModelSentry V1

V1 is the historical, gate-qualified baseline. It established the working
prediction API, stateful behavioral monitor, graduated enforcement, SQLite
evidence, dashboard, and reproducible three-seed validation.

## Validated result

| Metric | V1 result |
|---|---:|
| Required high-volume attacks detected | 3/3 |
| Simulated benign clients blocked | 0/6 |
| Undefended surrogate fidelity | 83.45% +/- 1.11 pp |
| Defended surrogate fidelity | 71.98% +/- 1.61 pp |
| Responses prevented | 4,655 +/- 184 of 5,000 |
| Mean first alert | 337 +/- 184 queries |

V1 used seeds 42, 7, and 123 with 40,000 victim-training images and eight
epochs. Its required test focused on a high-volume adaptive attack. Slow replay
and distributed attacks were documented as residual risks.

## Browse V1

- [Detailed V1 results](../docs/VALIDATED_RESULTS.md)
- [Architecture](../docs/ARCHITECTURE.md)
- [V1 source snapshot](https://github.com/AT-14/ModelSentry/tree/8e3e800)
- [V1/V2 comparison](../VERSION_COMPARISON.md)

## Reproduce

```powershell
python run_validation.py --seeds 42 7 123 --epochs 8 --output artifacts/validation
```

The current source retains V1 for historical comparison, but the command above
does not recreate a separate copy of the repository inside this folder.
