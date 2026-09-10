# Demo Recording Checklist

Target duration: 3-4 minutes. Record at 1920x1080 with browser zoom at 100% or
greater. Do not train a model during recording.

## Preflight

```powershell
python -m pytest -q
python run_demo.py --quick --seed 42
streamlit run dashboard.py
```

In a second terminal, start the API if it is part of the recording:

```powershell
python serve_api.py
```

Verify the dashboard, `http://127.0.0.1:8000/health`, and
`http://127.0.0.1:8000/docs` before recording. Close notifications and unrelated
applications. Keep `artifacts/validation_extended_v2_holdout` as the source of
V2.4 aggregate claims and `artifacts/validation_corrected` unchanged as the
historical Baseline V1 source.

## Recording order

1. Introduce the API model-theft problem and ModelSentry in 30 seconds.
2. Show normal and legitimate batch clients remaining available.
3. Show the saved undefended extraction curve reaching high fidelity.
4. Replay or show the identical defended campaign and its alert reasons.
5. Show throttle/block enforcement and the responses prevented.
6. End on 11/12 detections and 0/90 benign mitigations, then state that one
   slow-adaptive run was missed.

Use `docs/DEMO_SCRIPT.md` as the spoken script. If the live service fails, switch
to `submission/dashboard_snapshot.png` and the saved V2 holdout comparison
rather than retraining.

## After upload

Confirm that the video is viewable without signing in, then regenerate the final
presentation and PDF:

```powershell
python tools/build_presentation.py --video-url "PUBLIC_VIDEO_URL"
```

Check that the output has no draft watermark, that both links open, and that the
PDF remains exactly five pages and below 20 MiB.
