# Full validation in Google Colab

## Before opening Colab

Use `ModelSentry-colab.zip`, which excludes local datasets, checkpoints,
databases, and Git metadata. Upload both the archive and
`colab_full_validation.ipynb` to Colab.

## Colab runtime

1. Open the notebook in Google Colab.
2. Select **Runtime > Change runtime type > T4 GPU**.
3. Run each cell in order.
4. Upload `ModelSentry-colab.zip` when prompted.
5. Keep the browser tab open until all three seeds finish.
6. Download `modelsentry_validation.zip` from the final cell.

The notebook installs `requirements-colab.txt`, which deliberately preserves
Colab's preinstalled CUDA-enabled PyTorch and Torchvision versions.

The full command executed by the notebook is:

```bash
python run_validation.py --seeds 42 7 123 --epochs 8 --output /content/validation_results
```

## Expected outputs

- `per_seed_metrics.csv`: one row per independent seed.
- `validation_summary.json`: means, standard deviations, detection rate, and
  benign false-positive rate.
- `multi_seed_fidelity.png`: mean fidelity curves with one-standard-deviation
  bands.
- `manifest.json`: SHA-256 hashes that freeze the reported evidence.
- `seed_*/results.json`: complete evidence for each run.
- `seed_*/victim_model_*.pt`: portable model checkpoints.

Do not manually edit the generated CSV, JSON, or chart. If the detector or
experiment changes, rerun all seeds and use the new manifest.

## Extended V2 holdout

V2 uses `colab_v2_validation.ipynb`, which clones the public repository directly
instead of uploading a local archive.

The notebook runs the frozen enhanced v2.4 policy and all three comparison modes
on untouched seeds 314, 2718, and 1618. It evaluates four attack scenarios and
30 benign sessions per mode and seed. Do not replace these seeds with development
seeds 42, 7, and 123.

The V2 command is:

```bash
python run_validation_v2.py --seeds 314 2718 1618 --epochs 8 \
  --modes rate_only model_aware full enhanced \
  --output /content/validation_extended_v2_holdout
```

Treat `docs/V2_DEVELOPMENT_RESULTS.md` only as development evidence. Update final
claims only after downloading and verifying the V2 holdout manifest.

## Completed V2.4 run

The final archive was generated from source revision
`92a244ee98faa8b1dddf0770849ad4961f7fd79c`. All 88 manifested files passed
SHA-256 verification. Enhanced V2.4 detected 11/12 attacks, mitigated 0/90
benign sessions, and reached 71.78% mean final surrogate fidelity. The missed
run was slow adaptive on seed 1618.

Verify the downloaded archive with:

```powershell
python tools/verify_v2_evidence.py "$HOME\Downloads\modelsentry_v2_holdout.zip"
```
