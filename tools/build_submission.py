"""Build the historical Baseline V1 PDF.

Use tools/build_presentation.py for the accepted V2.4 presentation and PDF.
"""

import argparse
import json
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts" / "validation_corrected"
SUBMISSION = ROOT / "submission"

NAVY = "#071018"
PANEL = "#0d1c27"
PANEL_LIGHT = "#132a38"
INK = "#f7fafc"
MUTED = "#9aabb7"
GOLD = "#f4b942"
TEAL = "#69d4c5"
RED = "#ef6a6a"


def setup_slide(kicker: str, title: str, page: int, draft: bool = False) -> tuple[plt.Figure, plt.Axes]:
    figure, axis = plt.subplots(figsize=(13.333, 7.5), facecolor=NAVY)
    axis.set_facecolor(NAVY)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    axis.text(0.055, 0.94, kicker.upper(), color=TEAL, fontsize=9, weight="bold")
    if draft:
        axis.text(
            0.945,
            0.94,
            "DRAFT | IDENTITY + LINKS PENDING",
            color=RED,
            fontsize=8,
            weight="bold",
            ha="right",
        )
    axis.text(0.055, 0.875, title, color=INK, fontsize=25, weight="bold", va="top")
    axis.plot([0.055, 0.945], [0.055, 0.055], color="#294453", linewidth=0.8)
    axis.text(0.055, 0.027, "SCHOOL OF CYBER DEFENCE 2026", color=MUTED, fontsize=7)
    axis.text(0.945, 0.027, f"MODELSENTRY  |  {page}/5", color=MUTED, fontsize=7, ha="right")
    return figure, axis


def panel(axis: plt.Axes, x: float, y: float, width: float, height: float) -> None:
    axis.add_patch(
        FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.008,rounding_size=0.012",
            facecolor=PANEL,
            edgecolor="#234352",
            linewidth=0.9,
        )
    )


def wrapped(axis: plt.Axes, x: float, y: float, text: str, width: int, **kwargs) -> None:
    axis.text(x, y, textwrap.fill(text, width), **kwargs)


def metric_card(
    axis: plt.Axes,
    x: float,
    y: float,
    width: float,
    value: str,
    label: str,
    accent: str = GOLD,
) -> None:
    panel(axis, x, y, width, 0.14)
    axis.text(x + 0.018, y + 0.087, value, color=accent, fontsize=19, weight="bold")
    axis.text(x + 0.018, y + 0.035, label.upper(), color=MUTED, fontsize=7.5, weight="bold")


def format_pm(metric: dict, percent: bool = True) -> str:
    scale = 100 if percent else 1
    return f"{metric['mean'] * scale:.2f} +/- {metric['std'] * scale:.2f}"


def draw_arrow_flow(axis: plt.Axes, items: list[tuple[str, str]], y: float) -> None:
    count = len(items)
    width = 0.16
    gap = (0.89 - count * width) / (count - 1)
    x = 0.055
    for index, (heading, detail) in enumerate(items):
        panel(axis, x, y, width, 0.17)
        axis.text(x + 0.012, y + 0.115, heading, color=INK, fontsize=10, weight="bold")
        wrapped(axis, x + 0.012, y + 0.085, detail, 22, color=MUTED, fontsize=7.5, va="top")
        if index < count - 1:
            axis.annotate(
                "",
                xy=(x + width + gap - 0.012, y + 0.085),
                xytext=(x + width + 0.012, y + 0.085),
                arrowprops={"arrowstyle": "->", "color": GOLD, "lw": 1.6},
            )
        x += width + gap


