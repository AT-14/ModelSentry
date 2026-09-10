import argparse
import json
from pathlib import Path

import qrcode
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE, MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt
from pypdf import PdfReader, PdfWriter


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "artifacts" / "validation_corrected"
SUBMISSION = ROOT / "submission"

NAVY = "071018"
PANEL = "0D1C27"
PANEL_LIGHT = "132A38"
INK = "F7FAFC"
MUTED = "9AABB7"
GOLD = "F4B942"
TEAL = "69D4C5"
RED = "EF6A6A"
LINE = "294453"

SLIDE_W = 13.333
SLIDE_H = 7.5

TEAM = "Team TSA"
MEMBERS = (
    "Abdallah Abu Zaid",
    "Nahyan Alali",
    "Mahmoud Kassem",
    "Zayed Almarzooqi",
    "Rashed Alnuaimi",
)
UNIVERSITY = "United Arab Emirates University"
REPOSITORY = "https://github.com/AT-14/ModelSentry"


def rgb(value: str) -> RGBColor:
    return RGBColor.from_string(value)


def add_text(
    slide,
    text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    size: float,
    color: str = INK,
    bold: bool = False,
    font: str = "Aptos",
    align=PP_ALIGN.LEFT,
    valign=MSO_ANCHOR.TOP,
    margin: float = 0.0,
    hyperlink: str | None = None,
):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(height))
    frame = box.text_frame
    frame.clear()
    frame.word_wrap = True
    frame.margin_left = Inches(margin)
    frame.margin_right = Inches(margin)
    frame.margin_top = Inches(margin)
    frame.margin_bottom = Inches(margin)
    frame.vertical_anchor = valign
    paragraph = frame.paragraphs[0]
    paragraph.alignment = align
    paragraph.space_after = Pt(0)
    run = paragraph.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    if hyperlink:
        run.hyperlink.address = hyperlink
    return box


def add_panel(slide, x: float, y: float, width: float, height: float, fill: str = PANEL):
    shape = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
        Inches(x),
        Inches(y),
        Inches(width),
        Inches(height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(fill)
    shape.line.color.rgb = rgb(LINE)
    shape.line.width = Pt(1)
    shape.adjustments[0] = 0.08
    return shape


def add_metric(slide, x: float, y: float, width: float, value: str, label: str, accent: str = GOLD):
    add_panel(slide, x, y, width, 1.03)
    add_text(slide, value, x + 0.16, y + 0.17, width - 0.30, 0.40, 22, accent, True, "Aptos Display")
    add_text(slide, label.upper(), x + 0.16, y + 0.66, width - 0.30, 0.22, 8, MUTED, True)


def add_base(slide, kicker: str, title: str, page: int, draft: bool) -> None:
    background = slide.background
    background.fill.solid()
    background.fill.fore_color.rgb = rgb(NAVY)
    add_text(slide, kicker.upper(), 0.55, 0.25, 7.0, 0.25, 8.5, TEAL, True)
    if draft:
        add_text(slide, "DRAFT | VIDEO LINK PENDING", 9.0, 0.25, 3.75, 0.25, 8, RED, True, align=PP_ALIGN.RIGHT)
    add_text(slide, title, 0.55, 0.64, 12.1, 0.64, 25, INK, True, "Aptos Display")
    line = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT,
        Inches(0.55),
        Inches(7.15),
        Inches(12.75),
        Inches(7.15),
    )
    line.line.color.rgb = rgb(LINE)
    line.line.width = Pt(0.8)
    add_text(slide, "SCHOOL OF CYBER DEFENCE 2026", 0.55, 7.2, 4.0, 0.18, 6.5, MUTED)
    add_text(slide, f"MODELSENTRY  |  {page}/5", 10.0, 7.2, 2.75, 0.18, 6.5, MUTED, align=PP_ALIGN.RIGHT)


