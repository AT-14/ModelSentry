# ModelSentry Version Comparison

The `v1/` and `v2/` folders are clear entry points for reviewers. They describe
the versions and link to their frozen source and evidence. The implementation is
not duplicated because one source tree is easier to audit and maintain.

## What improved

| Capability | V1 | V2.4 |
|---|---|---|
| Detection horizon | Primarily rolling 50-query windows | Short-window telemetry plus long-term confirmation |
| Exact replay detection | No raw-request fingerprint | BLAKE2b request fingerprint |
| Linked-account handling | Independent API keys | Simulated organization-level correlation |
| Attack evaluation | High-volume adaptive focus | Fast, slow, replay, and distributed attacks |
| Benign evaluation | 6 simulated clients | 90 sessions per mode across five profiles |
| Detector comparison | Rate-only comparison | Four identical-traffic detector modes |
| Performance evidence | Experiment metrics | Service and in-process API p50/p95 latency |
| Live demonstration | Completed experiment artifacts | Real HTTP normal-to-attack flow with auto-refreshing alerts |
| Reproducibility | Evidence manifest | Protocol signatures, source revision, and 88-file manifest |

## Result context

| Version | Detection result | Benign result | Final fidelity result |
|---|---:|---:|---:|
| V1 historical baseline | 3/3 required high-volume runs | 0/6 clients blocked | 71.98% defended |
| V2.4 accepted holdout | 11/12 runs across four attack types | 0/90 sessions mitigated | 71.78% mean |

These headline detection fractions are not directly comparable. V2.4 uses a
larger and harder protocol. The fair improvement measurement is the comparison
inside the V2 holdout, where every detector saw identical traffic:

| V2 holdout mode | Attacks detected | Benign sessions mitigated | Mean final fidelity |
|---|---:|---:|---:|
| Baseline full | 4/12 | 4/90 | 80.92% |
| Enhanced V2.4 | 11/12 | 0/90 | 71.78% |

This shows the improvement without hiding the remaining limitation: one
slow-adaptive holdout run was not detected.

## Version links

- [V1 overview](v1/README.md)
- [V2.4 overview](v2/README.md)
- [Historical V1 evidence](docs/VALIDATED_RESULTS.md)
- [Accepted V2.4 evidence](docs/V2_HOLDOUT_RESULTS.md)