def build_dashboard_snapshot(summary: dict, frame: pd.DataFrame, destination: Path) -> None:
    figure, axis = plt.subplots(figsize=(13.333, 7.5), facecolor=NAVY)
    axis.set_facecolor(NAVY)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    axis.text(0.05, 0.94, "MODEL IP DEFENSE CONTROL ROOM", color=TEAL, fontsize=9, weight="bold")
    axis.text(0.05, 0.87, "ModelSentry", color=INK, fontsize=28, weight="bold")
    axis.text(0.05, 0.82, "Corrected three-seed validation snapshot", color=MUTED, fontsize=11)
    cards = [
        ("3/3", "Attacks detected"),
        ("0/6", "Benign blocked"),
        (f"{summary['fidelity_reduction']['mean']:.1%}", "Fidelity reduction"),
        (f"{summary['responses_prevented']['mean']:.0f}", "Responses prevented"),
    ]
    for index, (value, label) in enumerate(cards):
        metric_card(axis, 0.05 + index * 0.23, 0.62, 0.205, value, label)

    panel(axis, 0.05, 0.12, 0.56, 0.42)
    axis.text(0.072, 0.49, "SURROGATE FIDELITY BY SEED", color=INK, fontsize=10, weight="bold")
    seeds = np.arange(len(frame))
    axis.bar(
        0.12 + seeds * 0.14,
        frame["undefended_final_fidelity"] * 0.30,
        width=0.045,
        color=RED,
        label="Undefended",
        bottom=0.17,
    )
    axis.bar(
        0.17 + seeds * 0.14,
        frame["defended_final_fidelity"] * 0.30,
        width=0.045,
        color=TEAL,
        label="Defended",
        bottom=0.17,
    )
    for index, seed in enumerate(frame["seed"]):
        axis.text(0.145 + index * 0.14, 0.145, str(seed), color=MUTED, fontsize=8, ha="center")
    axis.text(0.075, 0.145, "SEED", color=MUTED, fontsize=7)
    axis.legend(loc="lower left", bbox_to_anchor=(0.07, 0.19), frameon=False, labelcolor=INK, fontsize=8)

    panel(axis, 0.65, 0.12, 0.30, 0.42)
    axis.text(0.675, 0.49, "POLICY STATUS", color=INK, fontsize=10, weight="bold")
    axis.text(0.675, 0.415, "FAST EXTRACTION", color=MUTED, fontsize=7.5, weight="bold")
    axis.text(0.675, 0.365, "DETECTED", color=TEAL, fontsize=17, weight="bold")
    axis.text(0.675, 0.285, "LOW-RATE REPLAY", color=MUTED, fontsize=7.5, weight="bold")
    axis.text(0.675, 0.235, "RESIDUAL GAP", color=GOLD, fontsize=17, weight="bold")
    axis.text(0.675, 0.17, "No result is hidden or hand-edited.", color=MUTED, fontsize=8)
    figure.savefig(destination, dpi=180, facecolor=NAVY, bbox_inches="tight")
    plt.close(figure)


