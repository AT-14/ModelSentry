# ModelSentry Baseline V1 Submission Package

This directory is generated from the frozen corrected validation evidence in
`artifacts/validation_corrected`.

## Current status

- `ModelSentry_Submission_DRAFT.pdf`: five-page competition submission draft.
- `dashboard_snapshot.png`: static snapshot generated from the corrected evidence.
- `baseline_v1_manifest.json`: source and evidence SHA-256 hashes.
- `ModelSentry_V1_Source.zip`: reproducible source package.
- `ModelSentry_V1_Evidence.zip`: corrected validation evidence package.

The PDF is deliberately watermarked as a draft until the following values are
provided:

- Team name and member names
- University or organization
- Repository URL
- Backup demonstration video URL

Regenerate the final PDF with:

```powershell
python tools/build_submission.py `
  --team "TEAM NAME" `
  --members "MEMBER ONE" "MEMBER TWO" `
  --university "UNIVERSITY" `
  --repo-url "https://..." `
  --video-url "https://..."
```

The generated file remains named `ModelSentry_Submission_DRAFT.pdf` until the
identity and links are reviewed. Rename it only after the final verification.

## Baseline isolation rule

Do not overwrite `artifacts/validation_corrected` during Extended V2 work. New
experiments must write to a separate output directory and may replace Baseline
V1 only after passing the documented acceptance gate.
