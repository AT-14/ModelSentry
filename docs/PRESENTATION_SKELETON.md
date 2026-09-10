# Five-page submission skeleton

Use the accepted holdout values in `docs/V2_HOLDOUT_RESULTS.md`. Baseline V1
values may be identified as historical evidence but must not replace the V2.4
headline result.

## Page 1 - Title and objective

**ModelSentry: Detecting Model Theft Before the Clone Becomes Useful**

- One-sentence value proposition.
- Buyer: government AI-platform and security-operations teams.
- Threat: black-box extraction through a prediction API.
- Business impact: IP loss, avoided API fees, and easier adversarial reconnaissance.
- Replacement: manual log review and rate-only controls.

Primary visual: simple attacker-to-API-to-surrogate diagram.

## Page 2 - Proposed solution

- Protected Fashion-MNIST CNN behind FastAPI.
- Stateful per-key windows and multi-timescale behavioral evidence.
- Benign-calibrated percentiles, exact replay fingerprints, and linked-account
  correlation.
- Information Acquisition Budget as an operational leakage proxy.
- Graduated response: allow, observe, throttle, block.

Primary visual: architecture diagram from `docs/ARCHITECTURE.md`.

## Page 3 - Validation methodology

- Disjoint victim, calibration, attacker, benign, and hidden fidelity partitions.
- Five benign profiles and four attacks: fast adaptive, slow adaptive, replay,
  and distributed linked accounts.
- Different surrogate architecture trained from actual API responses.
- Holdout seeds: 314, 2718, and 1618; 40,000 training images; 8 epochs.
- Metrics: accuracy, fidelity, detection rate, false positives, alert delay,
  responses prevented, and API overhead.

Primary visual: experimental protocol and data-partition diagram.

## Page 4 - Results

- Victim validation accuracy: `90.39% +/- 0.35 pp`.
- Attack detection: `11/12 (91.67%)`.
- Benign sessions mitigated: `0/90`.
- Mean final surrogate fidelity: `71.78% +/- 7.94 pp`.
- Service latency p50/p95: `7.30/8.45 ms`.
- In-process API latency p50/p95: `12.93/14.84 ms`.
- Explicit limitation: one slow-adaptive run was not detected.

Primary visual: detector-mode comparison. Include one compact metric table.

## Page 5 - Conclusion and deployment

- Demonstrated outcome and strongest attack evidence.
- Why enhanced multi-timescale monitoring outperformed the tested baselines.
- Limits: synthetic data, drift, one missed slow-adaptive run, and simulated
  rather than production-linked identities.
- Production roadmap: tenant baselines, cross-key linkage, streaming storage,
  drift review, telemetry retention, and analyst feedback.
- Repository and demonstration-video links or QR codes.

Primary visual: dashboard screenshot plus three concise takeaways.
