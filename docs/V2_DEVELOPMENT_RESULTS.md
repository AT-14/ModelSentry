# V2 Development Results

These are development results, not final submission claims. Enhanced policy
v2.4 was designed while inspecting seeds 42, 7, and 123. Final V2 evaluation
must use untouched holdout seeds.

## Protocol

- One training epoch and 8,000 victim-training images per seed.
- Seeds 42, 7, and 123.
- Maximum 500 queries per attack.
- Four attacks per seed: fast adaptive, slow adaptive, replay, and distributed.
- Thirty benign sessions per seed, including five 500-query sessions.
- Identical model checkpoints and traffic partitions for baseline full and
  enhanced comparisons.

## Aggregate comparison

| Metric | Baseline full | Enhanced v2.4 |
|---|---:|---:|
| Attack runs detected | 3/12 | 12/12 |
| Detection rate | 25.0% | 100.0% |
| Benign sessions mitigated | 4/90 | 0/90 |
| Mean final surrogate fidelity | 83.71% | 79.55% |
| Service latency p50 | 16.20 ms | 16.40 ms |
| In-process API latency p50 | 27.00 ms | 26.59 ms |

Enhanced mean queries to alert were 102 for fast, distributed, and replay
attacks, and 365 +/- 110 for slow adaptive extraction.

## Interpretation

The expanded benign workload invalidated the original small-sample assumption
that baseline full had zero false positives. Enhanced v2.4 separates short-window
telemetry from enforcement and requires orthogonal confirmation:

- Extreme rate relative to the calibrated benign maximum.
- Exact repeated-request fingerprints.
- Correlation across authenticated linked accounts.
- Persistent or boundary-heavy long-horizon acquisition.

The quick victim accuracy is approximately 76%, so these fidelity values are not
comparable to the eight-epoch Baseline V1 evidence. They validate the V2 harness
and policy direction only.

## Holdout gate

Run the full eight-epoch protocol on untouched seeds 314, 2718, and 1618. Do not
replace Baseline V1 unless enhanced V2 detects all required attack categories,
does not worsen benign mitigation, lowers attacker fidelity, and remains
reproducible from its manifest.
