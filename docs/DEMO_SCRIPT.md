# Jury demo script

Target duration: 3-4 minutes.

## 0:00-0:30 - Problem

"A government AI provider exposes a valuable image classifier through an API.
An attacker can collect its answers and train a substitute without accessing its
weights. ModelSentry detects systematic information gathering and limits what the
attacker receives."

## 0:30-1:00 - Legitimate traffic

1. Open the dashboard and point to the live API health indicator.
2. Run `python run_live_traffic.py reset`.
3. Run `python run_live_traffic.py normal`.
4. Show 75 real HTTP predictions and the green no-mitigation status.

## 1:00-1:40 - Extraction behavior

1. Explain that API answers become labels for a different surrogate model.
2. Run `python run_live_traffic.py attack`.
3. Show the extraction request counter updating through actual HTTP requests.
4. Point to the live replay ratio and model-aware evidence.

## 1:40-2:40 - ModelSentry response

1. Show the alert at extraction query 102 and its real wall-clock time.
2. Read the triggering reasons, including the repeated-query ratio.
3. Show the throttle action and denied response count.
4. Run `python run_live_traffic.py invalid`.
5. Show HTTP 422 and confirm that the API remains healthy.

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
