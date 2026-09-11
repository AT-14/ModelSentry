import argparse
import asyncio
import base64
import contextlib
import html
import io
import json
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import edge_tts
import httpx
import imageio_ffmpeg
import torch
from mutagen.mp3 import MP3
from playwright.sync_api import Page, sync_playwright

from modelsentry.config import ExperimentConfig
from modelsentry.data import load_partitions
from run_live_traffic import (
    check_unexpected_input,
    dataset_images,
    reset_demo,
    run_attack_phase,
    run_normal_phase,
)


SUBMISSION = ROOT / "submission"
WORK = SUBMISSION / "video_work"
API_URL = "http://127.0.0.1:8765"
DASHBOARD_URL = "http://127.0.0.1:8501"
DEFAULT_OUTPUT = SUBMISSION / "ModelSentry_Demo_DRAFT.mp4"


@dataclass(frozen=True)
class Scene:
    key: str
    narration: str


@dataclass(frozen=True)
class TrafficData:
    normal_images: torch.Tensor
    attack_pool: torch.Tensor


SCENES = (
    Scene(
        "title",
        "Artificial intelligence models are valuable intellectual property. "
        "A black-box attacker does not need to steal the model file. By sending "
        "carefully selected requests to a prediction API, collecting its answers, "
        "and training a substitute, the attacker can imitate valuable behavior. "
        "ModelSentry is a working security prototype that detects systematic model "
        "learning and limits information exposure as extraction behavior emerges.",
    ),
    Scene(
        "api",
        "The prototype protects a Fashion-MNIST convolutional neural network behind "
        "a real FastAPI endpoint. Every request is validated, classified, and passed "
        "through a stateful monitor. The monitor combines query rate, embedding "
        "diversity, exact repetition, decision-boundary activity, and linked-account "
        "evidence. Its graduated policy can allow, observe, throttle, or block while "
        "persisting explainable evidence for the dashboard.",
    ),
    Scene(
        "normal",
        "We begin by resetting the demonstration and sending seventy-five unique, "
        "legitimate images through the actual HTTP API. Watch the counters update "
        "automatically. All normal predictions remain available, no request is "
        "throttled or blocked, and the dashboard stays green. This matters because a "
        "security control that stops ordinary users would not be operationally useful.",
    ),
    Scene(
        "attack",
        "Next, we launch a replay-style extraction campaign. The attacker cycles "
        "through a diverse pool of fifty images and attempts to collect the protected "
        "model's answers. Individual requests are valid, so ModelSentry evaluates the "
        "sequence rather than judging one image in isolation. As repeated requests "
        "accumulate, the long-term replay ratio crosses twenty percent and remains "
        "persistent. At extraction query one hundred and two, ModelSentry issues a "
        "throttle alert and explains the triggering evidence.",
    ),
    Scene(
        "invalid",
        "The service also handles unexpected input safely. A malformed request with "
        "the wrong number of pixels receives HTTP status four hundred and twenty-two. "
        "The process does not crash, and the API health check remains green.",
    ),
    Scene(
        "validation",
        "The live demonstration is supported by a frozen three-seed holdout, not used "
        "for tuning. Four attack styles were evaluated: fast adaptive, slow adaptive, "
        "replay, and distributed extraction. Across twelve attack runs, Enhanced "
        "Version Two Point Four detected eleven, while producing zero false positives "
        "across ninety benign sessions. Mean final attacker fidelity was seventy-one "
        "point seven eight percent. The manifest verifies all eighty-eight evidence "
        "files so the reported result remains auditable.",
    ),
    Scene(
        "comparison",
        "On identical Version Two traffic, the baseline-full detector found four of "
        "twelve attacks and incorrectly mitigated four of ninety benign sessions. "
        "Enhanced Version Two Point Four increased detection to eleven of twelve, "
        "reduced benign false positives to zero, and lowered mean final attacker "
        "fidelity from eighty point nine two percent to seventy-one point seven eight "
        "percent. The limitation is explicit: one patient slow-adaptive run was not "
        "detected.",
    ),
    Scene(
        "conclusion",
        "ModelSentry demonstrates that model theft can be treated as an observable "
        "security incident rather than invisible API usage. It preserves legitimate "
        "access, correlates multi-timescale evidence, explains alerts, and applies "
        "graduated containment. Production work would add enterprise identity "
        "resolution, streaming storage, traffic-drift review, and analyst feedback. "
        "The source code and reproducible evidence are available in the public "
        "ModelSentry repository. Narration in this video was generated using artificial "
        "intelligence; all software behavior, traffic, and results shown are authentic.",
    ),
)