def add_flow(slide, items: tuple[tuple[str, str], ...], y: float) -> None:
    x_positions = (0.55, 3.72, 6.89, 10.06)
    for index, ((heading, detail), x) in enumerate(zip(items, x_positions)):
        add_panel(slide, x, y, 2.35, 1.2)
        add_text(slide, heading, x + 0.17, y + 0.18, 2.0, 0.26, 11, INK, True)
        add_text(slide, detail, x + 0.17, y + 0.56, 2.0, 0.48, 8, MUTED)
        if index < 3:
            arrow = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT,
                Inches(x + 2.45),
                Inches(y + 0.60),
                Inches(x_positions[index + 1] - 0.10),
                Inches(y + 0.60),
            )
            arrow.line.color.rgb = rgb(GOLD)
            arrow.line.width = Pt(1.8)
            arrow.line.end_arrowhead = True


def set_notes(slide, text: str) -> None:
    slide.notes_slide.notes_text_frame.text = text


def make_qr(url: str, destination: Path) -> None:
    image = qrcode.make(url)
    image.save(destination)


def add_slide_one(prs: Presentation, summary: dict, draft: bool) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, "National cybersecurity competition", "ModelSentry", 1, draft)
    add_text(slide, "Detect model theft before the copy becomes useful.", 0.55, 1.38, 10.8, 0.5, 20, GOLD, False, "Aptos Display")
    add_text(
        slide,
        "A stateful API-security layer that identifies systematic model learning, explains the evidence, and limits information exposure before a surrogate becomes valuable.",
        0.55,
        1.98,
        11.7,
        0.75,
        11,
        INK,
    )
    add_metric(slide, 0.55, 3.05, 2.85, "3/3", "Extraction campaigns detected")
    add_metric(slide, 3.57, 3.05, 2.85, "0/6", "Legitimate clients blocked", TEAL)
    add_metric(slide, 6.59, 3.05, 2.85, f"{summary['fidelity_reduction']['mean']:.1%}", "Mean fidelity reduction")
    add_metric(slide, 9.61, 3.05, 2.85, f"{summary['responses_prevented']['mean']:.0f}", "Responses prevented", TEAL)
    add_panel(slide, 0.55, 4.55, 11.91, 1.65)
    add_text(slide, TEAM, 0.78, 4.82, 2.0, 0.32, 14, INK, True)
    add_text(slide, "  |  ".join(MEMBERS), 0.78, 5.28, 10.9, 0.28, 8.5, INK)
    add_text(slide, UNIVERSITY, 0.78, 5.70, 6.0, 0.30, 10, MUTED)
    add_text(slide, "CONTROLLED PROOF OF CONCEPT", 9.2, 4.85, 2.95, 0.25, 8, TEAL, True, align=PP_ALIGN.RIGHT)
    set_notes(
        slide,
        "[Timing: 0:00-0:35]\nOpen with the risk: a public prediction API can become a labeling service for a competitor. ModelSentry watches behavior rather than isolated requests. State the controlled result: all three tested extraction campaigns were detected, no tested legitimate client was blocked, and the attack received roughly 4,655 fewer useful responses. Transition: first, show how API access becomes model theft.",
    )


