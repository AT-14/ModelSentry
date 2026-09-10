# Demo Video Guide

Record a clear 3-4 minute demonstration. The live demo shows how the prototype
works; the frozen V2.4 dashboard and chart show the accepted holdout result.
Do not claim that every attack was detected.

## 1. Prepare before recording

Install the project and presentation requirements if needed:

```powershell
pip install -r requirements.txt
pip install -r requirements-presentation.txt
```

Verify the software and frozen evidence:

```powershell
python -m pytest -q
python tools/verify_v2_evidence.py artifacts/validation_extended_v2_holdout
python run_demo.py --quick --seed 42
```

Run the quick demo before recording so training and downloads do not appear in
the video.

## 2. Start the screens to show

Open the dashboard in the first PowerShell window:

```powershell
streamlit run dashboard.py
```

Open the API in a second PowerShell window:

```powershell
python serve_api.py --reset-db --require-checkpoint --demo-reset-token modelsentry-demo
```

Check these pages before recording:

- Dashboard: the URL printed by Streamlit, normally `http://localhost:8501`
- API health: `http://127.0.0.1:8765/health`
- Interactive API documentation: `http://127.0.0.1:8765/docs`
- GitHub versions: `v1/`, `v2/`, and `VERSION_COMPARISON.md`

Close notifications, email, private browser tabs, and unrelated applications.
Use a 1920x1080 display with browser zoom at 100% or higher.

## 3. Record

OBS Studio is recommended. Windows Snipping Tool screen recording or Xbox Game
Bar (`Win+Alt+R`) is also acceptable. Record the screen and a clear microphone;
do not add copyrighted music.

Use this order:

| Time | Show and say |
|---|---|
| 0:00-0:25 | Introduce model theft: an attacker can use API answers as labels for a copy. |
| 0:25-0:55 | Show the API and explain prediction, monitoring, and allow/throttle/block actions. |
| 0:55-1:25 | Run `python run_live_traffic.py reset`, then `python run_live_traffic.py normal`; show the green dashboard. |
| 1:25-2:05 | Run `python run_live_traffic.py attack`; show the live alert, real elapsed seconds, replay ratio, and reasons. |
| 2:05-2:50 | Show the frozen V2.4 comparison: 11/12 attacks and 0/90 benign mitigations. |
| 2:50-3:15 | State that all fast, replay, and distributed runs were detected, but one slow run was missed. |
| 3:15-3:35 | Show the GitHub `v1/` and `v2/` folders, then close with the value and roadmap. |

Use `docs/DEMO_SCRIPT.md` as the full speaking guide. Do not train a model while
recording. If the live dashboard fails, show `submission/dashboard_snapshot.png`
and `submission/v2_holdout_comparison.png`.

After the alert, demonstrate safe unexpected-input handling:

```powershell
python run_live_traffic.py invalid
```

The command must show HTTP 422 and confirm that the API remains healthy. Before
the final recording, run `python run_live_traffic.py all` twice to verify a clean
second run.

## 4. Review the recording

Before uploading, confirm:

- Duration is approximately 3-4 minutes.
- Text is readable at normal playback size.
- Voice is clear and louder than computer noise.
- No passwords, tokens, notifications, or personal tabs are visible.
- The result is stated as 11/12, not 12/12.
- The missed slow-adaptive run is stated plainly.
- The repository URL is visible.
- The normal and extraction phases are actual HTTP traffic, not screenshots.
- AI narration, if used, is disclosed in the end credits.

## 5. Upload and share

YouTube with **Unlisted** visibility is recommended:

1. Sign in to YouTube and choose **Create > Upload video**.
2. Use a title such as `ModelSentry V2.4 Demo - Team TSA`.
3. Set visibility to **Unlisted**, not Private.
4. Finish processing and copy the public video URL.
5. Open an incognito/private browser window and confirm the URL works without
   signing in.

Google Drive is acceptable only if link access is set to **Anyone with the link
can view** and the link works while signed out.

## 6. Generate the final submission

Send the working public URL for final generation, or run:

```powershell
python tools/build_presentation.py --video-url "PUBLIC_VIDEO_URL"
```

This creates:

- `submission/ModelSentry_Presentation.pptx`
- `submission/ModelSentry_Submission.pdf`

Confirm the PDF has five pages, is below 20 MiB, has no draft watermark, and
contains working repository and video links.
