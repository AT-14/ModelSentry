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
4. State the measured 71.78% mean final fidelity from the verified V2.4 holdout.

## 1:40-2:40 - Same attack with ModelSentry

1. Start or replay the identical seeded attack with defence enabled.
2. Show query rate, boundary frequency, coverage, and acquisition evidence rising.
3. Open the alert reasons.
4. Show persistent evidence triggering throttle and block actions.
5. Point out that ordinary clients remain available.

## 2:40-3:20 - Security outcome

1. Show the four-mode holdout comparison.
2. State that Enhanced V2.4 detected 11/12 attack runs.
3. Show that none of 90 benign sessions was mitigated.
4. Disclose that one slow-adaptive run on seed 1618 was missed.

## 3:20-3:45 - Honest conclusion

"ModelSentry does not claim that model extraction is perfectly detectable. In
the untouched holdout, Enhanced V2.4 detected 11 of 12 attacks and mitigated none
of 90 benign sessions. It detected every tested fast, replay, and distributed
run, but missed one slow-adaptive run. This is an explainable early-warning and
graduated-response layer, not a guarantee."

## Backup order

If live services fail, show `per_mode_metrics_v2.csv`, the V2 dashboard snapshot,
and the short recorded run. Do not rerun model training during judging.
