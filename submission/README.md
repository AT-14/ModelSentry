# ModelSentry V2.4 Submission Package

This directory is generated from the accepted V2.4 holdout evidence in
`artifacts/validation_extended_v2_holdout`. The original 12/12 replacement gate
was not met; the presentation reports the verified 11/12 result explicitly.

## Generated final outputs

- `ModelSentry_Presentation.pptx`: editable five-slide presentation.
- `ModelSentry_Submission.pdf`: linked five-page competition submission.
- `ModelSentry_V2.4_Demo_Team_TSA.mp4`: automated live demonstration.

The PDF and editable presentation are intentionally excluded from Git. The
public demonstration video is tracked so the final PDF can link to a stable,
anonymous download. The PDF embeds the team identity, university, repository
URL, and video URL without a draft watermark. `tools/build_submission.py` is
retained only as the historical Baseline V1 PDF builder.

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