def image_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def card_html(
    kicker: str,
    title: str,
    body: str,
    metrics: tuple[tuple[str, str], ...] = (),
    image: Path | None = None,
    image_height: int = 500,
    footer: str = "School of Cyber Defence 2026 | Team TSA",
) -> str:
    metric_html = "".join(
        '<div class="metric"><strong>'
        + html.escape(value)
        + "</strong><span>"
        + html.escape(label)
        + "</span></div>"
        for value, label in metrics
    )
    image_html = (
        f'<img class="evidence" style="max-height:{image_height}px" '
        f'src="{image_uri(image)}" alt="Evidence">'
        if image is not None
        else ""
    )
    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; }}
body {{ margin: 0; width: 100vw; height: 100vh; overflow: hidden; background: #071018;
  color: #f7fafc; font-family: Arial, sans-serif; }}
main {{ height: 100%; padding: 70px 90px 54px; display: flex; flex-direction: column; }}
.kicker {{ color: #69d4c5; font-size: 21px; font-weight: 800; letter-spacing: 2px;
  text-transform: uppercase; }}
h1 {{ margin: 24px 0 18px; max-width: 1500px; font-size: 62px; line-height: 1.08; }}
.body {{ max-width: 1500px; color: #c6d2da; font-size: 29px; line-height: 1.48; }}
.metrics {{ display: flex; gap: 24px; margin-top: 42px; }}
.metric {{ min-width: 250px; flex: 1; padding: 25px 27px; border: 2px solid #294453;
  border-radius: 16px; background: #0d1c27; }}
.metric strong {{ display: block; color: #f4b942; font-size: 43px; }}
.metric span {{ display: block; margin-top: 10px; color: #9aabb7; font-size: 16px;
  font-weight: 700; text-transform: uppercase; }}
.evidence {{ margin-top: 28px; max-width: 100%; object-fit: contain;
  object-position: left center; border: 2px solid #294453; border-radius: 14px; }}
footer {{ margin-top: auto; padding-top: 18px; border-top: 1px solid #294453;
  color: #9aabb7; font-size: 16px; text-transform: uppercase; }}
</style>
</head>
<body><main>
<div class="kicker">{html.escape(kicker)}</div>
<h1>{html.escape(title)}</h1>
<div class="body">{html.escape(body)}</div>
<div class="metrics">{metric_html}</div>
{image_html}
<footer>{html.escape(footer)}</footer>
</main></body>
</html>
"""


async def generate_narration(voice: str) -> dict[str, Path]:
    narration_dir = WORK / "narration"
    narration_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    for scene in SCENES:
        destination = narration_dir / f"{scene.key}.mp3"
        print(f"Generating narration: {scene.key}", flush=True)
        await edge_tts.Communicate(
            scene.narration,
            voice,
            rate="+12%",
            volume="+0%",
        ).save(destination)
        outputs[scene.key] = destination
    return outputs


def wait_for_url(url: str, timeout_seconds: float = 120.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=1.0).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Service did not become ready: {url}")


def require_free_port(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        if connection.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(
                f"Port {port} is already in use. Stop the existing service and retry."
            )


def start_process(arguments: list[str], log_name: str) -> tuple[subprocess.Popen, object]:
    log = (WORK / log_name).open("w", encoding="utf-8")
    creationflags = (
        subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )
    process = subprocess.Popen(
        arguments,
        cwd=ROOT,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        text=True,
    )
    return process, log


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def load_traffic_data() -> TrafficData:
    config = ExperimentConfig(
        seed=42,
        data_dir=ROOT / "data",
        artifacts_dir=ROOT / "artifacts",
    )
    partitions = load_partitions(config)
    return TrafficData(
        normal_images=dataset_images(partitions.benign_evaluation, 75),
        attack_pool=dataset_images(partitions.attack_pool, 50),
    )


def capture_traffic(name: str, operation):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = operation()
    text = output.getvalue().strip()
    (WORK / f"traffic_{name}.log").write_text(text + "\n", encoding="utf-8")
    return result, text


def prepare_dashboard(page: Page) -> None:
    page.goto(DASHBOARD_URL, wait_until="domcontentloaded", timeout=120_000)
    page.get_by_text("Live competition demo", exact=True).wait_for(timeout=120_000)
    page.evaluate("document.body.style.zoom = '85%'")
    page.evaluate("window.scrollTo(0, 0)")


def record_browser(
    narration: dict[str, Path],
    traffic: TrafficData,
    headed: bool,
    browser_channel: str | None,
) -> tuple[Path, dict[str, float], float]:
    chart = SUBMISSION / "v2_holdout_comparison.png"
    snapshot = SUBMISSION / "dashboard_snapshot.png"
    qr = SUBMISSION / "repository_qr.png"
    chart = chart if chart.exists() else None
    snapshot = snapshot if snapshot.exists() else None
    qr = qr if qr.exists() else None

    durations = {key: MP3(path).info.length for key, path in narration.items()}
    raw_dir = WORK / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    offsets: dict[str, float] = {}

    with httpx.Client(
        base_url=API_URL, timeout=20.0
    ) as traffic_client, sync_playwright() as playwright:
        launch_options = {"headless": not headed}
        if browser_channel:
            launch_options["channel"] = browser_channel
        browser = playwright.chromium.launch(**launch_options)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=raw_dir,
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.set_default_timeout(120_000)
        video = page.video
        recording_started = time.monotonic()

        def hold(key: str, operation=None, padding: float = 0.5) -> None:
            offsets[key] = time.monotonic() - recording_started
            scene_started = time.monotonic()
            if operation is not None:
                operation()
            remaining = durations[key] + padding - (time.monotonic() - scene_started)
            if remaining > 0:
                page.wait_for_timeout(int(remaining * 1000))

        page.set_content(
            card_html(
                "Model IP defense control room",
                "ModelSentry",
                "Detect model-theft behavior and limit API leakage.",
                (("11/12", "attacks detected"), ("0/90", "benign false positives"),
                 ("71.78%", "mean final fidelity")),
            )
        )
        hold("title")

        page.goto(f"{API_URL}/docs", wait_until="domcontentloaded", timeout=120_000)
        page.get_by_text("ModelSentry protected inference API").wait_for()
        page.evaluate("document.body.style.zoom = '115%'")
        hold("api")

        capture_traffic(
            "reset", lambda: reset_demo(traffic_client, "modelsentry-demo")
        )
        prepare_dashboard(page)

        def normal_traffic() -> None:
            capture_traffic(
                "normal",
                lambda: run_normal_phase(
                    traffic_client, traffic.normal_images, delay_seconds=0.10
                ),
            )
            page.get_by_text("GREEN: normal traffic is allowed", exact=False).wait_for()

        hold("normal", normal_traffic, padding=1.0)

        def attack_traffic() -> None:
            capture_traffic(
                "attack",
                lambda: run_attack_phase(
                    traffic_client,
                    traffic.attack_pool,
                    maximum_queries=150,
                    delay_seconds=0.08,
                ),
            )
            prepare_dashboard(page)
            page.get_by_text("ALERT: THROTTLE", exact=False).wait_for()

        hold("attack", attack_traffic, padding=1.0)

        _, invalid_output = capture_traffic(
            "invalid", lambda: check_unexpected_input(traffic_client)
        )
        health = httpx.get(f"{API_URL}/health", timeout=5.0).json()["status"]
        page.set_content(
            card_html(
                "Resilient API handling",
                "Unexpected input rejected safely",
                "A real malformed prediction request returned HTTP 422. "
                f"The follow-up API health check returned: {health}.",
                (("HTTP 422", "invalid request"), (health.upper(), "API health")),
                footer=invalid_output.splitlines()[-1],
            )
        )
        hold("invalid")

        page.set_content(
            card_html(
                "Solution validation",
                "Frozen three-seed holdout",
                "Four detector modes were evaluated on identical attack and benign traffic.",
                (("11/12", "enhanced detections"), ("0/90", "benign false positives"),
                 ("88/88", "manifest hashes verified")),
                image=chart,
            )
        )
        hold("validation")

        page.set_content(
            card_html(
                "Measured improvement",
                "Stronger detection, lower attacker fidelity",
                "Baseline full and Enhanced V2.4 use the same V2 traffic and protocol.",
                (("4/12 -> 11/12", "attack detection"),
                 ("4/90 -> 0/90", "benign false positives"),
                 ("80.92% -> 71.78%", "mean final fidelity")),
                image=snapshot,
            )
        )
        hold("comparison")

        page.set_content(
            card_html(
                "Results and conclusions",
                "Operationally useful, honestly bounded",
                "All fast, replay, and distributed runs were detected. One slow-adaptive "
                "run was missed. Source and evidence: github.com/AT-14/ModelSentry",
                (("ALLOW", "legitimate access"), ("THROTTLE", "persistent risk"),
                 ("BLOCK", "continued abuse")),
                image=qr,
                image_height=330,
                footer="AI narration | Authentic software results and screen capture",
            )
        )
        hold("conclusion", padding=1.5)

        total_duration = time.monotonic() - recording_started
        context.close()
        raw_path = WORK / "ModelSentry_Demo_raw.webm"
        video.save_as(raw_path)
        browser.close()

    return raw_path, offsets, total_duration


def mix_video(
    raw_video: Path,
    narration: dict[str, Path],
    offsets: dict[str, float],
    total_duration: float,
    output: Path,
) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, "-y", "-i", str(raw_video)]
    for scene in SCENES:
        command.extend(["-i", str(narration[scene.key])])

    filters = [
        f"anullsrc=r=48000:cl=stereo,atrim=duration={total_duration + 1.0:.3f}[base]"
    ]
    delayed = []
    for index, scene in enumerate(SCENES, start=1):
        label = f"voice{index}"
        delay_ms = max(0, round(offsets[scene.key] * 1000))
        filters.append(
            f"[{index}:a]aresample=48000,aformat=channel_layouts=stereo,"
            f"adelay={delay_ms}:all=1[{label}]"
        )
        delayed.append(f"[{label}]")
    filters.append(
        "[base]"
        + "".join(delayed)
        + f"amix=inputs={len(SCENES) + 1}:duration=longest:normalize=0,"
        "alimiter=limit=0.95[aout]"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output),
        ]
    )
    print("Combining browser capture and AI narration", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an authentic automated ModelSentry demonstration video"
    )
    parser.add_argument("--voice", default="en-US-GuyNeural")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--browser-channel",
        help="Use an installed browser channel such as msedge instead of Playwright Chromium",
    )
    parser.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if not args.keep_work:
        try:
            output.resolve().relative_to(WORK.resolve())
        except ValueError:
            pass
        else:
            raise ValueError("Output inside submission/video_work requires --keep-work")

    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    require_free_port(8765)
    require_free_port(8501)

    narration = asyncio.run(generate_narration(args.voice))
    print("Loading deterministic traffic images", flush=True)
    traffic = load_traffic_data()
    api_process = dashboard_process = None
    api_log = dashboard_log = None
    try:
        api_process, api_log = start_process(
            [
                sys.executable,
                "serve_api.py",
                "--reset-db",
                "--require-checkpoint",
                "--demo-reset-token",
                "modelsentry-demo",
            ],
            "api.log",
        )
        dashboard_process, dashboard_log = start_process(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "dashboard.py",
                "--server.headless=true",
                "--server.port=8501",
                "--browser.gatherUsageStats=false",
            ],
            "dashboard.log",
        )
        wait_for_url(f"{API_URL}/health")
        wait_for_url(DASHBOARD_URL)
        raw_video, offsets, total_duration = record_browser(
            narration, traffic, args.headed, args.browser_channel
        )
        (WORK / "timeline.json").write_text(
            json.dumps(
                {"offsets": offsets, "total_duration": total_duration}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        mix_video(raw_video, narration, offsets, total_duration, output)
    finally:
        stop_process(dashboard_process)
        stop_process(api_process)
        if dashboard_log is not None:
            dashboard_log.close()
        if api_log is not None:
            api_log.close()

    print(f"Wrote {output}", flush=True)
    if not args.keep_work:
        shutil.rmtree(WORK)


if __name__ == "__main__":
    main()