def add_slide_two(prs: Presentation, draft: bool) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, "Project objective", "A prediction API can become a free training set", 2, draft)
    add_text(
        slide,
        "A black-box attacker needs neither the weights nor the original training data. They need enough carefully selected input-output pairs to train a substitute.",
        0.55,
        1.37,
        11.8,
        0.62,
        11,
        INK,
    )
    add_flow(
        slide,
        (
            ("1. Query", "Submit selected or manipulated images"),
            ("2. Collect", "Record labels and confidence values"),
            ("3. Train", "Use API answers as surrogate labels"),
            ("4. Replace", "Imitate the protected model's behavior"),
        ),
        2.30,
    )
    add_panel(slide, 0.55, 4.05, 3.62, 1.65)
    add_text(slide, "OWNER", 0.77, 4.31, 2.8, 0.25, 8, TEAL, True)
    add_text(slide, "Government AI platform and security operations teams", 0.77, 4.72, 3.0, 0.66, 11, INK, True)
    add_panel(slide, 4.36, 4.05, 3.62, 1.65)
    add_text(slide, "BUSINESS RISK", 4.58, 4.31, 2.8, 0.25, 8, TEAL, True)
    add_text(slide, "IP loss, avoided API fees, and cheaper adversarial reconnaissance", 4.58, 4.72, 3.0, 0.66, 11, INK, True)
    add_panel(slide, 8.17, 4.05, 4.29, 1.65, PANEL_LIGHT)
    add_text(slide, "THE GAP", 8.39, 4.31, 2.8, 0.25, 8, GOLD, True)
    add_text(slide, "Rate limits see speed. Model theft is a sequence of information-acquisition decisions.", 8.39, 4.72, 3.65, 0.70, 11, INK, True)
    set_notes(
        slide,
        "[Timing: 0:35-1:05]\nWalk left to right through the extraction loop. The attacker queries, collects labels, trains a different model, and can eventually replace paid API access. Explain the buyer and business impact. Emphasize the design gap: rate limiting is useful but cannot characterize the information value and structure of a query sequence. Transition: ModelSentry converts that sequence into persistent evidence.",
    )


def add_slide_three(prs: Presentation, draft: bool) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, "Proposed solution", "Stateful evidence, graduated response", 3, draft)
    add_flow(
        slide,
        (
            ("FastAPI", "Validated image and API identity"),
            ("Victim CNN", "Label, confidence, margin, embedding"),
            ("50-query monitor", "Per-key rolling behavioral evidence"),
            ("Policy", "Allow, observe, throttle, block"),
        ),
        1.48,
    )
    add_text(slide, "FIVE EXPLAINABLE SIGNALS", 0.55, 3.12, 4.0, 0.25, 8.5, TEAL, True)
    signals = (
        ("RATE", "Harvesting velocity"),
        ("DIVERSITY", "Embedding exploration"),
        ("SEQUENCE", "Structured perturbations"),
        ("BOUNDARY", "Low-margin probing"),
        ("COVERAGE", "Systematic output discovery"),
    )
    for index, (heading, detail) in enumerate(signals):
        x = 0.55 + index * 2.40
        add_panel(slide, x, 3.55, 2.17, 1.08)
        add_text(slide, heading, x + 0.15, 3.75, 1.8, 0.22, 8.5, GOLD, True)
        add_text(slide, detail, x + 0.15, 4.10, 1.8, 0.30, 8, MUTED)
    add_panel(slide, 0.55, 5.03, 11.91, 1.22, PANEL_LIGHT)
    add_text(slide, "INFORMATION ACQUISITION BUDGET", 0.78, 5.31, 3.2, 0.23, 8.5, TEAL, True)
    add_text(
        slide,
        "Novelty x boundary value estimates operational leakage. Benign-calibrated percentiles and three persistent suspicious windows prevent single unusual requests from triggering mitigation.",
        4.15,
        5.25,
        7.85,
        0.65,
        10.5,
        INK,
    )
    set_notes(
        slide,
        "[Timing: 1:05-1:50]\nFollow one request through the system. The victim model returns the normal prediction while exposing internal telemetry to the monitor. Explain the five signal families in plain language. The key innovation is an operational acquisition budget: novelty multiplied by boundary value approximates how useful each answer is to an extractor. Escalation needs multiple signals across three consecutive windows, then moves from observation to throttling and blocking. Transition: we tested this against a real surrogate-training loop.",
    )


