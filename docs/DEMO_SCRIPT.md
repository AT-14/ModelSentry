# Jury demo script

Target duration: 3-4 minutes.

## 0:00-0:30 - Problem

"A government AI provider exposes a valuable image classifier through an API.
An attacker can collect its answers and train a substitute without accessing its
weights. ModelSentry detects the information-gathering behavior before that copy
becomes useful."

## 0:30-1:00 - Legitimate traffic

1. Open the dashboard.
2. Point to the healthy protected API.
3. Show normal and high-volume batch clients.
4. Emphasize that both remain fully served; this is not rate limiting alone.

## 1:00-1:40 - Undefended theft

1. Show the saved, reproducible undefended run.
2. Explain that API answers become labels for a different surrogate model.
3. Point to fidelity increasing with query budget.
4. State the measured final fidelity from the verified Colab summary.

## 1:40-2:40 - Same attack with ModelSentry

1. Start or replay the identical seeded attack with defence enabled.
2. Show query rate, boundary frequency, coverage, and acquisition evidence rising.
3. Open the alert reasons.
4. Show persistent evidence triggering throttle and block actions.
5. Point out that ordinary clients remain available.

## 2:40-3:20 - Security outcome

1. Show the defended and undefended fidelity curves together.
2. Mark the mean query at first alert.
3. State responses prevented and fidelity reduction using final verified values.
4. Show detection rate and benign false-positive rate across all seeds.

## 3:20-3:45 - Honest conclusion

"ModelSentry does not claim that model extraction is perfectly detectable.
Patient in-distribution and distributed attackers remain difficult. Our result is
an explainable early-warning and graduated-response layer, validated against a
working extraction attack rather than suspicious traffic alone."

## Backup order

If live services fail, show `multi_seed_fidelity.png`, `per_seed_metrics.csv`,
the dashboard screenshot, and the short recorded run. Do not rerun model training
during judging.