def build_pdf(
    summary: dict,
    frame: pd.DataFrame,
    destination: Path,
    team: str,
    members: list[str],
    university: str,
    repo_url: str,
    video_url: str,
) -> None:
    chart_path = EVIDENCE / "multi_seed_fidelity.png"
    draft = any("TO BE ADDED" in value for value in (team, university, repo_url, video_url))
    with PdfPages(destination) as pdf:
        metadata = pdf.infodict()
        metadata["Title"] = "ModelSentry: AI Model Extraction Detection"
        metadata["Author"] = f"{team}: {', '.join(members)}" if members else team
        metadata["Subject"] = "School of Cyber Defence 2026 submission"
        metadata["Keywords"] = "model extraction, API security, machine learning, cybersecurity"

        figure, axis = setup_slide("National cybersecurity competition", "ModelSentry", 1, draft)
        axis.text(0.055, 0.75, "Detect model theft before the copy becomes useful.", color=GOLD, fontsize=22)
        wrapped(
            axis,
            0.055,
            0.665,
            "A stateful API-security layer that identifies systematic model learning, explains the evidence, and limits information exposure before a surrogate becomes valuable.",
            88,
            color=INK,
            fontsize=11,
            va="top",
            linespacing=1.45,
        )
        metric_card(axis, 0.055, 0.39, 0.20, "3/3", "Extraction campaigns detected")
        metric_card(axis, 0.275, 0.39, 0.20, "0/6", "Legitimate clients blocked", TEAL)
        metric_card(
            axis,
            0.495,
            0.39,
            0.20,
            f"{summary['fidelity_reduction']['mean']:.1%}",
            "Mean fidelity reduction",
        )
        metric_card(
            axis,
            0.715,
            0.39,
            0.20,
            f"{summary['responses_prevented']['mean']:.0f}",
            "Responses prevented",
            TEAL,
        )
        panel(axis, 0.055, 0.14, 0.86, 0.16)
        axis.text(0.075, 0.25, team, color=INK, fontsize=13, weight="bold")
        if members:
            axis.text(0.075, 0.21, "  |  ".join(members), color=INK, fontsize=7.5)
        axis.text(0.075, 0.17, university, color=MUTED, fontsize=9)
        axis.text(0.895, 0.25, "CONTROLLED PROOF OF CONCEPT", color=TEAL, fontsize=8, ha="right", weight="bold")
        pdf.savefig(figure, facecolor=NAVY)
        plt.close(figure)

        figure, axis = setup_slide("Project objective", "The API is the attack surface", 2, draft)
        wrapped(
            axis,
            0.055,
            0.78,
            "Government AI teams expose proprietary classifiers through prediction APIs. A black-box attacker can collect input-output pairs and train a different model that reproduces the victim's behavior without seeing its weights or training data.",
            82,
            color=INK,
            fontsize=11,
            va="top",
            linespacing=1.45,
        )
        draw_arrow_flow(
            axis,
            [
                ("1. Query", "Submit selected or manipulated images"),
                ("2. Collect", "Record labels and confidence values"),
                ("3. Train", "Use API answers as surrogate labels"),
                ("4. Replace", "Imitate the protected model's behavior"),
            ],
            0.45,
        )
        panel(axis, 0.055, 0.14, 0.42, 0.21)
        axis.text(0.075, 0.30, "WHO DEPLOYS IT", color=TEAL, fontsize=8, weight="bold")
        wrapped(axis, 0.075, 0.255, "Government AI-platform and security-operations teams protecting valuable inference services.", 47, color=INK, fontsize=9.5, va="top")
        panel(axis, 0.50, 0.14, 0.415, 0.21)
        axis.text(0.52, 0.30, "WHAT IT REPLACES", color=TEAL, fontsize=8, weight="bold")
        wrapped(axis, 0.52, 0.255, "Manual log review and rate-only controls that cannot explain model-aware extraction behavior.", 47, color=INK, fontsize=9.5, va="top")
        pdf.savefig(figure, facecolor=NAVY)
        plt.close(figure)

        figure, axis = setup_slide("Proposed solution", "Stateful evidence, graduated response", 3, draft)
        draw_arrow_flow(
            axis,
            [
                ("FastAPI", "Validated image requests and API identity"),
                ("Victim CNN", "Label, confidence, margin, embedding"),
                ("Monitor", "Per-key rolling 50-query evidence"),
                ("Policy", "Allow, observe, throttle, block"),
            ],
            0.61,
        )
        axis.text(0.055, 0.52, "FIVE EXPLAINABLE SIGNALS", color=TEAL, fontsize=8.5, weight="bold")
        signals = [
            ("RATE", "Harvesting velocity"),
            ("DIVERSITY", "Embedding exploration"),
            ("SEQUENCE", "Structured perturbations"),
            ("BOUNDARY", "Low-margin probing"),
            ("COVERAGE", "Systematic output discovery"),
        ]
        for index, (heading, detail) in enumerate(signals):
            x = 0.055 + index * 0.178
            panel(axis, x, 0.34, 0.16, 0.13)
            axis.text(x + 0.012, 0.42, heading, color=GOLD, fontsize=8, weight="bold")
            axis.text(x + 0.012, 0.375, detail, color=MUTED, fontsize=7.5)
        panel(axis, 0.055, 0.13, 0.86, 0.14)
        axis.text(0.075, 0.215, "INNOVATION", color=TEAL, fontsize=8, weight="bold")
        wrapped(
            axis,
            0.075,
            0.18,
            "The Information Acquisition Budget combines novelty and boundary value as an operational leakage proxy. Enforcement requires persistent, simultaneous signals calibrated only from benign reference traffic.",
            115,
            color=INK,
            fontsize=9,
            va="top",
        )
        pdf.savefig(figure, facecolor=NAVY)
        plt.close(figure)

        figure, axis = setup_slide("Solution validation", "An actual extraction attack, not synthetic alert labels", 4, draft)
        items = [
            ("40,000", "victim training images"),
            ("3", "independent seeds"),
            ("5,000", "queries per campaign"),
            ("50", "query monitoring window"),
        ]
        for index, (value, label) in enumerate(items):
            metric_card(axis, 0.055 + index * 0.22, 0.66, 0.20, value, label)
        panel(axis, 0.055, 0.25, 0.42, 0.33)
        axis.text(0.075, 0.525, "EXPERIMENT", color=TEAL, fontsize=8, weight="bold")
        validation_lines = [
            "Compact CNN victim; different SGD surrogate",
            "Disjoint train, calibration, attack, and test sets",
            "Adaptive boundary-seeking transfer-set attack",
            "Same seeded campaign with defence off and on",
            "Fidelity measured on an untouched hidden set",
        ]
        for index, line in enumerate(validation_lines):
            axis.text(0.08, 0.475 - index * 0.052, f"- {line}", color=INK, fontsize=8.8)
        panel(axis, 0.50, 0.25, 0.415, 0.33)
        axis.text(0.52, 0.525, "CORRECTNESS CONTROLS", color=TEAL, fontsize=8, weight="bold")
        correctness_lines = [
            "Thresholds established from benign traffic only",
            "50-query calibration and monitoring windows match",
            "Complete sessions remain within one data split",
            "Mean and standard deviation reported across seeds",
            "Low-rate evasion retained as an honest residual gap",
        ]
        for index, line in enumerate(correctness_lines):
            axis.text(0.525, 0.475 - index * 0.052, f"- {line}", color=INK, fontsize=8.8)
        axis.text(0.055, 0.17, "METRICS", color=TEAL, fontsize=8, weight="bold")
        axis.text(0.13, 0.17, "accuracy  |  fidelity  |  detection  |  benign blocks  |  queries to alert  |  responses prevented", color=MUTED, fontsize=8.5)
        pdf.savefig(figure, facecolor=NAVY)
        plt.close(figure)

        figure, axis = setup_slide("Results and conclusions", "Detection reduced the useful information returned", 5, draft)
        if chart_path.exists():
            image = plt.imread(chart_path)
            axis.imshow(image, extent=(0.045, 0.60, 0.25, 0.78), aspect="auto")
        metric_card(axis, 0.64, 0.65, 0.275, format_pm(summary["victim_validation_accuracy"]), "Victim accuracy (%)", TEAL)
        metric_card(axis, 0.64, 0.48, 0.275, "3/3 and 0/6", "Attacks detected / benign blocked")
        metric_card(axis, 0.64, 0.31, 0.275, "83.45% -> 71.98%", "Mean surrogate fidelity")
        panel(axis, 0.055, 0.105, 0.86, 0.095)
        axis.text(0.075, 0.165, "CONCLUSION", color=TEAL, fontsize=8, weight="bold")
        axis.text(0.155, 0.165, "ModelSentry detected tested high-volume extraction early and reduced clone fidelity without blocking tested legitimate clients.", color=INK, fontsize=8.7)
        axis.text(0.075, 0.125, "LIMIT", color=GOLD, fontsize=8, weight="bold")
        axis.text(0.13, 0.125, "Low-rate and distributed extraction remain residual risks; 3 seeds and 6 benign clients do not establish production rates.", color=MUTED, fontsize=8.2)
        axis.text(0.64, 0.245, f"Repository: {repo_url}", color=MUTED, fontsize=7.5)
        axis.text(0.64, 0.215, f"Demo: {video_url}", color=MUTED, fontsize=7.5)
        pdf.savefig(figure, facecolor=NAVY)
        plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the historical Baseline V1 PDF")
    parser.add_argument("--team", default="TEAM DETAILS TO BE ADDED")
    parser.add_argument("--members", nargs="*", default=[])
    parser.add_argument("--university", default="UNIVERSITY TO BE ADDED")
    parser.add_argument("--repo-url", default="LINK TO BE ADDED")
    parser.add_argument("--video-url", default="LINK TO BE ADDED")
    args = parser.parse_args()

    summary_path = EVIDENCE / "validation_summary.json"
    metrics_path = EVIDENCE / "per_seed_metrics.csv"
    if not summary_path.exists() or not metrics_path.exists():
        raise FileNotFoundError("Corrected validation evidence is missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    frame = pd.read_csv(metrics_path)
    SUBMISSION.mkdir(parents=True, exist_ok=True)
    build_dashboard_snapshot(summary, frame, SUBMISSION / "dashboard_snapshot.png")
    destination = SUBMISSION / "ModelSentry_Submission_DRAFT.pdf"
    build_pdf(
        summary,
        frame,
        destination,
        args.team,
        args.members,
        args.university,
        args.repo_url,
        args.video_url,
    )
    print(f"Wrote {destination}")


if __name__ == "__main__":
    main()