def add_slide_four(prs: Presentation, summary: dict, chart_path: Path, draft: bool) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, "Validation and results", "Detection reduced clone fidelity by 11.47 points", 4, draft)
    add_panel(slide, 0.55, 1.40, 7.45, 4.90)
    slide.shapes.add_picture(str(chart_path), Inches(0.79), Inches(1.72), width=Inches(6.97), height=Inches(3.92))
    add_text(slide, "Same seeded adaptive extraction, defence disabled vs enabled", 0.86, 5.83, 6.8, 0.23, 8, MUTED, align=PP_ALIGN.CENTER)
    add_metric(slide, 8.28, 1.40, 4.18, "90.56% +/- 0.59", "Victim validation accuracy", TEAL)
    add_metric(slide, 8.28, 2.65, 4.18, "83.45% -> 71.98%", "Mean surrogate fidelity")
    add_metric(slide, 8.28, 3.90, 4.18, "337 +/- 184", "Queries to first alert", TEAL)
    add_metric(slide, 8.28, 5.15, 4.18, "4,655 +/- 184", "Responses prevented of 5,000")
    add_text(slide, "3 seeds  |  40,000 training images  |  8 epochs  |  disjoint calibration, attack and hidden-test partitions", 0.75, 6.53, 11.8, 0.25, 8, MUTED, align=PP_ALIGN.CENTER)
    set_notes(
        slide,
        "[Timing: 1:50-2:40]\nState the methodology before the result: three independent seeds, 40,000 victim-training images, eight epochs, disjoint partitions, and an adaptive boundary-seeking attack training a different SGD surrogate. Point to the curve: without defence, fidelity reaches 83.45 percent; with ModelSentry it ends at 71.98 percent. Alerts occur after 337 queries on average and enforcement prevents about 4,655 of 5,000 responses. All three required attacks were detected and none of six tested legitimate clients was blocked. Transition: the prototype is useful, but its limits are explicit.",
    )


def add_slide_five(prs: Presentation, dashboard_path: Path, qr_path: Path, video_url: str, draft: bool) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_base(slide, "Conclusion and deployment", "Operationally useful, honestly bounded", 5, draft)
    add_panel(slide, 0.55, 1.42, 6.15, 3.46)
    slide.shapes.add_picture(str(dashboard_path), Inches(0.74), Inches(1.63), width=Inches(5.77), height=Inches(3.24))
    add_panel(slide, 6.95, 1.42, 5.51, 3.46)
    takeaways = (
        ("01", "Explainable early warning", "Analysts see which behaviors crossed benign-calibrated percentiles."),
        ("02", "Graduated containment", "Monitor, throttle, and block reduce leakage without a binary shutdown."),
        ("03", "Known residual risk", "Patient in-domain and distributed multi-account attacks remain difficult."),
    )
    for index, (number, heading, detail) in enumerate(takeaways):
        y = 1.72 + index * 0.94
        add_text(slide, number, 7.20, y, 0.50, 0.25, 9, GOLD, True)
        add_text(slide, heading, 7.82, y - 0.02, 3.95, 0.26, 10.5, INK, True)
        add_text(slide, detail, 7.82, y + 0.32, 4.05, 0.42, 8.2, MUTED)
    add_panel(slide, 0.55, 5.18, 8.62, 1.05, PANEL_LIGHT)
    add_text(slide, "DEPLOYMENT ROADMAP", 0.78, 5.41, 2.0, 0.23, 8, TEAL, True)
    add_text(slide, "Tenant baselines  ->  cross-key linkage  ->  streaming storage  ->  drift review  ->  analyst feedback", 2.67, 5.37, 6.14, 0.42, 9.2, INK)
    add_panel(slide, 9.42, 5.18, 3.04, 1.05)
    slide.shapes.add_picture(str(qr_path), Inches(9.61), Inches(5.31), width=Inches(0.78), height=Inches(0.78))
    add_text(slide, "SOURCE CODE", 10.56, 5.35, 1.53, 0.22, 8, TEAL, True)
    add_text(slide, "github.com/AT-14/ModelSentry", 10.56, 5.65, 1.55, 0.40, 6.8, INK, hyperlink=REPOSITORY)
    video_text = "Demo video: link pending" if draft else "Demo video: open recording"
    add_text(slide, video_text, 0.74, 6.48, 5.3, 0.24, 8, RED if draft else TEAL, True, hyperlink=None if draft else video_url)
    set_notes(
        slide,
        "[Timing: 2:40-3:25]\nClose with three points. ModelSentry provides an explainable warning, limits information through graduated containment, and does not pretend that every extraction strategy is detectable. Name the main gaps: patient in-distribution and distributed attackers. Briefly give the production roadmap. Invite judges to scan the repository QR code. Finish: ModelSentry turns model extraction from an invisible billing pattern into an observable security incident.\n\n[Backup demo order]\nShow the healthy API, legitimate interactive and batch clients, the undefended fidelity curve, the identical defended campaign, alert reasons, and the aggregate result. If live services fail, use the saved dashboard snapshot and chart.",
    )


