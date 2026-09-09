# Five-page submission skeleton

Use the corrected, frozen values in `docs/VALIDATED_RESULTS.md`.

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
- Stateful per-key windows and five behavioral signal families.
- Benign-calibrated percentiles and persistent multi-signal escalation.
- Information Acquisition Budget as an operational leakage proxy.
- Graduated response: allow, observe, throttle, block.

Primary visual: architecture diagram from `docs/ARCHITECTURE.md`.

## Page 3 - Validation methodology

- Disjoint victim, calibration, attacker, benign, and hidden fidelity partitions.
- Normal, legitimate batch, and adaptive boundary-seeking clients.
- Different surrogate architecture trained from actual API responses.
- Seeds: 42, 7, and 123; 40,000 training images; 8 epochs.
- Metrics: accuracy, fidelity, detection rate, false positives, alert delay,
  responses prevented, and API overhead.

Primary visual: experimental protocol and data-partition diagram.

## Page 4 - Results

- Victim validation accuracy: `90.56% +/- 0.59 pp`.
- Required attack detection rate: `3/3 (100%)`.
- Benign clients blocked: `0/6`.
- Undefended fidelity: `83.45% +/- 1.11 pp`.
- Defended fidelity: `71.98% +/- 1.61 pp`.
- Mean queries to alert: `337 +/- 184`.
- Responses prevented: `4,655 +/- 184 of 5,000`.

Primary visual: final `multi_seed_fidelity.png`. Include one compact metric table.

## Page 5 - Conclusion and deployment

- Demonstrated outcome and strongest attack evidence.
- Why multi-signal stateful monitoring outperforms rate-only detection.
- Limits: synthetic data, drift, patient in-domain attackers, and Sybil accounts.
- Production roadmap: tenant baselines, cross-key linkage, streaming storage,
  drift review, telemetry retention, and analyst feedback.
- Repository and demonstration-video links or QR codes.

Primary visual: dashboard screenshot plus three concise takeaways.
