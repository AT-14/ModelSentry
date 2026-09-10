# ModelSentry V2.4 Submission Package

This directory is generated from the accepted V2.4 holdout evidence in
`artifacts/validation_extended_v2_holdout`. The original 12/12 replacement gate
was not met; the presentation reports the verified 11/12 result explicitly.

## Current status

- `ModelSentry_Presentation_DRAFT.pptx`: editable five-slide presentation draft.
- `ModelSentry_Submission_DRAFT.pdf`: matching five-page competition submission draft.
- `dashboard_snapshot.png`: static snapshot generated from V2.4 evidence.
- `v2_holdout_comparison.png`: detector-mode holdout comparison.
- `baseline_v1_manifest.json` and V1 archives: preserved historical packages.

The team identity, university, and repository URL are embedded. The PDF remains
watermarked as a draft only because the public demonstration-video URL is still
pending. `tools/build_submission.py` is retained only as the historical
Baseline V1 PDF builder.

Generate the editable presentation and matching PDF after uploading the video:

```powershell
pip install -r requirements-presentation.txt
python tools/build_presentation.py --video-url "https://..."
```

With a real video URL, this creates `ModelSentry_Presentation.pptx` and
`ModelSentry_Submission.pdf` without the draft watermark.

## Evidence isolation rule

Do not overwrite `artifacts/validation_corrected` or
`artifacts/validation_extended_v2_holdout`. New experiments must write to a
separate output directory. The accepted V2.4 record is documented in
`docs/V2_HOLDOUT_RESULTS.md`.
