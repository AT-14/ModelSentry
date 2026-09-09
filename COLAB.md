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
