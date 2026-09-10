# ModelSentry

ModelSentry is a reproducible proof of concept for detecting model-extraction
attacks against an image-classification API. It compares normal and malicious
query streams, trains an attacker surrogate from API responses, and measures
whether detection occurs before the surrogate reaches useful fidelity.

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_demo.py --quick
```

The first run downloads Fashion-MNIST and trains a compact victim model. Later
runs reuse the mode- and seed-specific checkpoint in `artifacts/`. Each new
checkpoint includes JSON metadata and a SHA-256 checksum for safe transfer from
Colab or another team member's computer.

Start the HTTP API after the checkpoint exists:

```powershell
python serve_api.py
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

View results from the most recent experiment:

```powershell
streamlit run dashboard.py
```

Run a three-seed local validation with reduced settings:

```powershell
python run_validation.py --quick --seeds 42 7 123
```

For the accepted Extended V2.4 GPU protocol, follow `COLAB.md` and use
`colab_v2_validation.ipynb`. Its `requirements-colab.txt` preserves the
runtime's preinstalled CUDA-enabled PyTorch build.

## Design goals

- CPU-compatible quick mode for the live demonstration.
- Fixed seeds and disjoint data partitions.
- Actual surrogate training rather than synthetic risk labels alone.
- Stateful, explainable monitoring with a rate-only baseline.
- Generated metrics and figures from real experiment runs.

## System architecture

```text
Normal / batch / extraction clients
                 |
                 v
      FastAPI prediction endpoint
                 |
        +--------+---------+
        |                  |
        v                  v
  Protected CNN     Stateful monitor
                           |
                  Risk and evidence
                           |
                 Allow / throttle / block
                           |
                    SQLite + dashboard
```

The HTTP endpoint and simulation runner use the same `PredictionService`.
Consequently, the command-line fallback exercises the same model, monitoring,
logging, and enforcement code as the live API.

## Threat model

The attacker has black-box API access and knows the input and output formats.
They can create multiple valid images, observe returned labels or probabilities,
and train a different local model. They cannot read the victim's weights,
training set, process memory, or event database.

ModelSentry aims to identify sustained extraction behavior before the substitute
model reaches high fidelity. It does not claim perfect detection of patient or
in-distribution attackers. V2.4 correlates simulated linked accounts, but a
production identity resolver remains future work.

All attacks in this repository target the locally owned demonstration model.
Do not run extraction traffic against third-party services without authorization.

## Commands

Run the complete CPU-friendly demonstration:

```powershell
python run_demo.py --quick --seed 42
```

Run independent local validation seeds:

```powershell
python run_validation.py --quick --seeds 42 7 123
```

Run the isolated Extended V2 protocol with expanded traffic, attack scenarios,
detector ablations, alert-time fidelity, and latency measurements:

```powershell
python run_validation_v2.py --quick --seeds 42 --epochs 1 --max-queries 500
```

V2 writes only to `artifacts/validation_extended_v2` by default and refuses to
write inside the frozen `artifacts/validation_corrected` Baseline V1 evidence.
Use `colab_v2_validation.ipynb` for the frozen eight-epoch holdout protocol on
seeds 314, 2718, and 1618.

The verified V2.4 holdout detected 11/12 attacks, mitigated 0/90 benign sessions,
and reached 71.78% mean final surrogate fidelity. One slow-adaptive run was not
detected. The original 12/12 replacement gate was not met, so this result is
reported as accepted extended evidence rather than a perfect-detection claim.
See `docs/V2_HOLDOUT_RESULTS.md` for the final record and
`docs/V2_DEVELOPMENT_RESULTS.md` for development-only results.

Run the full validation protocol, preferably on Colab:

```bash
python run_validation.py --seeds 42 7 123 --epochs 8 --output artifacts/validation
```

Run automated tests:

```powershell
python -m pytest -q
```

## Evidence produced

- `results.json`: complete result from one seed.
- `per_seed_metrics.csv`: auditable row-level metrics across seeds.
- `validation_summary.json`: means, standard deviations, detection rate, and
  benign false-positive rate.
- `fidelity_vs_queries.png`: one-run defended/undefended extraction comparison.
- `multi_seed_fidelity.png`: aggregate curve with variability bands.
- `manifest.json`: SHA-256 hashes of reported evidence.
- `manifest_v2.json`: source revision, protocol signatures, and SHA-256 hashes
  for Extended V2 evidence.
- `*.db`: query transcripts, scores, actions, and alert reasons.

## Metric definitions

- **Victim accuracy:** agreement between the protected model and true labels.
- **Surrogate fidelity:** agreement between attacker and victim predictions on
  an untouched evaluation set.
- **Detection rate:** fraction of extraction sessions that trigger mitigation.
- **Benign false-positive rate:** fraction of legitimate clients incorrectly
  throttled or blocked.
- **Queries to alert:** attempted requests before the first mitigation decision.
- **Responses prevented:** attack requests denied by enforcement.

Thresholds are established from benign calibration streams before attack
evaluation. Data used for victim training, calibration, attacker queries, benign
evaluation, and fidelity evaluation are disjoint.

## Current limitations

- Fashion-MNIST and generated traffic are a proof of concept, not production logs.
- V2 linked-account tests use simulated organization-prefixed identities; a
  production identity resolver is not implemented.
- Slow in-distribution attacks can be substantially harder to distinguish.
- The Information Acquisition Budget is an operational proxy, not theoretical
  mutual information.
- Production deployment requires tenant-specific calibration, drift handling,
  privacy retention controls, and analyst review.

See `docs/ARCHITECTURE.md`, `docs/DEMO_SCRIPT.md`, and
`docs/PRESENTATION_SKELETON.md` for jury-facing material. The accepted V2.4
holdout claim is documented in `docs/V2_HOLDOUT_RESULTS.md`; historical
Baseline V1 evidence remains in `docs/VALIDATED_RESULTS.md`.