def add_pdf_links(pdf_path: Path, video_url: str, draft: bool) -> None:
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)
    if reader.metadata:
        writer.add_metadata(reader.metadata)
    writer.add_uri(4, REPOSITORY, (678, 91, 897, 167))
    if not draft:
        writer.add_uri(4, video_url, (53, 48, 435, 74))
    temporary_path = pdf_path.with_suffix(".linked.pdf")
    with temporary_path.open("wb") as handle:
        writer.write(handle)
    temporary_path.replace(pdf_path)


def export_pdf(presentation_path: Path, pdf_path: Path, video_url: str, draft: bool) -> None:
    import win32com.client

    application = win32com.client.DispatchEx("PowerPoint.Application")
    application.Visible = True
    presentation = None
    try:
        presentation = application.Presentations.Open(
            str(presentation_path.resolve()),
            ReadOnly=True,
            Untitled=False,
            WithWindow=False,
        )
        presentation.SaveAs(str(pdf_path.resolve()), 32)
    finally:
        if presentation is not None:
            presentation.Close()
        application.Quit()
    add_pdf_links(pdf_path, video_url, draft)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ModelSentry PPTX and matching PDF")
    parser.add_argument("--video-url", default="VIDEO LINK PENDING")
    parser.add_argument("--skip-pdf", action="store_true")
    args = parser.parse_args()
    draft = args.video_url == "VIDEO LINK PENDING"

    summary_path = EVIDENCE / "validation_summary.json"
    chart_path = EVIDENCE / "multi_seed_fidelity.png"
    dashboard_path = SUBMISSION / "dashboard_snapshot.png"
    if not all(path.exists() for path in (summary_path, chart_path, dashboard_path)):
        raise FileNotFoundError("Corrected evidence or dashboard snapshot is missing")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    SUBMISSION.mkdir(parents=True, exist_ok=True)
    qr_path = SUBMISSION / "repository_qr.png"
    make_qr(REPOSITORY, qr_path)

    presentation = Presentation()
    presentation.slide_width = Inches(SLIDE_W)
    presentation.slide_height = Inches(SLIDE_H)
    presentation.core_properties.title = "ModelSentry: Detect Model Theft Before the Copy Becomes Useful"
    presentation.core_properties.subject = "School of Cyber Defence 2026"
    presentation.core_properties.author = f"{TEAM}: {', '.join(MEMBERS)}"
    presentation.core_properties.keywords = "model extraction, API security, cybersecurity"

    add_slide_one(presentation, summary, draft)
    add_slide_two(presentation, draft)
    add_slide_three(presentation, draft)
    add_slide_four(presentation, summary, chart_path, draft)
    add_slide_five(presentation, dashboard_path, qr_path, args.video_url, draft)

    suffix = "_DRAFT" if draft else ""
    presentation_path = SUBMISSION / f"ModelSentry_Presentation{suffix}.pptx"
    pdf_path = SUBMISSION / f"ModelSentry_Submission{suffix}.pdf"
    presentation.save(presentation_path)
    print(f"Wrote {presentation_path}")
    if not args.skip_pdf:
        export_pdf(presentation_path, pdf_path, args.video_url, draft)
        print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
