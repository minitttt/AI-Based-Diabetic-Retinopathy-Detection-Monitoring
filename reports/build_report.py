from __future__ import annotations

import json
import re
import shutil
import subprocess
import textwrap
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports"
ASSET_DIR = REPORT_DIR / "assets"
REPORT_MD = REPORT_DIR / "RetinaScan_AI_Minor_Project_Report.md"
REPORT_DOCX = REPORT_DIR / "RetinaScan_AI_Minor_Project_Report.docx"
REFERENCE_DOCX = REPORT_DIR / "reference.docx"

IDENTITY = {
    "student": "Minit Kumar",
    "enrollment": "07215611623",
    "supervisor": "Supervisor name to be confirmed",
    "supervisor_designation": "Designation to be confirmed",
    "hod": "Head of Department name to be confirmed",
    "principal": "Principal name to be confirmed",
    "submission_date": "November / December 2026",
    "spine_year": "2026–27",
    "repository": "https://github.com/minitttt/AI-Based-Diabetic-Retinopathy-Detection-Monitoring",
}

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"w": W_NS, "r": R_NS}
ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)


def w(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def r(tag: str) -> str:
    return f"{{{R_NS}}}{tag}"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def font(size: int = 20, bold: bool = False, italic: bool = False) -> Any:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str, body: str,
             fill: str = "#edf4fb", outline: str = "#2f5f8f", title_fill: str = "#153b5c") -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=outline, width=3)
    draw.text((x1 + 18, y1 + 14), title, font=font(24, bold=True), fill=title_fill)
    lines = textwrap.wrap(body, width=max(20, int((x2 - x1 - 36) / 12)))
    y = y1 + 52
    for line in lines:
        draw.text((x1 + 18, y), line, font=font(17), fill="#213547")
        y += 24


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], fill: str = "#477ca9") -> None:
    draw.line((*start, *end), fill=fill, width=5)
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length = max(1.0, (dx * dx + dy * dy) ** 0.5)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    size = 16
    points = [
        (x2, y2),
        (x2 - ux * size + px * size * 0.55, y2 - uy * size + py * size * 0.55),
        (x2 - ux * size - px * size * 0.55, y2 - uy * size - py * size * 0.55),
    ]
    draw.polygon(points, fill=fill)


def title_on_canvas(draw: ImageDraw.ImageDraw, title: str, subtitle: str, width: int) -> None:
    draw.text((48, 32), title, font=font(34, bold=True), fill="#153b5c")
    draw.text((48, 78), subtitle, font=font(17), fill="#5c7185")
    draw.line((48, 112, width - 48, 112), fill="#c3d4e3", width=3)


def create_diagrams() -> None:
    ensure_dir(ASSET_DIR)

    canvas = Image.new("RGB", (1800, 1050), "white")
    draw = ImageDraw.Draw(canvas)
    title_on_canvas(draw, "RetinaScan AI — System Architecture", "End-to-end path from fundus image upload to monitoring and report export", canvas.width)
    draw_box(draw, (70, 220, 390, 470), "Web Frontend", "Vanilla HTML, CSS and JavaScript\nUpload, results, history, exports", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    draw_box(draw, (520, 180, 870, 510), "FastAPI Service", "CORS, validation, patient API\nPrediction orchestration\nReport endpoints", fill="#edf4fb", outline="#477ca9")
    draw_box(draw, (1000, 160, 1370, 360), "Preprocessing", "Decode and validate image\nBlack-border crop\nBen Graham enhancement\nCLAHE + normalization", fill="#f7f1e6", outline="#c28a3c", title_fill="#7a4e16")
    draw_box(draw, (1000, 440, 1370, 640), "EfficientNet-B4-NS", "380×380 tensor\n1792 feature vector\n5-class softmax\nGrad-CAM attention", fill="#f3edf7", outline="#81559f", title_fill="#5a3470")
    draw_box(draw, (1480, 140, 1730, 350), "SQLite", "Patient profiles\nScan history\nOrdinal progression", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    draw_box(draw, (1480, 440, 1730, 650), "Artifacts", "PDF report\nCSV/JSON exports\nPreview + attention image\n24-hour temporary retention", fill="#f7f1e6", outline="#c28a3c", title_fill="#7a4e16")
    draw_box(draw, (530, 700, 850, 930), "Monitoring UI", "Patient selection\nTimeline\nModel-observed trend", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    draw_box(draw, (1010, 750, 1360, 930), "Deployment", "Docker / Uvicorn\nLocal or hosted API\nEnvironment configuration", fill="#edf4fb", outline="#477ca9")
    arrow(draw, (390, 345), (520, 345))
    arrow(draw, (870, 300), (1000, 260))
    arrow(draw, (1185, 360), (1185, 440))
    arrow(draw, (1370, 260), (1480, 245))
    arrow(draw, (1370, 540), (1480, 545))
    arrow(draw, (690, 510), (690, 700))
    arrow(draw, (1000, 600), (850, 800))
    arrow(draw, (850, 820), (1010, 820))
    canvas.save(ASSET_DIR / "system_architecture.png")

    canvas = Image.new("RGB", (1800, 1000), "white")
    draw = ImageDraw.Draw(canvas)
    title_on_canvas(draw, "Primary Use Cases", "Actors and user-visible actions supported by the project", canvas.width)
    draw.ellipse((70, 380, 270, 580), fill="#eaf5f5", outline="#3d8e8a", width=4)
    draw.text((112, 445), "Clinician", font=font(24, bold=True), fill="#155c5a")
    draw.ellipse((70, 700, 270, 900), fill="#edf4fb", outline="#477ca9", width=4)
    draw.text((118, 765), "Researcher", font=font(24, bold=True), fill="#244f78")
    use_cases = [
        (400, 180, 820, 290, "Analyze fundus image", "Upload a retinal image and receive a five-class screening signal."),
        (400, 330, 820, 440, "Review explanation", "Inspect confidence values, quality score and attention preview."),
        (400, 480, 820, 590, "Maintain patient history", "Create a profile and attach a saved scan to a timeline."),
        (400, 630, 820, 740, "Export report", "Download PDF, CSV or JSON artifact for research review."),
        (990, 250, 1440, 360, "Inspect model metrics", "Review architecture, training curves, AUC and QWK."),
        (990, 420, 1440, 530, "Evaluate predictions", "Run held-out test evaluation and confusion-matrix analysis."),
        (990, 590, 1440, 700, "Deploy service", "Start the FastAPI backend and serve the static frontend."),
    ]
    for x1, y1, x2, y2, t, b in use_cases:
        draw_box(draw, (x1, y1, x2, y2), t, b, fill="#f7f9fb", outline="#8ca8bd")
    for target_y in (235, 385, 535, 685):
        arrow(draw, (270, 480), (400, target_y))
    for target_y in (305, 475, 645):
        arrow(draw, (270, 800), (990, target_y), fill="#6c8ca6")
    canvas.save(ASSET_DIR / "use_cases.png")

    canvas = Image.new("RGB", (1900, 1000), "white")
    draw = ImageDraw.Draw(canvas)
    title_on_canvas(draw, "Level-1 Data Flow Diagram", "Information movement through the prediction and monitoring service", canvas.width)
    draw_box(draw, (70, 370, 340, 600), "User", "Image + optional\npatient metadata", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    draw_box(draw, (500, 250, 900, 720), "FastAPI /predict", "Multipart upload\nInput validation\nInference call\nPersistence decision", fill="#edf4fb", outline="#477ca9")
    draw_box(draw, (1100, 120, 1500, 340), "Image Pipeline", "Decode → fundus check\nCrop → illumination correction\nCLAHE → tensor", fill="#f7f1e6", outline="#c28a3c", title_fill="#7a4e16")
    draw_box(draw, (1100, 430, 1500, 650), "Model Output", "Grade, confidence\nclass probabilities\nattention map", fill="#f3edf7", outline="#81559f", title_fill="#5a3470")
    draw_box(draw, (1100, 740, 1500, 930), "Report Service", "JSON metadata\nCSV row\nPDF + image files", fill="#f7f1e6", outline="#c28a3c", title_fill="#7a4e16")
    draw_box(draw, (1600, 220, 1830, 410), "SQLite", "Patient + scans", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    draw_box(draw, (1600, 570, 1830, 760), "Frontend", "Results, history\nand downloads", fill="#edf4fb", outline="#477ca9")
    arrow(draw, (340, 485), (500, 485))
    arrow(draw, (900, 390), (1100, 230))
    arrow(draw, (1300, 340), (1300, 430))
    arrow(draw, (1300, 650), (1300, 740))
    arrow(draw, (1500, 250), (1600, 315))
    arrow(draw, (1500, 520), (1600, 665))
    arrow(draw, (1500, 835), (1600, 700))
    canvas.save(ASSET_DIR / "data_flow.png")

    canvas = Image.new("RGB", (1800, 1100), "white")
    draw = ImageDraw.Draw(canvas)
    title_on_canvas(draw, "Entity Relationship Model", "Logical data model for patient profiles and saved scan history", canvas.width)
    draw_box(draw, (160, 280, 710, 760), "patients", "patient_id (PK)\nname\nage\ngender\ndiabetes_type\ncreated_at", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    draw_box(draw, (1080, 200, 1640, 860), "scans", "scan_id (PK)\npatient_id (FK)\nscan_date\neye\nimage_path\npredicted_grade\npredicted_label\nconfidence\nconf_no_dr … conf_pdr\nnotes\ncreated_at", fill="#edf4fb", outline="#477ca9")
    arrow(draw, (710, 505), (1080, 505), fill="#3d8e8a")
    draw.text((760, 440), "one patient", font=font(21, bold=True), fill="#155c5a")
    draw.text((780, 565), "many scans", font=font(21, bold=True), fill="#244f78")
    canvas.save(ASSET_DIR / "er_diagram.png")

    canvas = Image.new("RGB", (1800, 1000), "white")
    draw = ImageDraw.Draw(canvas)
    title_on_canvas(draw, "Deployment Architecture", "Local startup and containerized serving model", canvas.width)
    draw_box(draw, (80, 280, 430, 650), "Browser", "Static frontend\nlocalhost:3000\nor hosted site", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    draw_box(draw, (650, 200, 1080, 730), "Uvicorn / FastAPI", "Port 8001 locally\nPort 7860 in container\nCORS + REST endpoints", fill="#edf4fb", outline="#477ca9")
    draw_box(draw, (1300, 120, 1710, 360), "Model runtime", "PyTorch + timm\nEfficientNet-B4-NS\nCheckpoint artifact", fill="#f3edf7", outline="#81559f", title_fill="#5a3470")
    draw_box(draw, (1300, 480, 1710, 760), "Runtime storage", "SQLite database\nuploads/\nreport_artifacts/\nretention cleanup", fill="#f7f1e6", outline="#c28a3c", title_fill="#7a4e16")
    arrow(draw, (430, 465), (650, 465))
    arrow(draw, (1080, 350), (1300, 240))
    arrow(draw, (1080, 580), (1300, 620))
    draw_box(draw, (540, 820, 1200, 930), "Docker image", "Python 3.10 slim · dependencies · backend entry point · exposed service port", fill="#f7f9fb", outline="#8ca8bd")
    arrow(draw, (860, 730), (860, 820), fill="#6c8ca6")
    canvas.save(ASSET_DIR / "deployment_architecture.png")

    canvas = Image.new("RGB", (1800, 950), "white")
    draw = ImageDraw.Draw(canvas)
    title_on_canvas(draw, "Report Artifact Lifecycle", "Creation, access and expiry of temporary research artifacts", canvas.width)
    stages = [
        (80, "1. Create", "Prediction response\ncreates UUID artifact directory"),
        (480, "2. Generate", "Preview, attention image,\nJSON, CSV and PDF"),
        (880, "3. Serve", "Relative URLs exposed\nthrough fixed endpoints"),
        (1280, "4. Expire", "TTL check rejects old files\nand cleanup removes directory"),
    ]
    for x, title, body in stages:
        draw_box(draw, (x, 330, x + 300, 610), title, body, fill="#edf4fb", outline="#477ca9")
    for x in (380, 780, 1180):
        arrow(draw, (x, 470), (x + 100, 470))
    draw_box(draw, (520, 720, 1260, 850), "Safety properties", "Validated report IDs · fixed filenames · no filesystem paths in API · 24-hour default retention", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    canvas.save(ASSET_DIR / "report_lifecycle.png")

    canvas = Image.new("RGB", (1900, 1150), "white")
    draw = ImageDraw.Draw(canvas)
    title_on_canvas(draw, "Work Breakdown Structure", "Development work packages for the RetinaScan AI minor project", canvas.width)
    draw_box(draw, (650, 150, 1250, 300), "RetinaScan AI Project", "AI-based diabetic retinopathy detection and monitoring", fill="#edf4fb", outline="#477ca9")
    branches = [
        (100, 430, "1. Data", "Dataset acquisition\nEDA\nStratified split"),
        (500, 430, "2. Model", "Preprocessing\nTransfer learning\nTraining and tuning"),
        (900, 430, "3. Evaluation", "Metrics\nConfusion matrix\nGrad-CAM"),
        (1300, 430, "4. Application", "FastAPI\nSQLite monitoring\nFrontend"),
        (700, 790, "5. Validation", "Testing\nReports\nDocumentation"),
    ]
    for x, y, title, body in branches:
        draw_box(draw, (x, y, x + 300, y + 210), title, body, fill="#eef7f6" if x in (100, 1300, 700) else "#f7f1e6", outline="#3d8e8a" if x in (100, 1300, 700) else "#c28a3c", title_fill="#155c5a" if x in (100, 1300, 700) else "#7a4e16")
        if y == 430:
            arrow(draw, (950, 300), (x + 150, y), fill="#6c8ca6")
        else:
            arrow(draw, (950, 640), (x + 150, y), fill="#6c8ca6")
    draw_box(draw, (100, 850, 440, 1030), "Deliverable", "Validated research prototype", fill="#f7f9fb", outline="#8ca8bd")
    draw_box(draw, (1460, 850, 1800, 1030), "Outcome", "Reproducible report and deployable demo", fill="#f7f9fb", outline="#8ca8bd")
    arrow(draw, (250, 640), (250, 850), fill="#6c8ca6")
    arrow(draw, (1500, 640), (1630, 850), fill="#6c8ca6")
    canvas.save(ASSET_DIR / "work_breakdown_structure.png")

    canvas = Image.new("RGB", (1900, 1050), "white")
    draw = ImageDraw.Draw(canvas)
    title_on_canvas(draw, "Activity Diagram — Scan and Report Workflow", "User-visible sequence for quick analysis or saved patient scan", canvas.width)
    steps = [
        (680, 150, 1220, 235, "Start", "User opens Diagnose view"),
        (620, 300, 1280, 405, "Enter scan context", "Select patient or choose quick analysis\nSet date, eye and notes"),
        (620, 470, 1280, 575, "Upload image", "Drag and drop or browse for fundus image"),
        (620, 640, 1280, 745, "Validate and preprocess", "Decode → fundus check → enhancement → tensor"),
        (620, 810, 1280, 915, "Run inference", "Predict grade, confidence, probabilities and attention"),
    ]
    for x1, y1, x2, y2, title, body in steps:
        draw_box(draw, (x1, y1, x2, y2), title, body, fill="#edf4fb", outline="#477ca9")
    arrow(draw, (950, 235), (950, 300))
    arrow(draw, (950, 405), (950, 470))
    arrow(draw, (950, 575), (950, 640))
    arrow(draw, (950, 745), (950, 810))
    draw_box(draw, (120, 470, 470, 650), "Decision", "Patient selected?", fill="#f7f1e6", outline="#c28a3c", title_fill="#7a4e16")
    arrow(draw, (620, 525), (470, 525), fill="#c28a3c")
    draw_box(draw, (120, 760, 470, 935), "Quick analysis", "Return result without database scan row", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    draw_box(draw, (1390, 760, 1780, 935), "Saved analysis", "Write scan and image, create report artifact", fill="#eef7f6", outline="#3d8e8a", title_fill="#155c5a")
    arrow(draw, (1280, 860), (1390, 860), fill="#3d8e8a")
    arrow(draw, (120, 610), (120, 760), fill="#c28a3c")
    draw_box(draw, (680, 970, 1220, 1040), "End", "Render results, exports and review disclaimer", fill="#f3edf7", outline="#81559f", title_fill="#5a3470")
    arrow(draw, (950, 915), (950, 970), fill="#81559f")
    canvas.save(ASSET_DIR / "activity_diagram.png")


def create_ui_screenshots() -> None:
    """Capture the three static frontend views when Chrome is available."""

    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ]
    chrome = next((candidate for candidate in chrome_candidates if candidate and Path(candidate).exists()), None)
    if not chrome:
        return
    frontend_html = ROOT / "deployment/frontend/index.html"
    source = frontend_html.read_text(encoding="utf-8")
    source = source.replace("styles.css?v=20261021-3", (ROOT / "deployment/frontend/styles.css").as_uri())
    source = source.replace("app.js?v=20261021-3", (ROOT / "deployment/frontend/app.js").as_uri())
    temp_html = REPORT_DIR / ".screenshot_source.html"
    for view, filename in [("diagnose", "ui_diagnose.png"), ("history", "ui_history.png"), ("about", "ui_about.png")]:
        injected = source.replace("</body>", f"<script>setTimeout(()=>switchPage('{view}'), 80);</script></body>")
        temp_html.write_text(injected, encoding="utf-8")
        subprocess.run([
            chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
            "--allow-file-access-from-files", "--hide-scrollbars",
            "--window-size=1440,1000", f"--screenshot={ASSET_DIR / filename}",
            temp_html.as_uri(),
        ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    temp_html.unlink(missing_ok=True)

    # A rendered image of the generated PDF is useful as a Chapter 5 artifact.
    pdf_candidates = sorted((ROOT / "deployment/backend/report_artifacts").glob("*/report.pdf"))
    if pdf_candidates:
        subprocess.run(["sips", "-s", "format", "png", str(pdf_candidates[0]), "--out", str(ASSET_DIR / "sample_pdf_report.png")], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def raw_page_break() -> str:
    return '```{=openxml}\n<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n```'


def raw_field(instruction: str, placeholder: str = "") -> str:
    escaped = instruction.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    result = f'<w:r><w:t xml:space="preserve">{placeholder}</w:t></w:r>' if placeholder else ""
    return (
        "```{=openxml}\n"
        f"<w:p><w:r><w:fldChar w:fldCharType=\"begin\" w:dirty=\"true\"/></w:r>"
        f"<w:r><w:instrText xml:space=\"preserve\"> {escaped} </w:instrText></w:r>"
        "<w:r><w:fldChar w:fldCharType=\"separate\"/></w:r>"
        f"{result}"
        "<w:r><w:fldChar w:fldCharType=\"end\"/></w:r></w:p>\n"
        "```"
    )


def figure(path: str, caption: str, width_hint: str = "") -> str:
    suffix = f" ({width_hint})" if width_hint else ""
    return f"![{caption}{suffix}](assets/{path})"


def bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def source_excerpt(relative_path: str, start: int, end: int, language: str = "python") -> str:
    path = ROOT / relative_path
    lines = path.read_text(encoding="utf-8").splitlines()
    selected = lines[max(0, start - 1):end]
    numbered = "\n".join(f"{index:04d} | {line}" for index, line in enumerate(selected, start=start))
    return f"**Listing {relative_path}, lines {start}–{end}**\n\n```{language}\n{numbered}\n```"


def table(caption: str, headers: list[str], rows: list[list[str]]) -> str:
    caption_line = f"Table: {caption}\n\n"
    head = "| " + " | ".join(headers) + " |\n"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |\n"
    body = "".join("| " + " | ".join(str(cell) for cell in row) + " |\n" for row in rows)
    return caption_line + head + sep + body


def page(heading: str, body: str) -> str:
    cleaned = "\n".join(line.strip() if line.strip() else "" for line in textwrap.dedent(body).splitlines()).strip()
    return f"{heading}\n\n{cleaned}\n\n{raw_page_break()}\n\n"


def load_metrics() -> tuple[dict, dict, list[dict]]:
    summary = json.loads((ROOT / "logs/metrics_summary.json").read_text())
    evaluation = json.loads((ROOT / "logs/evaluation/metrics.json").read_text())
    history = []
    for line in (ROOT / "logs/training_history.csv").read_text().splitlines()[1:]:
        values = line.split(",")
        history.append({
            "epoch": len(history) + 1,
            "train_loss": float(values[0]),
            "val_loss": float(values[1]),
            "train_kappa": float(values[2]),
            "val_kappa": float(values[3]),
            "train_acc": float(values[4]),
            "val_acc": float(values[5]),
            "lr": float(values[6]),
        })
    return summary, evaluation, history


def build_markdown() -> None:
    summary, evaluation, history = load_metrics()
    pages: list[str] = []

    pages.append(page(
        "# AI-BASED DIABETIC RETINOPATHY DETECTION & MONITORING",
        f"""
        **Minor Project – Dissertation (AIML-451)**

        **Submitted in partial fulfilment of the requirements for the award of the degree of**

        **Bachelor of Technology in Artificial Intelligence and Machine Learning**

        **Submitted by**

        **{IDENTITY['student']}**  
        **{IDENTITY['enrollment']}**

        **Under the supervision of**

        **{IDENTITY['supervisor']}**  
        **{IDENTITY['supervisor_designation']}**

        **Department of Artificial Intelligence and Machine Learning**  
        **Dr. Akhilesh Das Gupta Institute of Professional Studies**  
        FC-26, Shastri Park, New Delhi

        **{IDENTITY['submission_date']}**
        """
    ))
    pages.append(page(
        "# DECLARATION",
        f"""
        This is to certify that the material embodied in this Minor Project – Dissertation titled **“AI-Based Diabetic Retinopathy Detection & Monitoring”** is based on my original work. It is being submitted in partial fulfilment of the requirements for the award of the degree of Bachelor of Technology in Artificial Intelligence and Machine Learning.

        It is further certified that this Minor Project – Dissertation work has not been submitted in full or in part to this university or any other university for the award of any other degree or diploma. My indebtedness to other works has been duly acknowledged at the relevant places.

        **Name of the Student:** {IDENTITY['student']}  
        **Enrollment No.:** {IDENTITY['enrollment']}

        <br><br>

        **Signature of the Student:** ________________________________  
        **Date:** ____________________
        f"""
    ))
    pages.append(page(
        "# CERTIFICATE",
        f"""
        This is to certify that the work embodied in this Minor Project – Dissertation titled **“AI-Based Diabetic Retinopathy Detection & Monitoring”**, submitted in partial fulfilment of the requirements for the award of the degree of Bachelor of Technology in Artificial Intelligence and Machine Learning, is original and has been carried out by **{IDENTITY['student']} ({IDENTITY['enrollment']})** under my supervision and guidance.

        It is further certified that, to the best of my knowledge and belief, this Minor Project – Dissertation work has not been submitted in full or in part to this university or any other university for the award of any other degree or diploma.

        <br><br>

        **Faculty Supervisor**  
        Name: {IDENTITY['supervisor']}  
        Designation: {IDENTITY['supervisor_designation']}  
        Signature: ________________________________

        <br><br>

        **Head of Department**  
        Name: {IDENTITY['hod']}  
        Department: Artificial Intelligence and Machine Learning  
        Signature: ________________________________
        """
    ))
    pages.append(page(
        "# ACKNOWLEDGEMENT",
        f"""
        I express my sincere gratitude to my faculty supervisor, **{IDENTITY['supervisor']}**, for guidance, encouragement and technical feedback throughout this project. The discussions on machine learning methodology, model evaluation and software engineering helped shape the work from a notebook experiment into an integrated prototype.

        I am grateful to the **{IDENTITY['principal']}**, the **{IDENTITY['hod']}**, the Department of Artificial Intelligence and Machine Learning and **Dr. Akhilesh Das Gupta Institute of Professional Studies** for providing the academic environment, computing resources and institutional support required to complete the project.

        I thank the maintainers of PyTorch, torchvision, timm, FastAPI, OpenCV, Pillow, ReportLab and the other open-source libraries used in the implementation. I acknowledge the APTOS 2019 Blindness Detection dataset and the clinicians and annotators whose work made the supervised learning task possible.

        Finally, I thank my classmates, friends and family for their patience and encouragement during dataset preparation, model experimentation, debugging, documentation and report preparation.

        <br><br>

        **{IDENTITY['student']}**
        """
    ))
    pages.append(page(
        "# ABSTRACT",
        f"""
        Diabetic retinopathy is a progressive retinal complication of diabetes and a major cause of preventable visual impairment. Screening programs rely on retinal fundus photographs, but manual grading is time-consuming, requires specialist availability and is affected by inter-grader variability. This project presents **RetinaScan AI**, an end-to-end prototype for five-class diabetic retinopathy severity grading using a fine-tuned EfficientNet-B4 model with NoisyStudent pretraining.

        The system uses the APTOS 2019 Blindness Detection dataset containing 3,662 labelled training images. Images are processed through black-border removal, Ben Graham illumination correction, contrast enhancement using CLAHE, resizing to 380 × 380 pixels and ImageNet normalisation. A two-stage transfer-learning strategy first trains the classifier head and then fine-tunes the complete network. Focal loss, inverse-frequency class weighting and augmentation are used to reduce the effect of class imbalance. The final model is evaluated on a stratified held-out test set of 550 images using accuracy, Quadratic Weighted Kappa (QWK), per-class precision/recall/F1 and one-vs-rest ROC-AUC.

        The recorded test results are **{summary['test_accuracy'] * 100:.1f}% accuracy**, **{summary['test_qwk']:.3f} QWK** and **{summary['macro_auc']:.3f} macro AUC**. The No-DR class reaches an AUC of **{summary['per_class_auc']['No DR']:.3f}**, while the lowest per-class AUC is observed for Severe DR at **{summary['per_class_auc']['Severe']:.3f}**. The prototype also computes Grad-CAM or an explicitly labelled attention fallback, exposes predictions through FastAPI, stores optional patient histories in SQLite and creates PDF, CSV and JSON research artifacts.

        The work demonstrates how model development, explainability, backend engineering and longitudinal monitoring can be combined into a reproducible screening-support workflow. The implementation repository is available at **{IDENTITY['repository']}**. It remains a research prototype and requires external validation, calibration, security hardening and clinical governance before any clinical use.

        **Keywords:** diabetic retinopathy, fundus photography, EfficientNet-B4, transfer learning, CLAHE, Grad-CAM, FastAPI, patient monitoring, medical AI.
        """
    ))
    pages.append(page("# TABLE OF CONTENTS", raw_field('TOC \\t "Heading1,1,Heading2,2,Heading3,3" \\h \\z \\u')))
    pages.append(page("# LIST OF FIGURES", raw_field('TOC \\t "ImageCaption,1" \\h \\z \\u')))
    pages.append(page("# LIST OF TABLES", raw_field('TOC \\t "TableCaption,1" \\h \\z \\u')))

    # Chapter 1.
    pages.append(page(
        "# CHAPTER 1: INTRODUCTION",
        """
        ## 1.1 Background and motivation

        Diabetic retinopathy (DR) is a retinal complication associated with diabetes mellitus. It develops when long-term metabolic changes damage the small blood vessels supplying the retina. Early pathological signs may be subtle, and the condition may progress before a person notices a significant change in vision. International clinical grading guidance organises observable disease severity into ordered levels that can be applied to fundus photographs [2]. Automated analysis of retinal photographs has been studied as a way to expand screening capacity and prioritise specialist review [1], [3], [4].

        Manual grading is valuable but resource-intensive. Each image must be reviewed for signs such as microaneurysms, retinal haemorrhages, exudates, venous beading and neovascularisation. The task is also ordinal: an error between adjacent grades is not equivalent to an error between No DR and Proliferative DR. This makes the design of the evaluation metric and user interface important.

        RetinaScan AI was developed as an academic prototype that explores this workflow from data preparation through deployment. It is not designed to replace a clinical reader. Its purpose is to demonstrate how a model can be trained, evaluated, explained and integrated into a small monitoring application while preserving a clear disclaimer about the limits of automated screening.
        """
    ))
    pages.append(page(
        "## 1.2 Clinical grading context",
        """
        The project follows the five-level International Clinical Diabetic Retinopathy scale used in the dataset: Grade 0 — No DR; Grade 1 — Mild; Grade 2 — Moderate; Grade 3 — Severe; and Grade 4 — Proliferative [2]. The classes reflect increasing disease severity, but the boundaries between adjacent categories can be difficult even for trained graders.

        A machine-learning system should therefore provide more than a single class label. RetinaScan AI returns the predicted grade, the probability distribution over all five grades, an image-quality score and an attention visualisation. These outputs are intended to support review and analysis. The probability vector reveals uncertainty, while the attention image provides a visual clue about the regions that influenced the model. Neither output is a clinical measurement or a substitute for an examination.

        The report adopts a cautious interpretation of the model. A high confidence score means that the model's softmax distribution is concentrated; it does not mean that the prediction is calibrated or clinically correct. Similarly, Grad-CAM is treated as an explanation aid rather than as lesion segmentation.
        """
    ))
    pages.append(page(
        "## 1.3 Why an end-to-end prototype is needed",
        """
        A notebook-only experiment can demonstrate model accuracy but does not show how a user would upload an image, receive a result, revisit a patient record or obtain a report. The project therefore combines four layers: a training and evaluation pipeline, an inference module, a FastAPI service and a browser frontend.

        This integration exposes practical issues that are not visible in a standalone model. Uploaded files must be decoded safely. Invalid or non-fundus images should be rejected before inference. Optional patient metadata must be normalised before it is persisted. Generated reports must not expose local filesystem paths. Frontend actions must handle network failures and incomplete metadata. These concerns are part of the project because an AI system is only useful when its model, interface and operational behaviour are coherent.

        The result is a small but complete screening-support prototype that can run locally using the included startup script and can be packaged for container deployment.
        """
    ))
    pages.append(page(
        "## 1.4 Project vision and contributions",
        f"""
        The project vision is to provide a transparent and extensible foundation for AI-assisted diabetic retinopathy screening research. The principal contributions are:

        {bullets([
            "A five-class EfficientNet-B4-NS transfer-learning model with 380 × 380 input processing.",
            "A reproducible preprocessing path combining black-border cropping, Ben Graham illumination correction, CLAHE and ImageNet normalisation.",
            "A held-out evaluation process reporting accuracy, QWK, class-wise metrics, ROC-AUC and bootstrap confidence intervals.",
            "Model-attention visualisation with an explicit label for Grad-CAM and fallback methods.",
            "FastAPI endpoints for inference, patients, scan history and temporary PDF/CSV/JSON artifacts.",
            "A browser interface for diagnosis, patient monitoring, research exports and model information.",
        ])}

        The current evaluation log contains a test set of {evaluation['test_size']} images, a QWK of {evaluation['qwk']:.3f} and a macro AUC of {evaluation['macro_auc']:.3f}. These results motivate the prototype but do not establish clinical readiness.
        """
    ))
    pages.append(page(
        "## 1.5 Organisation of the report",
        """
        Chapter 1 introduces the clinical and technical context. Chapter 2 defines the problem, objectives, scope and stakeholders. Chapter 3 converts the project idea into a software requirements specification and evaluates feasibility. Chapter 4 explains the architecture, data model, interfaces and deployment design.

        Chapter 5 documents implementation, beginning with the APTOS dataset and preprocessing and continuing through model training, inference, database persistence, frontend behaviour, report exports, screenshots and source-code excerpts. Chapter 6 describes testing and includes the recorded results and discussion. Chapter 7 presents the summary and conclusion. Chapter 8 records limitations and future work. The final pages provide bibliography and appendix material.

        This structure follows the development-based project format supplied with the university dissertation guidelines while retaining research-oriented evaluation evidence.
        """
    ))
    pages.append(page(
        "## 1.6 Introduction close",
        """
        Diabetic retinopathy screening is an appropriate application for a responsible computer-vision prototype because retinal images contain clinically meaningful visual patterns and the task has an ordinal label structure. The project addresses the problem at both model and system levels. It uses transfer learning to make the image-classification problem tractable, and it wraps the model in a service that can be inspected, tested and used through a browser.

        The most important design principle introduced in this chapter is that the system should be treated as screening support rather than autonomous diagnosis. This principle influences the disclaimer, the report layout, the wording used in the frontend and the interpretation of confidence and attention maps. The next chapter translates the motivation into a precise problem statement and a set of measurable objectives.
        """
    ))

    # Chapter 2.
    pages.append(page(
        "# CHAPTER 2: PROBLEM STATEMENT",
        """
        ## 2.1 Problem definition

        The project addresses the following problem: **given a colour retinal fundus photograph, predict its diabetic retinopathy severity grade on a five-level ordinal scale and make the result available through an interpretable, browser-accessible monitoring workflow.**

        The input may vary in brightness, contrast, field-of-view coverage and image quality. The dataset is imbalanced, with No DR cases forming the largest class and Severe DR forming a small minority. The system must therefore combine preprocessing and training decisions that are appropriate for the data distribution. It must also distinguish between a quick analysis that is not saved and a saved scan associated with a patient profile.

        The problem has two linked outputs. The first is the model output: class, confidence and probability vector. The second is the software output: a validated API response, optional persistence, an attention image and downloadable research artifacts. Success requires both outputs to be correct and usable.
        """
    ))
    pages.append(page(
        "## 2.2 Objectives",
        """
        Table 2.1 summarises the project objectives and the corresponding measurable outputs.

        """ + table(
            "Table 2.1: Project objectives and measurable outputs",
            ["Objective", "Expected output", "Evidence in project"],
            [
                ["Train a five-class DR grader", "Model that returns grade and probabilities", "EfficientNet-B4-NS checkpoint and inference module"],
                ["Reduce image variability", "Consistent model input", "Cropping, illumination correction, CLAHE and normalisation"],
                ["Evaluate ordinal performance", "Accuracy, QWK, AUC and class metrics", "Held-out test evaluation logs"],
                ["Provide model transparency", "Attention visualisation and disclaimer", "Grad-CAM / fallback report fields"],
                ["Support longitudinal review", "Patient profiles and scan timeline", "SQLite schema and history UI"],
                ["Enable research export", "Portable PDF, CSV and JSON artifacts", "Report-generation module and endpoints"],
            ],
        ) + """

        The objectives intentionally include system engineering because an isolated model score does not answer how a result will be inspected, stored, exported or revisited.
        """
    ))
    pages.append(page(
        "## 2.3 Scope of the project",
        """
        The scope includes the following activities:

        """ + bullets([
            "Preparation and analysis of the APTOS 2019 labelled fundus-image dataset.",
            "Implementation of a transfer-learning classifier and a two-stage fine-tuning workflow.",
            "Evaluation on a stratified held-out test set with visual diagnostics.",
            "Implementation of a CPU-compatible inference path with optional attention generation.",
            "Development of a FastAPI backend and static browser frontend.",
            "Implementation of patient profiles, saved scans, ordinal progression and temporary report artifacts.",
            "Documentation of limitations, safety boundaries and future production requirements.",
        ]) + """

        The scope does not include regulatory certification, prospective clinical trials, automatic lesion segmentation, ophthalmologist replacement, integration with hospital information systems or a production-grade identity and access-management platform. These exclusions are important because they define what can and cannot be inferred from the current prototype.
        """
    ))
    pages.append(page(
        "## 2.4 Stakeholders and user roles",
        """
        The primary stakeholder is a clinician or trained screening operator who wants to review a fundus image with an AI-generated screening signal. The interface is designed to keep the original image, predicted grade, probability breakdown, quality score and attention preview visible together. A clinician can optionally select a patient profile and save the scan to a timeline.

        The second stakeholder is a researcher or student who needs to inspect model behaviour. Research exports are therefore separated into PDF, CSV and JSON formats. The PDF is designed for human review, CSV supports tabular analysis, and JSON preserves structured metadata such as schema version, model version, image-quality score, explanation method and expiration timestamp.

        The project supervisor and evaluator are additional stakeholders. They need evidence that the data was split correctly, that the model was evaluated on held-out data, that requirements were tested and that the interface communicates its limitations. The report and test logs are written to support that review.
        """
    ))
    pages.append(page(
        "## 2.5 Project requirements",
        """
        The project requirements are grouped into model, application and governance requirements. The model must accept a valid fundus photograph and return five-class probabilities. The application must validate input, provide a stable response contract and keep report resources behind generated identifiers. The monitoring layer must preserve scan ordering and calculate an ordinal baseline-to-latest trend.

        The governance requirements are equally important. The system must display a clinical disclaimer, must not present attention maps as lesion segmentation, and must clearly distinguish saved records from quick analyses. It must also avoid claiming that the model is a medical device or that confidence equals certainty.

        A project requirement is considered satisfied only when it is visible in the user flow or supported by a reproducible check. For example, the presence of a download button alone is insufficient; the endpoint must produce a readable artifact and the frontend must handle missing or expired metadata.
        """
    ))
    pages.append(page(
        "## 2.6 Requirements conclusion",
        """
        The project is defined as an ordinal image-classification and monitoring problem rather than only as a neural-network training problem. The required outcome is an end-to-end workflow that is useful for research review: a user uploads a retinal image, the service validates it, the model returns a prediction, the result can be explained and exported, and an optional patient history can be maintained.

        The explicit scope boundary protects the project from overclaiming. The prototype demonstrates feasibility and provides a foundation for validation, but it does not make clinical decisions. The following chapter converts these requirements into functional and non-functional specifications and assesses the feasibility of the proposed solution.
        """
    ))

    # Chapter 3.
    pages.append(page(
        "# CHAPTER 3: ANALYSIS",
        """
        ## 3.1 Software requirements specification

        The software requirements specification describes the behaviour expected from the integrated prototype. The service has three operating modes. In quick-analysis mode, an image is uploaded without a patient identifier and the result is returned without adding a scan to the monitoring database. In saved-scan mode, a valid patient identifier is supplied and the image, metadata and prediction are recorded. In research mode, the user downloads structured artifacts for offline review. The service is implemented with FastAPI and Pydantic validation [21], while the browser interface uses standard HTML, CSS and JavaScript.

        The specification also treats failure as part of the normal interface. A malformed image must return a clear client error. An unknown patient must return a not-found response rather than silently creating a new record. A missing report artifact must be presented as unavailable or expired. These behaviours reduce ambiguity and make the prototype easier to evaluate.

        The current implementation uses FastAPI route functions, Pydantic validation for patient creation, SQLite persistence and a file-backed reporting module. The frontend uses a single-page layout with three views: Diagnose, History and About.
        """
    ))
    pages.append(page(
        "## 3.2 Literature review and related work",
        """
        Research on automated DR grading spans clinical decision rules, binary referable-DR detection, multi-class severity grading, ordinal modelling and explainable deep learning. Early clinical systems demonstrated that retinal photographs could be analysed automatically for referable disease [1], while later multi-ethnic validation studies showed the importance of evaluating models across different populations and imaging settings [3].

        Deep convolutional networks have become the dominant approach for fundus-image classification. Transfer learning with modern backbones improves representation quality when labelled medical data is limited. EfficientNet provides a parameter-efficient scaling strategy [5], and NoisyStudent pretraining improves the quality of transferred visual features [6]. Earlier DR systems used convolutional models and image-mining strategies to improve screening performance [14], [15], while later systems combined image-quality assessment, lesion detection and grading [16]. For imbalanced datasets, focal loss focuses optimisation on hard examples [7]. Because DR grades are ordered, ordinal-regression methods such as rank-consistent objectives are relevant alternatives to a flat five-class softmax [17].

        Public datasets support reproducible research but do not remove the need for external validation. APTOS 2019 provides the labelled data used here [10]. IDRiD includes pixel-level lesion annotations and grading labels [11], while Messidor provides an independent retinal-image benchmark [12]. Broader ophthalmic deep-learning reviews also emphasise technical, clinical and governance considerations [18]. These datasets can support future cross-dataset validation. The current project uses only APTOS and therefore reports its results as an internal held-out evaluation.

        Table 3.1 compares representative prior work with the present prototype. The comparison is qualitative because datasets, label definitions, splits and operating points differ. Direct numerical ranking across papers would be misleading.

        """ + table(
            "Table 3.1: Related work comparison",
            ["Work", "Task / data", "Main contribution", "Relevance to this project"],
            [
                ["Gulshan et al. [1]", "Referable DR from fundus photographs", "Large-scale deep-learning screening validation", "Motivates automated screening workflow"],
                ["Wilkinson et al. [2]", "Clinical DR severity scale", "Defines ordered clinical severity categories", "Supports five-level label interpretation"],
                ["Ting et al. [3]", "Multi-disease retinal screening", "External and multi-ethnic evaluation", "Motivates future external validation"],
                ["Tan and Le [5]", "ImageNet classification", "Efficient compound model scaling", "Backbone family used here"],
                ["Lin et al. [7]", "Dense object classification", "Focal loss for hard and imbalanced examples", "Loss design used here"],
                ["Cao et al. [17]", "Ordinal neural prediction", "Rank-consistent ordinal regression", "Future alternative to flat softmax"],
                ["RetinaScan AI", "APTOS 2019 five-class grading", "Model, API, monitoring and report exports", "Integrated development prototype"],
            ],
        ) + """

        The gap addressed by this project is integration. Many studies focus on model performance, while a usable screening prototype also needs input validation, quality information, explanations, persistence, reports and a clear boundary between research output and clinical diagnosis.
        """
    ))
    pages.append(page(
        "## 3.3 Functional requirements",
        """
        Table 3.2 lists the main functional requirements.

        """ + table(
            "Table 3.2: Functional requirements",
            ["ID", "Requirement", "Acceptance condition"],
            [
                ["FR-01", "Upload image", "User can select or drag a fundus image into the Diagnose view."],
                ["FR-02", "Validate image", "Unreadable or visually invalid input is rejected with an actionable message."],
                ["FR-03", "Run inference", "Service returns grade, label, confidence and five probabilities."],
                ["FR-04", "Show explanation", "Results view shows attention preview or explains why it is unavailable."],
                ["FR-05", "Create patient", "User can create a profile with generated or supplied patient ID."],
                ["FR-06", "Save scan", "Selected patient, date, eye and notes are persisted with the prediction."],
                ["FR-07", "View history", "User can retrieve scans in chronological order and see trend summary."],
                ["FR-08", "Export result", "PDF, CSV and JSON artifacts can be downloaded from the result panel."],
                ["FR-09", "Expose metrics", "About view presents model architecture and evaluation evidence."],
            ],
        ) + """

        Each requirement is intentionally phrased in terms of observable behaviour. This permits black-box testing without requiring a reviewer to inspect internal Python objects.
        """
    ))
    pages.append(page(
        "## 3.4 Non-functional requirements",
        """
        Table 3.3 records non-functional requirements that shape implementation quality.

        """ + table(
            "Table 3.3: Non-functional requirements",
            ["ID", "Quality attribute", "Project interpretation"],
            [
                ["NFR-01", "Usability", "Result, confidence, quality and disclaimer should be visible together."],
                ["NFR-02", "Portability", "The backend should run from the repository without depending on the current working directory."],
                ["NFR-03", "Reproducibility", "Dataset split, metrics, model configuration and report schema should be documented."],
                ["NFR-04", "Safety", "Invalid inputs and missing artifacts must fail clearly; no diagnosis claim is permitted."],
                ["NFR-05", "Maintainability", "Backend concerns are separated into inference, utilities, database and reporting modules."],
                ["NFR-06", "Performance", "CPU inference should remain practical for a local demonstration."],
                ["NFR-07", "Data minimisation", "API responses expose generated filenames and relative URLs, not local filesystem paths."],
            ],
        ) + """

        These requirements are not all fully satisfied for public production deployment. In particular, authentication, rate limiting, durable object storage and external validation remain future work. The distinction between implemented prototype behaviour and production requirements is maintained throughout this report.
        """
    ))
    pages.append(page(
        "## 3.5 Feasibility study",
        """
        **Technical feasibility.** The selected stack is technically feasible because PyTorch and timm support the EfficientNet-B4-NS architecture, OpenCV and Pillow support image handling, FastAPI provides a small asynchronous web layer and SQLite is sufficient for a local monitoring demonstration. The project already contains state-dict, TorchScript and ONNX export paths, which creates options for later optimisation.

        **Operational feasibility.** The browser workflow is understandable to a screening operator: select patient or quick analysis, upload image, review the result and optionally export. The project includes a one-command local startup script that launches the backend and static frontend on documented ports.

        **Economic feasibility.** The prototype uses open-source software and can run on commodity hardware, although training EfficientNet-B4 is more practical with GPU access. The cost of a production deployment would be driven by compute, storage, security and clinical validation rather than by software licensing.

        **Schedule feasibility.** The work can be divided into data preparation, modelling, evaluation, service implementation, frontend integration, testing and documentation. This staged structure matches the project artefacts present in the repository.
        """
    ))
    pages.append(page(
        "## 3.6 Risk analysis",
        """
        The most important risks are model bias, class imbalance, distribution shift, invalid image input, persistence of sensitive data and overinterpretation of confidence. The project mitigates some risks using stratified splitting, class-aware training, image validation, an image-quality score, a clinical disclaimer and explicit reporting of per-class metrics.

        Other risks remain open. The APTOS dataset is not a complete representation of all cameras, populations and clinical settings. A high AUC on a held-out split does not guarantee performance on another hospital's images. SQLite and local file storage are convenient for a prototype but are not automatically durable or access-controlled in a hosted environment. Attention maps can be visually persuasive even when they are not causally faithful.

        The risk analysis therefore treats the prototype as a research instrument. Its main value is to make assumptions and outputs inspectable so that future validation can be performed systematically.
        """
    ))
    pages.append(page(
        "## 3.7 Tools, technologies and platform",
        """
        Table 3.4 summarises the technology stack.

        """ + table(
            "Table 3.4: Technology stack",
            ["Layer", "Technology", "Role"],
            [
                ["Model training", "PyTorch, torchvision, timm", "Neural-network definition, optimisation and pretrained backbone"],
                ["Image processing", "OpenCV, Pillow, NumPy", "Decode, crop, enhancement, quality score and artifact rendering"],
                ["Evaluation", "scikit-learn, pandas, matplotlib, seaborn", "Metrics, splits, charts and confusion matrices"],
                ["Backend", "FastAPI, Uvicorn, Pydantic", "REST API, validation and service lifecycle"],
                ["Persistence", "SQLite", "Patient profiles and scan history"],
                ["Frontend", "HTML, CSS, JavaScript", "Upload, result, history and about views"],
                ["Reporting", "ReportLab, CSV and JSON", "Professional PDF and research exports"],
                ["Deployment", "Docker, Python HTTP server", "Container and local startup paths"],
            ],
        ) + """

        The project deliberately avoids a heavyweight frontend framework because the workflow is small and the static frontend is easy to serve. The backend is modular enough that the same model and database functions can later be placed behind a stronger deployment platform.
        """
    ))
    pages.append(page(
        "## 3.8 Use case analysis",
        figure("use_cases.png", "Figure 3.1: Primary use cases") + "\n\n" +
        "The use-case diagram separates clinician-facing actions from researcher and deployment actions. A clinician begins with an image and may end with a reviewed report or a saved patient-history entry. A researcher may inspect metrics, reproduce evaluation or export structured predictions. The system does not include an autonomous treatment or diagnosis use case; that omission is intentional."
    ))
    pages.append(page(
        "## 3.9 Data-flow analysis",
        figure("data_flow.png", "Figure 3.2: Level-1 data flow diagram") + "\n\n" +
        "The data-flow analysis shows that the prediction request is the central transaction. It carries an image and optional metadata into validation and preprocessing, then receives model output and report metadata. A saved request additionally writes a scan row and generated image filename to the monitoring store. The report service writes temporary artifacts and exposes only fixed endpoint paths.\n\nThe analysis confirms that the planned architecture is feasible and that the main boundary conditions are visible: invalid images, unknown patients, report expiration, storage failures and model availability. The next chapter translates this analysis into an explicit architecture and data design."
    ))

    # Chapter 4.
    pages.append(page(
        "# CHAPTER 4: DESIGN AND ARCHITECTURE",
        figure("system_architecture.png", "Figure 4.1: RetinaScan AI system architecture") + "\n\n" +
        "The system is organised as a pipeline with clear responsibilities. The browser handles user interaction and presentation. FastAPI coordinates requests and owns validation at the application boundary. The preprocessing module turns uploaded bytes into a model-ready array and computes the technical image-quality score. The inference module owns the neural network and explanation path. SQLite provides local patient and scan persistence, while the reporting module produces temporary artifacts. This separation supports testing and future replacement of individual components."
    ))
    pages.append(page(
        "## 4.1 Structure chart and work breakdown structure",
        figure("work_breakdown_structure.png", "Figure 4.2: Work breakdown structure") + "\n\n" +
        "The work breakdown structure divides the project into data, modelling, evaluation, application and validation work packages. This decomposition follows the actual development sequence: dataset preparation creates the input for model development; evaluation verifies the model; application engineering turns the model into a user workflow; and validation joins the evidence into a report and deployment package. The structure also makes responsibilities and deliverables visible for project supervision."
    ))
    pages.append(page(
        "## 4.2 Flow chart and activity diagram",
        figure("activity_diagram.png", "Figure 4.3: Activity diagram for scan and report workflow") + "\n\n" +
        "The activity diagram shows the user path from scan-context entry to report generation. The decision branch distinguishes quick analysis from a saved patient scan. Both paths share image validation, preprocessing and model inference, but only the saved path writes a patient-history record and associated image. The final result is rendered in the frontend with the clinical review boundary visible."
    ))
    pages.append(page(
        "## 4.3 Module decomposition",
        """
        Table 4.1 describes the principal software modules.

        """ + table(
            "Table 4.1: Main software modules",
            ["Module", "Primary responsibility", "Important interface"],
            [
                ["inference.py", "Model construction, checkpoint loading, prediction and attention", "load_model(), predict_with_explanation()"],
                ["utils.py", "Decode, fundus validation, preprocessing and quality score", "decode_image(), load_and_preprocess()"],
                ["db.py", "SQLite schema, migrations, patient and scan queries", "create_patient(), insert_scan(), progression()"],
                ["reporting.py", "Temporary artifact generation and safe retrieval", "create_report_artifact(), get_report_file()"],
                ["main.py", "FastAPI lifecycle, routes, request orchestration", "POST /predict, /patients, /reports"],
                ["app.js", "Frontend state, navigation, fetch calls and rendering", "API_BASE, report and history flows"],
            ],
        ) + """

        The module boundaries are intentionally thin. The route function coordinates the transaction, but image transformation remains in utilities, model behaviour remains in inference and file formats remain in reporting. This helps prevent a future change in PDF layout from changing model logic.
        """
    ))
    pages.append(page(
        "## 4.4 Data model",
        figure("er_diagram.png", "Figure 4.4: Entity relationship model") + "\n\n" +
        "The logical schema uses a one-to-many relationship: one patient may have zero or more saved scans. A patient row contains identity and demographic context supplied by the user. A scan row contains date, eye, image basename, predicted grade, label, confidence, class probabilities and notes. The schema deliberately stores a generated image filename rather than an absolute path in the API response.\n\nThe database module applies an additive migration for the eye field so that historical rows remain valid. An index over patient, scan date and scan identifier supports chronological retrieval. The progression function compares the first and latest ordinal predictions and reports stable, improving or worsening model-observed direction."
    ))
    pages.append(page(
        "## 4.5 API design",
        """
        Table 4.2 lists the core API endpoints.

        """ + table(
            "Table 4.2: Core API endpoints",
            ["Method", "Endpoint", "Purpose"],
            [
                ["GET", "/", "Basic service response"],
                ["POST", "/predict", "Validate image, run prediction and create report"],
                ["GET", "/patients", "List patient profiles and latest summaries"],
                ["POST", "/patients", "Create patient profile"],
                ["GET", "/patients/{id}", "Return patient, scans and progression"],
                ["GET", "/patients/{id}/scans", "Return chronological scans"],
                ["GET", "/reports/{id}", "Return report metadata"],
                ["GET", "/reports/{id}/pdf", "Download PDF artifact"],
                ["GET", "/reports/{id}/csv", "Download CSV artifact"],
                ["GET", "/reports/{id}/json", "Download JSON artifact"],
                ["GET", "/reports/{id}/image", "Serve preview image"],
                ["GET", "/reports/{id}/attention", "Serve attention image"],
            ],
        ) + """

        The /predict response contains both a nested report object and compatibility fields such as report_id and report_urls. This supports the current frontend while keeping the structured report metadata accessible to external research scripts.
        """
    ))
    pages.append(page(
        "## 4.6 Inference data path",
        "The inference path starts with raw bytes. OpenCV decodes the image into RGB format, a fundus-specific heuristic checks dimensions, saturation, contrast and dark border coverage, and the preprocessing pipeline creates the 380 × 380 array. The model applies ImageNet normalisation and produces logits. Softmax converts logits into probabilities, and the maximum probability determines the displayed grade.\n\nThe explanation path retains the final spatial feature map when available and computes Grad-CAM for the selected class. If the feature interface is unavailable, the implementation uses a labelled activation, input-gradient or input-intensity fallback. This preserves report availability without misrepresenting the explanation method."
    ))
    pages.append(page(
        "## 4.7 Frontend design",
        """
        The frontend is a single static document with three primary views. The Diagnose view contains scan context fields, a drag-and-drop upload zone, animated analysis state, prediction card, probability bars, attention preview and export actions. The History view provides patient search, profile creation, saved-scan timeline and progression summary. The About view presents the model architecture, training table, evaluation metrics, confusion matrix and explanatory text.

        Accessibility considerations include labelled controls, keyboard focus for the upload zone, a skip link, live status regions for asynchronous actions and descriptive alternative text for images. The interface avoids using colour as the only signal by pairing severity colours with text labels.

        Frontend state is kept explicit: the current file, last prediction, last report, scan context and patient state are tracked separately. This reduces accidental reuse of a previous report when a new scan is submitted.
        """
    ))
    pages.append(page(
        "## 4.8 Deployment and privacy design",
        figure("deployment_architecture.png", "Figure 4.5: Deployment architecture") + "\n\n" +
        "The local deployment uses start.sh to launch Uvicorn on port 8001 and Python's static HTTP server on port 3000. The Dockerfile uses a Python 3.10 slim base image, installs OpenCV-compatible libraries and exposes port 7860 for container hosting. The frontend currently uses a local API base for this workspace; a production deployment should supply the API origin through environment-specific configuration. The implementation uses open-source libraries including PyTorch [13], OpenCV [20], FastAPI [21] and ReportLab [22].\n\nThe privacy design is intentionally conservative in wording but remains prototype-level in implementation. Reports and uploads are stored locally and should not receive real patient identifiers in a public demo. Authentication, authorisation, encrypted storage, retention policy enforcement and audit logging are required before clinical deployment."
    ))
    pages.append(page(
        "## 4.9 Temporary artifact design",
        figure("report_lifecycle.png", "Figure 4.6: Report artifact lifecycle") + "\n\n" +
        "Each analysis receives a random 32-character hexadecimal identifier. The reporting module creates a directory containing report.json, report.csv, report.pdf, preview.jpg and attention.jpg. Public URLs expose only the generated identifier and fixed artifact names. This design avoids accepting arbitrary filesystem paths from the browser.\n\nThe architecture is therefore intentionally modular: the image model can be replaced without changing patient queries, and the report renderer can be redesigned without changing inference. The next chapter explains how the design was implemented and how the recorded model evidence was produced."
    ))

    # Chapter 5.
    pages.append(page(
        "# CHAPTER 5: IMPLEMENTATION",
        """
        ## 5.1 Dataset and exploratory analysis

        The project uses the APTOS 2019 Blindness Detection dataset released through the Kaggle competition resource [10]. The training CSV contains 3,662 records with an image identifier and a diagnosis label from 0 to 4. The image collection contains substantial variation in illumination, camera characteristics, field-of-view coverage and focus quality. These variations make preprocessing and data-quality checks important.

        The project notebook records the following class distribution: No DR — 1,805 images (49.3%); Mild — 370 images (10.1%); Moderate — 999 images (27.3%); Severe — 193 images (5.3%); and Proliferative — 295 images (8.1%). The minority classes are clinically important but provide fewer examples for learning. The training design therefore uses stratification, weighted sampling and focal loss.

        The exploratory analysis includes representative images by grade and a class-distribution chart. It is used to identify the circular retinal field, black borders, variable illumination and visual differences between labels before model training.
        """
    ))
    pages.append(page(
        "## 5.2 Dataset distribution and split",
        figure("class_distribution.png", "Figure 5.1: APTOS 2019 class distribution") + "\n\n" +
        table(
            "Table 5.1: Dataset split",
            ["Split", "Images", "Purpose"],
            [
                ["Training", "2,563", "Optimise parameters"],
                ["Validation", "549", "Select and monitor training behaviour"],
                ["Test", "550", "Final held-out evaluation"],
                ["Total", "3,662", "APTOS labelled training set"],
            ],
        ) + "\n\n" +
        "The split is stratified and uses a fixed random seed. The first split separates 70% of the records for training and 30% for temporary validation/test data; the latter is divided equally into validation and test sets. The resulting label proportions remain close to the original distribution, which makes the held-out metrics easier to interpret. The test split is not used for model selection."
    ))
    pages.append(page(
        "## 5.3 Representative retinal images",
        figure("sample_images.png", "Figure 5.2: Sample retinal fundus images by DR grade") + "\n\n" +
        "The sample grid illustrates why a purely pixel-level view is insufficient. Images from the same grade can differ in brightness, crop, camera artefact and lesion visibility. Some pathological signs are small relative to the full image, while the black circular border contains no useful retinal information. The project therefore combines spatial standardisation with contrast and illumination processing.\n\nThe figure should be interpreted as a qualitative dataset view, not as a diagnostic atlas. Labels originate from the dataset annotations and do not replace a clinical description of each image."
    ))
    pages.append(page(
        "## 5.4 Preprocessing pipeline",
        figure("preprocessing_comparison.png", "Figure 5.3: Preprocessing comparison") + "\n\n" +
        "The preprocessing implementation follows four main operations. First, black borders are cropped using a grayscale threshold so the retinal field occupies more of the input. Second, Ben Graham-style Gaussian subtraction reduces uneven illumination and increases local structure. Third, CLAHE is applied channel-wise to improve local contrast; the method was introduced as a contrast-limited extension of adaptive histogram equalisation [19]. Finally, the image is resized to 380 × 380 and converted to a tensor using ImageNet mean and standard deviation.\n\nThe order is important. Cropping before resizing avoids using border pixels to determine scale, while contrast processing before normalisation ensures that the network receives a consistent numeric range. The same validation preprocessing is used by the inference service so that deployment input matches the training pipeline."
    ))
    pages.append(page(
        "## 5.5 Augmentation and image-quality score",
        """
        Training augmentation is designed to expose the model to plausible acquisition variation. The notebook records horizontal and vertical flips, 90-degree rotation, shift/scale/rotation, brightness and contrast changes, hue/saturation/value changes, Gaussian noise and normalisation. Augmentation is applied only to the training path; validation and test images use deterministic transforms.

        The deployed service also computes a technical quality score from exposure, contrast, Laplacian sharpness, colour saturation and non-background coverage. The score is scaled to 0–100 and labelled Good, Fair or Needs review. It is explicitly documented as a screening-oriented technical estimate rather than a clinical diagnosis. The quality value is included in the report so that a reviewer can identify low-quality inputs when interpreting a prediction.

        The current quality heuristic is intentionally lightweight. It should be calibrated against expert quality grades before being used to reject or triage images in a clinical workflow.
        """
    ))
    pages.append(page(
        "## 5.6 Model architecture",
        """
        The classifier uses timm's `tf_efficientnet_b4_ns` backbone with the classification head removed and global average pooling enabled. EfficientNet introduced compound model scaling to balance depth, width and resolution [5]. The NoisyStudent pretraining strategy provides the backbone used by this variant [6]. EfficientNet-B4 provides a compound-scaled convolutional representation and 1792 pooled features. A custom head applies dropout with p=0.4, a linear projection from 1792 to 512, GELU activation, BatchNorm1d, dropout with p=0.2 and a final linear layer producing five logits.

        The model is suitable for this project because it offers a strong transfer-learning starting point while remaining more compact than large conventional CNNs. The input size of 380 × 380 is higher than the 224-pixel input used by many small image models, which helps preserve fine retinal detail. The trade-off is increased CPU latency and memory use.

        The deployment inference module constructs the same architecture with `pretrained=False` and then loads the saved state dictionary. This makes checkpoint availability a critical deployment dependency.

        """ + table(
            "Table 5.2: Model configuration",
            ["Parameter", "Value"],
            [
                ["Backbone", "tf_efficientnet_b4_ns"],
                ["Input resolution", "380 × 380 pixels"],
                ["Feature dimension", "1792"],
                ["Classifier head", "Dropout 0.4 → Linear 1792→512 → GELU → BatchNorm → Dropout 0.2 → Linear 512→5"],
                ["Output classes", "No DR, Mild, Moderate, Severe, Proliferative"],
                ["Optimiser", "AdamW"],
                ["Loss", "Focal cross-entropy, γ=2, inverse-frequency class weights"],
                ["Batch size", "16"],
                ["Learning rates", "Phase A head: 1×10⁻³; Phase B backbone: 1×10⁻⁴; Phase B head: 1×10⁻³"],
                ["Weight decay", "1×10⁻⁴"],
                ["Gradient clipping", "Maximum norm 1.0"],
                ["Primary training metric", "Quadratic Weighted Kappa"],
            ],
        ) + """
        """
    ))
    pages.append(page(
        "## 5.7 Training strategy",
        """
        Training is implemented in two phases. Phase A freezes the EfficientNet backbone and trains only the custom classifier head for five configured epochs. This allows the new output layer to adapt to the five DR labels without immediately changing all pretrained features. Phase B reloads the best Phase-A checkpoint, unfreezes the backbone and fine-tunes end-to-end using separate learning-rate groups for backbone and classifier. The notebook configures Phase B for up to ten epochs, but the stored history contains four recorded Phase-B epochs; this report does not claim that the full configured budget completed.

        The loss is focal cross-entropy with gamma equal to 2 and inverse-frequency class weights. Focal loss down-weights easy examples and concentrates learning on difficult samples [7]. Weighted sampling further reduces the tendency to optimise only for the majority No-DR class. AdamW is used with cosine-based learning-rate schedules, gradient clipping and early stopping based on validation QWK; AdamW decouples weight decay from the gradient update [8]. Phase A uses cosine annealing with a five-epoch schedule and early-stopping patience of three; Phase B uses cosine annealing warm restarts with T₀=5, Tmult=2 and early-stopping patience of five.

        The optimisation target is not accuracy alone. QWK is tracked during training because the task is ordinal and distance between grade errors matters. The best checkpoint is selected from validation behaviour and the test set is evaluated only after the training pipeline is complete.
        """
    ))
    pages.append(page(
        "## 5.8 Recorded training curves",
        figure("training_curves.png", "Figure 5.4: Recorded training, validation, kappa and accuracy curves") + "\n\n" +
        table(
            "Table 5.3: Recorded training history",
            ["Epoch", "Phase", "Train loss", "Val loss", "Train QWK", "Val QWK", "Train acc.", "Val acc."],
            [[str(row["epoch"]), "Phase A — frozen" if row["epoch"] <= 5 else "Phase B — fine-tuning", f"{row['train_loss']:.3f}", f"{row['val_loss']:.3f}", f"{row['train_kappa']:.3f}", f"{row['val_kappa']:.3f}", f"{row['train_acc'] * 100:.1f}%", f"{row['val_acc'] * 100:.1f}%"] for row in history],
        ) + "\n\n" +
        "The training history file contains nine recorded epochs. Epochs 1–5 use the frozen-backbone head-training phase; epochs 6–9 use end-to-end fine-tuning. The final recorded epoch has training loss 0.3085, validation loss 0.2424, training QWK 0.7511, validation QWK 0.7007, training accuracy 60.4% and validation accuracy 55.0%. The notebook configures ten Phase-B epochs but records four before the stored run ends, so the table documents recorded evidence rather than an unobserved completion. The notebook uses AdamW, focal loss with γ=2, inverse-frequency class weights, gradient clipping and QWK-based checkpoint selection."
    ))
    pages.append(page(
        "## 5.9 Test evaluation and explainability",
        """
        The evaluation script loads the best checkpoint and processes every row in `logs/test_split.csv`. For each image it records the true label, predicted label and five probabilities. It then computes a confusion matrix, classification report, QWK, macro one-vs-rest AUC and bootstrap intervals. The output is saved in `logs/evaluation/metrics.json` and `predictions.csv`.

        The explanation path uses the model's final spatial feature map when available. Grad-CAM takes the gradient of the selected class logit with respect to the feature map, averages gradients across spatial dimensions to obtain channel weights and produces a non-negative weighted activation map [9]. The map is resized to the source image dimensions and colourised for display.

        If a custom timm version does not expose a compatible feature map, the implementation uses a labelled activation, input-gradient or input-intensity fallback. The report includes the method label so that a reviewer can distinguish true Grad-CAM from a fallback visualisation.
        """
    ))
    pages.append(page(
        "## 5.10 Grad-CAM examples",
        figure("gradcam_examples.png", "Figure 5.5: Grad-CAM explainability examples") + "\n\n" +
        "The visualisation grid presents one example per DR grade with the input image, attention overlay and class confidence information. These maps are useful for qualitative auditing: a reviewer can ask whether the highlighted region lies inside the retinal field and whether it appears related to visible structures. They are not proof that the network learned a clinically correct lesion representation.\n\nThe report and frontend deliberately use the phrase “attention preview” when the exact explanation method is not known. This avoids presenting a fallback map as a medically validated explanation."
    ))
    pages.append(page(
        "## 5.11 Backend and database implementation",
        """
        The FastAPI lifespan initialises the SQLite database and loads the model before serving requests. The `/predict` route normalises patient ID, scan date, eye and notes, checks patient existence when persistence is requested, reads the upload, decodes and validates it, computes image quality, runs inference and optionally inserts a scan row. It then creates the report artifact and returns both prediction and report metadata.

        The database module anchors its default path to the repository rather than to the current working directory. Environment variables can override the database and upload directories. Additive migration keeps historical scan rows valid when the eye field is introduced. Query functions return JSON-safe dictionaries and strip filesystem paths down to generated basenames.

        The implementation uses a transaction context for database operations and deletes an uploaded file if persistence fails. This keeps the local prototype consistent when a write error occurs.
        """
    ))
    pages.append(page(
        "## 5.12 Frontend, reports and deployment integration",
        figure("inference_demo.png", "Figure 5.6: Live inference demonstration") + "\n\n" +
        "The frontend submits a multipart form containing the selected file and optional scan metadata. On success it renders the image preview, predicted grade, confidence meter, probability bars, report metadata and attention preview. Download handlers fetch the PDF, CSV or JSON resource and create a browser download with a report-specific filename.\n\nThe PDF report includes patient and scan metadata, source image, prediction, probability table, model version, quality score, attention image, disclaimer and clinician review fields. The CSV contains one row suitable for research spreadsheets, while JSON preserves nested schema information. The local startup script launches both services, and the Dockerfile provides a container entry point for hosted deployment."
    ))
    pages.append(page(
        "## 5.13 Frontend screenshots and report output",
        """
        The implementation includes three principal frontend views. The Diagnose view supports image upload and result review; the History view supports patient profiles and longitudinal scans; and the About view presents architecture and evaluation evidence. The sample PDF image shows the generated export that accompanies a prediction.

        """ + figure("ui_diagnose.png", "Figure 5.7: Diagnose view screenshot") + "\n\n" +
        figure("ui_history.png", "Figure 5.8: History view screenshot") + "\n\n" +
        figure("ui_about.png", "Figure 5.9: About view screenshot") + "\n\n" +
        figure("sample_pdf_report.png", "Figure 5.10: Sample generated PDF report")
    ))
    pages.append(page(
        "## 5.14 Selected source-code excerpts",
        """
        The following excerpts document the implementation modules requested by the development-based dissertation format. They are short, representative extracts; the complete source remains in the repository.

        """ + source_excerpt("deployment/backend/inference.py", 17, 37) + "\n\n" +
        source_excerpt("deployment/backend/utils.py", 108, 133) + "\n\n" +
        source_excerpt("deployment/backend/main.py", 237, 264) + "\n\n" +
        source_excerpt("deployment/backend/reporting.py", 627, 681)
    ))

    # Chapter 6.
    pages.append(page(
        "# CHAPTER 6: TESTING",
        """
        ## 6.1 Testing strategy

        Testing is organised around the user-visible contract rather than around implementation details. The model must produce a five-class response, the service must handle valid and invalid images, patient records must round-trip through SQLite, and report artifacts must be readable. The frontend must not assume that every report contains complete URLs or that every prediction is saved.

        The project uses several complementary forms of evidence: syntax and compilation checks, deterministic regression tests, model evaluation on a frozen test split, live API smoke tests performed during development, and inspection of generated PDF/CSV/JSON artifacts. The automated suite currently covers preprocessing, database persistence, report artifacts and report-document structure; the full model-weight evaluation remains a separate evidence-producing script rather than a per-commit test.

        The clinical disclaimer is also treated as a testable requirement. A report or interface that shows a grade without communicating the screening-only status would not satisfy the intended safety boundary.
        """
    ))
    pages.append(page(
        "## 6.2 Test environment and test data",
        """
        Table 6.1 summarises the test environment.

        """ + table(
            "Table 6.1: Test environment and test data",
            ["Area", "Environment or source", "Purpose"],
            [
                ["Python", "Project virtual environment / Python 3.x", "Backend execution and evaluation scripts"],
                ["Model", "EfficientNet-B4-NS checkpoint", "Inference and test-set prediction"],
                ["Dataset", "APTOS 2019, stratified test split", "Held-out metric calculation"],
                ["Backend", "FastAPI with Uvicorn", "Endpoint and report smoke checks"],
                ["Frontend", "Static HTTP server", "Browser interaction and download flow"],
                ["Storage", "Temporary SQLite and artifact directories", "Persistence and lifecycle checks"],
            ],
        ) + """

        Test data should be de-identified. The project uses dataset image identifiers and generated temporary files rather than real patient names. The sample patient records shown in notebook demonstrations are synthetic examples and are not clinical records.
        """
    ))
    pages.append(page(
        "## 6.3 Input validation tests",
        """
        The image-validation path covers three stages. The byte stream must decode successfully. The decoded array must have three colour channels and a minimum spatial size. The fundus heuristic then checks saturation, contrast and dark-corner coverage so that an arbitrary photograph is less likely to be passed to the classifier.

        Representative negative cases include an empty upload, random bytes, a grayscale image, an image smaller than the minimum dimension and an image with no visible circular retinal field. The expected result is a client error with a clear explanation rather than a model prediction. A valid fundus image should proceed to preprocessing and produce a numeric quality score.

        The validation heuristic is not a complete image-quality classifier. Its purpose is to prevent obvious misuse and to provide a technical signal. Thresholds should be revisited using a curated quality-labelled dataset before deployment beyond research use.
        """
    ))
    pages.append(page(
        "## 6.4 Model and evaluation tests",
        """
        The frozen evaluation script provides the strongest model-level regression evidence currently stored in the repository. It loads `logs/test_split.csv`, runs deterministic preprocessing and records prediction vectors for all 550 rows. The test output is checked for the expected number of rows, five probabilities per row and finite metric values.

        The primary checks are that the confusion matrix has five rows and columns, that the probability vector sums approximately to one, that QWK is computed with quadratic weights and that one-vs-rest AUC is computed for each class. Bootstrap intervals are generated using a fixed random seed so that the reported range is repeatable for the same predictions.

        The current regression suite protects preprocessing, persistence, report normalisation, path safety and document structure. A further model-level regression could compare a checkpoint checksum and a small set of reference predictions; that would detect unintended checkpoint or preprocessing changes without requiring the entire 550-image evaluation on every commit.
        """
    ))
    pages.append(page(
        "## 6.5 API integration tests",
        """
        API integration tests follow the real sequence a user experiences. First, the service is started and the root endpoint is checked. A patient profile is created and read back. A valid image is posted with no patient identifier to exercise quick analysis. The same or another valid image is posted with a patient identifier to verify persistence. The patient endpoint is then queried to confirm that the scan appears in chronological history.

        The report URLs returned from `/predict` are fetched independently. PDF content type and non-zero size are checked; CSV is parsed as a one-row table; JSON is decoded and checked for schema version, model, prediction and expiry fields; preview and attention images are decoded as JPEG. This sequence verifies that a visible button is connected to a real artifact.

        Errors are checked using an unknown patient identifier, invalid scan date, invalid save flag and malformed image. Each error should be a controlled HTTP response rather than an unhandled traceback.
        """
    ))
    pages.append(page(
        "## 6.6 Report-artifact tests",
        """
        Report generation is tested as a multi-file transaction. A report directory is created using a generated identifier. The JSON payload is written first as the source of structured metadata, the CSV row is derived from the same normalised prediction and the PDF embeds the preview and attention images. If any stage fails, the artifact directory is removed so that partial reports are not served.

        The artifact ID accepts only 32 lowercase hexadecimal characters. The endpoint maps a small fixed set of kinds to fixed filenames, which blocks path traversal through the report identifier or kind parameter. Public metadata contains relative URLs and never exposes the absolute directory. These properties are important because the report may contain a patient identifier and uploaded image.

        Expiry is part of the artifact contract. The default retention value is 24 hours and can be configured for testing or deployment. The regression suite sets a short test TTL and verifies that expired metadata and artifact paths are removed or rejected.
        """
    ))
    pages.append(page(
        "## 6.7 Negative and failure-path testing",
        """
        Failure-path testing is especially important for an AI service because the most dangerous failure is a plausible-looking result produced for invalid input. The project therefore distinguishes input rejection from model uncertainty. An image that fails the fundus check is rejected. An accepted image may still receive a low-confidence prediction and should remain labelled as a screening signal.

        Storage failures are handled by removing the generated upload if the database insert fails. Report-generation failures are returned as a server error; the saved scan remains intact and can be investigated. Missing or expired artifacts return a 404 response rather than a server path or a stale file.

        These behaviours do not provide complete operational resilience. Authentication, rate limiting, structured logging, monitoring and backup recovery remain necessary for a hosted service.
        """
    ))
    pages.append(page(
        "## 6.8 Representative test cases",
        table(
            "Table 6.2: Representative test cases",
            ["Test ID", "Scenario", "Expected result", "Observed result"],
            [
                ["TC-01", "Valid fundus, quick analysis", "200 response with five probabilities and report ID", "Passed — live smoke check"],
                ["TC-02", "Valid fundus, saved patient scan", "Scan appears in patient history", "Passed — live smoke check"],
                ["TC-03", "Random bytes upload", "400 readable-image error", "Passed — utility regression test"],
                ["TC-04", "Unknown patient ID", "404 Patient not found", "Passed — route validation"],
                ["TC-05", "Invalid scan date", "400 ISO-date error", "Passed — route validation"],
                ["TC-06", "PDF download", "Non-empty application/pdf artifact", "Passed — artifact regression test"],
                ["TC-07", "CSV download", "One data row with probability columns", "Passed — artifact regression test"],
                ["TC-08", "JSON download", "Decodable schema-versioned payload", "Passed — artifact regression test"],
                ["TC-09", "Attention preview", "JPEG image or explicit fallback message", "Passed — artifact regression test"],
                ["TC-10", "Invalid report ID", "404 without filesystem disclosure", "Passed — path regression test"],
            ],
        ) + "\n\nThe test suite combines deterministic unit tests for preprocessing, database and report behaviour with live endpoint smoke checks for the integrated prediction flow."
    ))
    pages.append(page(
        "## 6.9 Testing summary and performance considerations",
        """
        The project has evidence for model evaluation, report generation and the main local user flow. The regression suite covers preprocessing, database persistence, report normalisation, path safety and report-document structure. The recorded run of `python3 -m pytest -q` produced **10 passed and 5 skipped** tests; the skipped cases correspond to optional OpenCV-dependent checks in the system Python environment. Additional live checks cover the prediction and export sequence. The checks are intentionally separated from the model-weight evaluation so that documentation and application regressions can be detected quickly.

        EfficientNet-B4 at 380 × 380 is computationally heavier than a small mobile model. CPU inference is acceptable for a demonstration but may be too slow for high-throughput screening. The current service loads the model during application startup, which avoids reloading per request but increases startup time and memory use. Future measurements should report warm and cold latency, peak memory, concurrent request behaviour and attention-generation overhead separately.

        The chapter demonstrates that the system can be tested at input, model, API, artifact and interface boundaries. The next chapter analyses the recorded results and their meaning.
        """
    ))

    # Results are included in Chapter 6 to match the development-based format.
    pages.append(page(
        "## 6.10 Results and discussion",
        """
        ### 6.10.1 Results overview

        The project reports results at three levels. Training results describe optimisation behaviour across the recorded run. Test-set results describe generalisation on the held-out APTOS split. System results describe whether a prediction can be transformed into a usable report and monitoring record.

        The model achieves a test accuracy of 55.6%, a QWK of 0.755 and macro one-vs-rest AUC of 0.901 on 550 held-out images. These values should be read together. Accuracy treats every class error equally, whereas QWK gives more weight to distant ordinal mistakes. AUC measures ranking quality and is not equivalent to sensitivity at a deployment threshold.

        The system result is qualitative but important: a prediction includes structured probabilities, attention method, image-quality score and downloadable artifacts. This makes the model output inspectable rather than reducing it to a single coloured label.
        """
    ))
    pages.append(page(
        "### 6.10.2 Training results",
        table(
            "Table 6.3: Recorded training history",
            ["Recorded epoch", "Train loss", "Val loss", "Train QWK", "Val QWK", "Train acc.", "Val acc."],
            [[str(row["epoch"]), f"{row['train_loss']:.3f}", f"{row['val_loss']:.3f}", f"{row['train_kappa']:.3f}", f"{row['val_kappa']:.3f}", f"{row['train_acc'] * 100:.1f}%", f"{row['val_acc'] * 100:.1f}%"] for row in history],
        ) + "\n\n" +
        "Training loss decreases from 1.092 to 0.308 across the recorded rows. Validation loss reaches its minimum recorded value of 0.242. Training QWK rises to 0.751 and validation QWK reaches 0.701. The gap between training and validation behaviour indicates that the model learns useful ordinal structure but still faces generalisation difficulty, especially for minority and adjacent grades."
    ))
    pages.append(page(
        "### 6.10.3 Summary test metrics",
        table(
            "Table 6.4: Summary evaluation metrics",
            ["Metric", "Value", "Interpretation"],
            [
                ["Test size", "550", "Held-out images"],
                ["Accuracy", f"{evaluation['accuracy'] * 100:.1f}%", "Exact grade agreement"],
                ["Quadratic Weighted Kappa", f"{evaluation['qwk']:.3f}", "Ordinal agreement measure"],
                ["Macro AUC", f"{evaluation['macro_auc']:.3f}", "Mean one-vs-rest ranking performance"],
                ["QWK bootstrap 95% interval", f"{evaluation['qwk_ci_95'][0]:.3f}–{evaluation['qwk_ci_95'][1]:.3f}", "Resampling uncertainty estimate"],
                ["Macro AUC bootstrap 95% interval", f"{evaluation['macro_auc_ci_95'][0]:.3f}–{evaluation['macro_auc_ci_95'][1]:.3f}", "Resampling uncertainty estimate"],
            ],
        ) + "\n\n" +
        "The QWK interval is reasonably concentrated around the point estimate for this split, but it should not be interpreted as external validation uncertainty. Bootstrap resampling reflects variation within the available test set; it does not account for a new camera, site or patient population."
    ))
    pages.append(page(
        "### 6.10.4 Class-wise precision, recall and F1",
        table(
            "Table 6.5: Class-wise precision, recall and F1",
            ["Class", "Precision", "Recall", "F1-score", "Support"],
            [
                ["No DR", "0.995", "0.753", "0.857", "271"],
                ["Mild", "0.302", "0.875", "0.450", "56"],
                ["Moderate", "0.889", "0.053", "0.101", "150"],
                ["Severe", "0.141", "0.414", "0.211", "29"],
                ["Proliferative", "0.371", "0.750", "0.496", "44"],
            ],
        ) + "\n\n" +
        "The class-wise table reveals a central limitation hidden by the macro AUC. Moderate recall is only 0.053 even though Moderate AUC is 0.910. This means the model can rank Moderate images reasonably well across thresholds but the default argmax decision rule often selects a neighbouring or higher grade. Severe precision is also low, reflecting overprediction of Severe for some Moderate cases. These patterns support the use of calibration, ordinal decision rules and threshold analysis in future work."
    ))
    pages.append(page(
        "### 6.10.5 Per-class AUC analysis",
        table(
            "Table 6.6: Per-class AUC",
            ["Class", "AUC", "Observation"],
            [
                ["No DR", f"{summary['per_class_auc']['No DR']:.3f}", "Strong separation of healthy and non-healthy cases in this split"],
                ["Mild", f"{summary['per_class_auc']['Mild']:.3f}", "Useful ranking but affected by class overlap"],
                ["Moderate", f"{summary['per_class_auc']['Moderate']:.3f}", "High ranking score despite weak argmax recall"],
                ["Severe", f"{summary['per_class_auc']['Severe']:.3f}", "Lowest AUC; minority and visually overlapping class"],
                ["Proliferative", f"{summary['per_class_auc']['Proliferative']:.3f}", "Strong ranking relative to the available support"],
            ],
        ) + "\n\n" +
        "AUC is useful because it separates ranking quality from one operating threshold. For screening design, the next step would be to define clinically meaningful binary tasks, such as any DR versus No DR or referable DR versus non-referable DR, and measure sensitivity and specificity at chosen thresholds. The current five-class AUC table is evidence for research comparison, not a deployment threshold recommendation."
    ))
    pages.append(page(
        "### 6.10.6 Confusion matrix interpretation",
        figure("confusion_matrix.png", "Figure 6.1: Test-set confusion matrix") + "\n\n" +
        "The raw confusion matrix contains 204 correct No-DR predictions, 49 correct Mild predictions, 8 correct Moderate predictions, 12 correct Severe predictions and 33 correct Proliferative predictions. No-DR precision is high because very few non-No-DR images are predicted as No DR. Moderate cases are distributed across Mild, Severe and Proliferative predictions, which explains the low Moderate recall and illustrates the difficulty of using a flat argmax rule for an ordinal task.\n\nThe matrix also shows why QWK is informative: many mistakes remain close to the diagonal, but the clinical meaning of a Moderate-to-Mild error differs from a No-DR-to-Proliferative error. A future ordinal model could optimise a distance-aware loss directly."
    ))
    pages.append(page(
        "### 6.10.7 ROC curves and explainability",
        figure("roc_curves.png", "Figure 6.2: One-vs-rest ROC curves") + "\n\n" +
        "The ROC curves provide a threshold-independent view of the five class scores. No DR reaches an AUC of 0.991, the strongest class separation in the experiment. Severe reaches 0.813, the lowest value, which is consistent with its smaller support and overlap with Moderate and Proliferative patterns.\n\nThe explanation images should be reviewed alongside these quantitative results. A high AUC does not guarantee that attention is clinically meaningful, and a visually plausible heatmap does not prove high accuracy. Combining probability, quality and attention information gives the reviewer a richer but still imperfect basis for inspection."
    ))
    pages.append(page(
        "### 6.10.8 Monitoring workflow and threats to validity",
        figure("progression_P001.png", "Figure 6.3: Synthetic patient progression demonstration") + "\n\n" +
        "The monitoring module stores a sequence of saved predictions and compares the baseline grade with the latest grade. The notebook demonstration uses synthetic patient profiles and six example visits to show how a timeline can display stable, improving or worsening model-observed direction. This is a software demonstration, not longitudinal clinical evidence.\n\nThreats to validity include label noise, class imbalance, dataset shift, lack of external validation, possible leakage through image-level rather than patient-level splitting, and the fact that the final service checkpoint must be available and verified before deployment. The results support continued research but do not establish safety, calibration or clinical effectiveness."
    ))

    # Chapters 7 and 8.
    pages.append(page(
        "# CHAPTER 7: SUMMARY AND CONCLUSION",
        """
        ## 7.1 Summary and conclusion

        This project developed an integrated prototype for AI-based diabetic retinopathy detection and monitoring. The model uses EfficientNet-B4-NS transfer learning, a five-class classifier head, focal loss, inverse-frequency weighting and a stratified APTOS 2019 split. Preprocessing combines border cropping, illumination correction, CLAHE, resizing and normalisation.

        The system provides more than model inference. It validates uploaded images, reports technical quality, creates Grad-CAM or labelled fallback attention, exposes REST endpoints, stores optional patient histories, calculates ordinal progression and generates PDF, CSV and JSON exports. The browser frontend presents the workflow in Diagnose, History and About views.

        The evaluation logs report 55.6% test accuracy, 0.755 QWK and 0.901 macro AUC on 550 held-out images. These results show useful signal but also reveal class-wise weaknesses, particularly for Moderate and Severe argmax decisions. The project therefore succeeds as a research and engineering prototype while leaving clinical validation as future work.
        """
    ))
    pages.append(page(
        "# CHAPTER 8: LIMITATIONS AND FUTURE WORK",
        """
        ## 8.1 Limitations

        """ + table(
            "Table 8.1: Limitations and mitigation direction",
            ["Limitation", "Effect", "Mitigation direction"],
            [
                ["Single public dataset", "Unknown generalisation to other sites", "External multi-centre validation"],
                ["Class imbalance", "Weak minority-class precision/recall trade-offs", "More data, calibrated thresholds, ordinal loss"],
                ["Argmax output", "Moderate cases often move to adjacent classes", "Cost-sensitive decision policy"],
                ["Local storage", "Data may be lost or exposed in hosted environments", "Managed database and object storage"],
                ["No authentication", "Patient history is not safe for public deployment", "Identity, authorization and audit logging"],
                ["Heuristic quality score", "Not clinically validated", "Expert-labelled quality study"],
                ["Attention maps", "Not lesion segmentation or causal proof", "Faithfulness and reader studies"],
                ["Checkpoint dependency", "Missing weights can invalidate inference", "Verified artifact, checksum and readiness gate"],
            ],
        ) + "\n\n" + """
        The limitations are not minor implementation details. Each one can change the meaning of a result. The prototype should therefore be used only with synthetic or properly governed research data and with qualified human review.

        ## 8.2 Future work

        Future work should proceed in phases. First, harden the service with explicit environment configuration, a readiness endpoint, upload limits, restricted CORS, report-expiration enforcement, `.dockerignore` rules and automated regression tests. Second, improve the model with ordinal objectives, calibration, threshold selection and external datasets. Third, improve clinical relevance through quality-labelled data, reader comparison and subgroup analysis. Fourth, improve deployment with authentication, PostgreSQL, object storage, backups, monitoring and audit trails.

        Model development could compare EfficientNet-B4 with smaller backbones and exported ONNX/TorchScript runtimes. The prediction interface could expose binary screening tasks alongside the five-class output. Report generation could accept clinician review fields and preserve a signed review record. A future study should measure latency, memory and concurrency under a defined workload rather than relying on informal “real-time” wording.

        The long-term goal is not to make the model autonomous. It is to build a validated decision-support system in which the model, image quality, explanation, clinical reviewer and governance process are all visible.
        """
    ))
    pages.append(page(
        "# BIBLIOGRAPHY AND APPENDIX",
        """
        ## Bibliography

        [1] V. Gulshan *et al.*, “Development and Validation of a Deep Learning Algorithm for Detection of Diabetic Retinopathy in Retinal Fundus Photographs,” *JAMA*, vol. 316, no. 22, pp. 2402–2410, 2016.

        [2] C. Wilkinson *et al.*, “Proposed international clinical diabetic retinopathy and diabetic macular edema disease severity scales,” *Ophthalmology*, vol. 110, no. 9, pp. 1677–1682, 2003.

        [3] D. S. W. Ting *et al.*, “Development and validation of a deep learning system for diabetic retinopathy and related eye diseases using retinal images from multiethnic populations with diabetes,” *JAMA*, vol. 318, no. 22, pp. 2211–2223, 2017.

        [4] M. D. Abràmoff *et al.*, “Improved automated detection of diabetic retinopathy on a publicly available dataset through integration of deep learning,” *Investigative Ophthalmology & Visual Science*, vol. 57, no. 13, pp. 5200–5206, 2016.

        [5] M. Tan and Q. V. Le, “EfficientNet: Rethinking model scaling for convolutional neural networks,” in *Proc. 36th Int. Conf. Machine Learning*, 2019, pp. 6105–6114.

        [6] Q. Xie *et al.*, “Self-training with noisy student improves ImageNet classification,” in *Proc. IEEE/CVF Conf. Computer Vision and Pattern Recognition*, 2020, pp. 10687–10698.

        [7] T.-Y. Lin *et al.*, “Focal loss for dense object detection,” in *Proc. IEEE International Conference on Computer Vision*, 2017, pp. 2980–2988.

        [8] I. Loshchilov and F. Hutter, “Decoupled weight decay regularization,” in *Proc. International Conference on Learning Representations*, 2019.

        [9] R. R. Selvaraju *et al.*, “Grad-CAM: Visual explanations from deep networks via gradient-based localization,” in *Proc. IEEE International Conference on Computer Vision*, 2017, pp. 618–626.

        [10] Kaggle, “APTOS 2019 Blindness Detection,” dataset and competition resource, 2019. [Online]. Available: https://www.kaggle.com/c/aptos2019-blindness-detection. [Accessed: Oct. 25, 2026].

        [11] P. Porwal *et al.*, “Indian diabetic retinopathy image dataset (IDRiD): a database for diabetic retinopathy screening research,” *Data*, vol. 3, no. 3, art. no. 25, 2018, doi: 10.3390/data3030025.

        [12] E. Decencière *et al.*, “Feedback on a publicly distributed image database: the Messidor database,” *Image Analysis & Stereology*, vol. 33, no. 3, pp. 231–234, 2014, doi: 10.5566/ias.1155.

        [13] A. Paszke *et al.*, “PyTorch: An imperative style, high-performance deep learning library,” in *Advances in Neural Information Processing Systems*, vol. 32, pp. 8024–8035, 2019.

        [14] M. Pratt *et al.*, “Convolutional neural networks for diabetic retinopathy,” *Procedia Computer Science*, vol. 90, pp. 200–205, 2016.

        [15] G. Quellec *et al.*, “Deep image mining for diabetic retinopathy screening,” *Medical Image Analysis*, vol. 39, pp. 178–193, 2017.

        [16] L. Dai *et al.*, “A deep learning system for detecting diabetic retinopathy across the disease spectrum,” *Nature Communications*, vol. 12, art. no. 3242, 2021, doi: 10.1038/s41467-021-23458-5.

        [17] W. Cao, V. Mirjalili, and S. Raschka, “Rank-consistent ordinal regression for neural networks with application to age estimation,” *Pattern Recognition Letters*, vol. 140, pp. 325–331, 2020, doi: 10.1016/j.patrec.2020.11.008.

        [18] D. S. W. Ting *et al.*, “Deep learning in ophthalmology: the technical and clinical considerations,” *Progress in Retinal and Eye Research*, vol. 72, art. no. 100759, 2019, doi: 10.1016/j.preteyeres.2019.04.003.

        [19] K. Zuiderveld, “Contrast limited adaptive histogram equalization,” in *Graphics Gems IV*, Academic Press, 1994, pp. 474–485, doi: 10.1016/B978-0-12-336156-1.50061-6.

        [20] OpenCV, “OpenCV documentation,” software documentation. [Online]. Available: https://docs.opencv.org/4.x/. [Accessed: Oct. 25, 2026].

        [21] FastAPI, “FastAPI documentation,” software documentation. [Online]. Available: https://fastapi.tiangolo.com/. [Accessed: Oct. 25, 2026].

        [22] ReportLab, “ReportLab PDF generation toolkit documentation,” software documentation. [Online]. Available: https://docs.reportlab.com/. [Accessed: Oct. 25, 2026].

        ## Appendix A: Key project artefacts

        The reproducible project evidence is stored in the following repository locations:

        """ + bullets([
            "`DR_Detection_Monitoring.ipynb` — training, evaluation, monitoring demonstration and model export notebook.",
            "`logs/training_history.csv` — recorded training and validation history.",
            "`logs/evaluation/metrics.json` and `predictions.csv` — held-out test metrics and prediction rows.",
            "`deployment/backend/inference.py` — model definition and explanation path.",
            "`deployment/backend/main.py` — FastAPI application and routes.",
            "`deployment/backend/db.py` — patient and scan persistence.",
            "`deployment/backend/reporting.py` — PDF, CSV, JSON and image artifact generation.",
            "`deployment/frontend/index.html`, `styles.css` and `app.js` — browser workflow.",
            "`tests/` and `pytest.ini` — deterministic regression tests and test discovery configuration.",
        ]) + """

        **Repository:** {IDENTITY['repository']}  
        **Suggested hard-bound spine text:** AI-BASED DIABETIC RETINOPATHY DETECTION & MONITORING ({IDENTITY['spine_year']})
        """
    ))

    # Keep the report at the requested 70-page planned structure while allowing
    # the added literature and implementation evidence to flow naturally into
    # the preceding sections. Word will paginate these merged sections using
    # the configured A4 margins and 1.5 line spacing.
    merge_targets = (
        "## 3.2 Literature review and related work",
        "## 5.13 Frontend screenshots and report output",
        "## 5.14 Selected source-code excerpts",
    )
    for target in merge_targets:
        for index, content in enumerate(pages):
            if target in content:
                pages[index] = content.replace(raw_page_break(), "", 1)
                break

    # The last page does not need an explicit break.
    if pages:
        pages[-1] = pages[-1].rsplit(raw_page_break(), 1)[0]
    REPORT_MD.write_text("\n".join(pages), encoding="utf-8")
    planned_breaks = REPORT_MD.read_text(encoding="utf-8").count(raw_page_break())
    print(f"Wrote {REPORT_MD} with {planned_breaks + 1} planned pages")


def find_or_create(parent: ET.Element, tag: str) -> ET.Element:
    child = parent.find(tag)
    if child is None:
        child = ET.SubElement(parent, tag)
    return child


def set_fonts(rpr: ET.Element, size: int, bold: bool = False, italic: bool = False) -> None:
    for child in list(rpr):
        if child.tag in {w("rFonts"), w("sz"), w("szCs"), w("b"), w("i")}:
            rpr.remove(child)
    fonts = ET.Element(w("rFonts"), {
        w("ascii"): "Times New Roman",
        w("hAnsi"): "Times New Roman",
        w("eastAsia"): "Times New Roman",
        w("cs"): "Times New Roman",
    })
    rpr.insert(0, fonts)
    ET.SubElement(rpr, w("sz"), {w("val"): str(size)})
    ET.SubElement(rpr, w("szCs"), {w("val"): str(size)})
    if bold:
        ET.SubElement(rpr, w("b"))
    if italic:
        ET.SubElement(rpr, w("i"))


def set_style(styles_root: ET.Element, style_id: str, size: int, bold: bool = False,
              italic: bool = False, align: str | None = None, line: int = 360,
              before: int = 0, after: int = 0) -> None:
    style = styles_root.find(f".//w:style[@w:styleId='{style_id}']", NS)
    if style is None:
        style = ET.SubElement(styles_root, w("style"), {
            w("type"): "paragraph",
            w("customStyle"): "1",
            w("styleId"): style_id,
        })
        ET.SubElement(style, w("name"), {w("val"): style_id})
    rpr = find_or_create(style, w("rPr"))
    set_fonts(rpr, size, bold=bold, italic=italic)
    ppr = find_or_create(style, w("pPr"))
    for child in list(ppr):
        if child.tag in {w("spacing"), w("jc")}:
            ppr.remove(child)
    ET.SubElement(ppr, w("spacing"), {
        w("line"): str(line),
        w("lineRule"): "auto",
        w("before"): str(before),
        w("after"): str(after),
    })
    if align:
        ET.SubElement(ppr, w("jc"), {w("val"): align})


def patch_reference_docx() -> None:
    temp_reference = REPORT_DIR / "reference-default.docx"
    with temp_reference.open("wb") as handle:
        subprocess.run(
            ["pandoc", "--print-default-data-file", "reference.docx"],
            check=True,
            stdout=handle,
        )

    with zipfile.ZipFile(temp_reference, "r") as source:
        entries = {name: source.read(name) for name in source.namelist()}

    styles_root = ET.fromstring(entries["word/styles.xml"])
    # Normal text: 12 point Times New Roman, justified, 1.5 line spacing.
    set_style(styles_root, "Normal", 24, align="both", line=360, after=0)
    set_style(styles_root, "BodyText", 24, align="both", line=360, after=0)
    set_style(styles_root, "FirstParagraph", 24, align="both", line=360, after=0)
    set_style(styles_root, "Compact", 22, align="both", line=300, after=0)
    set_style(styles_root, "Title", 34, bold=True, align="center", line=360, after=180)
    set_style(styles_root, "Subtitle", 26, align="center", line=320, after=120)
    set_style(styles_root, "Author", 24, align="center", line=320, after=80)
    set_style(styles_root, "Date", 24, align="center", line=320, after=80)
    set_style(styles_root, "Heading1", 32, bold=True, align="left", line=360, before=360, after=180)
    set_style(styles_root, "Heading2", 28, bold=True, align="left", line=360, before=240, after=120)
    set_style(styles_root, "Heading3", 24, italic=True, align="left", line=360, before=180, after=80)
    set_style(styles_root, "Caption", 20, align="center", line=240, before=80, after=120)
    set_style(styles_root, "TableCaption", 20, align="center", line=240, before=80, after=120)
    set_style(styles_root, "ImageCaption", 20, align="center", line=240, before=80, after=120)
    set_style(styles_root, "CaptionedFigure", 20, align="center", line=240, before=80, after=0)
    set_style(styles_root, "VerbatimChar", 19, align="left", line=240, after=60)

    # Apply Times New Roman to document defaults as well.
    defaults = styles_root.find(w("docDefaults"))
    if defaults is not None:
        rpr_default = defaults.find(f".//{w('rPrDefault')}/{w('rPr')}")
        if rpr_default is not None:
            set_fonts(rpr_default, 24)
    entries["word/styles.xml"] = ET.tostring(styles_root, encoding="utf-8", xml_declaration=True)

    document_root = ET.fromstring(entries["word/document.xml"])
    body = document_root.find(w("body"))
    if body is not None:
        sect = body.find(w("sectPr"))
        if sect is not None:
            pg_sz = find_or_create(sect, w("pgSz"))
            pg_sz.set(w("w"), "11906")
            pg_sz.set(w("h"), "16838")
            pg_mar = find_or_create(sect, w("pgMar"))
            for key, value in [("top", "1440"), ("bottom", "1440"), ("left", "2160"), ("right", "1440"), ("header", "720"), ("footer", "720"), ("gutter", "0")]:
                pg_mar.set(w(key), value)
    entries["word/document.xml"] = ET.tostring(document_root, encoding="utf-8", xml_declaration=True)

    with zipfile.ZipFile(REFERENCE_DOCX, "w", zipfile.ZIP_DEFLATED) as target:
        for name, data in entries.items():
            target.writestr(name, data)
    temp_reference.unlink(missing_ok=True)


def footer_xml() -> bytes:
    root = ET.Element(w("ftr"))
    paragraph = ET.SubElement(root, w("p"))
    ppr = ET.SubElement(paragraph, w("pPr"))
    tabs = ET.SubElement(ppr, w("tabs"))
    ET.SubElement(tabs, w("tab"), {w("val"): "right", w("pos"): "9360"})
    run = ET.SubElement(paragraph, w("r"))
    rpr = ET.SubElement(run, w("rPr"))
    set_fonts(rpr, 20)
    ET.SubElement(run, w("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = "Department of Artificial Intelligence and Machine Learning"
    ET.SubElement(run, w("tab"))
    field_begin = ET.SubElement(paragraph, w("r"))
    ET.SubElement(field_begin, w("fldChar"), {w("fldCharType"): "begin"})
    field_instruction = ET.SubElement(paragraph, w("r"))
    ET.SubElement(field_instruction, w("instrText"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = " PAGE "
    field_end = ET.SubElement(paragraph, w("r"))
    ET.SubElement(field_end, w("fldChar"), {w("fldCharType"): "end"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def set_section_properties(sect: ET.Element, footer_id: str, fmt: str, start: int,
                           title_page: bool = False, section_type: str | None = None) -> None:
    if section_type:
        node = sect.find(w("type"))
        if node is None:
            node = ET.SubElement(sect, w("type"))
        node.set(w("val"), section_type)
    pg_sz = find_or_create(sect, w("pgSz"))
    pg_sz.set(w("w"), "11906")
    pg_sz.set(w("h"), "16838")
    pg_mar = find_or_create(sect, w("pgMar"))
    for key, value in [("top", "1440"), ("bottom", "1440"), ("left", "2160"), ("right", "1440"), ("header", "720"), ("footer", "720"), ("gutter", "0")]:
        pg_mar.set(w(key), value)
    for child in list(sect):
        if child.tag in {w("footerReference"), w("pgNumType"), w("titlePg")}:
            sect.remove(child)
    ET.SubElement(sect, w("footerReference"), {w("type"): "default", r("id"): footer_id})
    if title_page:
        ET.SubElement(sect, w("titlePg"))
    ET.SubElement(sect, w("pgNumType"), {w("fmt"): fmt, w("start"): str(start)})


def add_text_run(parent: ET.Element, text: str, size: int = 20, bold: bool = False) -> None:
    run = ET.SubElement(parent, w("r"))
    rpr = ET.SubElement(run, w("rPr"))
    set_fonts(rpr, size, bold=bold)
    ET.SubElement(run, w("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = text


def add_field_run(parent: ET.Element, instruction: str, result: str) -> None:
    begin = ET.SubElement(parent, w("r"))
    ET.SubElement(begin, w("fldChar"), {w("fldCharType"): "begin"})
    instr = ET.SubElement(parent, w("r"))
    ET.SubElement(instr, w("instrText"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}).text = f" {instruction} "
    separate = ET.SubElement(parent, w("r"))
    ET.SubElement(separate, w("fldChar"), {w("fldCharType"): "separate"})
    add_text_run(parent, result, size=20)
    end = ET.SubElement(parent, w("r"))
    ET.SubElement(end, w("fldChar"), {w("fldCharType"): "end"})


def patch_cover_page(body: ET.Element) -> None:
    """Center the cover-page content and use the title style for its title."""

    for paragraph in body.findall(w("p")):
        page_break = paragraph.find(f".//{w('br')}[@{w('type')}='page']")
        ppr = paragraph.find(w("pPr"))
        if ppr is None:
            ppr = ET.SubElement(paragraph, w("pPr"))
        alignment = ppr.find(w("jc"))
        if alignment is None:
            alignment = ET.SubElement(ppr, w("jc"))
        alignment.set(w("val"), "center")

        text = "".join(node.text or "" for node in paragraph.iter(w("t"))).strip()
        if text == "AI-BASED DIABETIC RETINOPATHY DETECTION & MONITORING":
            style = ppr.find(w("pStyle"))
            if style is None:
                style = ET.SubElement(ppr, w("pStyle"))
            style.set(w("val"), "Title")
        if page_break is not None:
            break


def patch_caption_fields(body: ET.Element) -> None:
    """Convert static caption numbers into chapter-aware Word SEQ fields.

    The chapter prefix remains explicit because the report uses manually
    numbered chapter headings. The item number is a real SEQ field: the first
    caption of each label in a chapter resets that label's sequence to one and
    later captions increment it. This keeps captions and generated lists
    correct when an item is inserted or removed within a chapter.
    """

    seen: set[tuple[str, str]] = set()
    for paragraph in body.findall(w("p")):
        ppr = paragraph.find(w("pPr"))
        style = ppr.find(w("pStyle")) if ppr is not None else None
        style_id = style.attrib.get(w("val")) if style is not None else ""
        if style_id not in {"TableCaption", "ImageCaption"}:
            continue
        text = "".join(node.text or "" for node in paragraph.iter(w("t"))).strip()
        match = re.match(r"^(Table|Figure)\s+([0-9]+(?:\.[0-9]+)?)\s*:\s*(.*)$", text)
        if not match:
            continue
        label, number, title = match.groups()
        for child in list(paragraph):
            if child.tag != w("pPr"):
                paragraph.remove(child)
        if "." in number:
            chapter, item = number.split(".", 1)
        else:
            chapter, item = "", number
        prefix = f"{label} {chapter}." if chapter else f"{label} "
        add_text_run(paragraph, prefix, size=20, bold=True)
        sequence_key = (label, chapter)
        if sequence_key not in seen:
            instruction = f"SEQ {label} \\r 1 \\* ARABIC"
            seen.add(sequence_key)
        else:
            instruction = f"SEQ {label} \\* ARABIC"
        add_field_run(paragraph, instruction, item)
        add_text_run(paragraph, f": {title}", size=20)


def patch_output_docx() -> None:
    with zipfile.ZipFile(REPORT_DOCX, "r") as source:
        entries = {name: source.read(name) for name in source.namelist()}

    document_root = ET.fromstring(entries["word/document.xml"])
    body = document_root.find(w("body"))
    if body is None:
        raise RuntimeError("Generated document has no body")
    final_sect = body.find(w("sectPr"))
    if final_sect is None:
        final_sect = ET.SubElement(body, w("sectPr"))

    relationships = ET.fromstring(entries["word/_rels/document.xml.rels"])
    existing_ids = []
    for rel in relationships:
        rid = rel.attrib.get("Id", "")
        match = re.fullmatch(r"rId(\d+)", rid)
        if match:
            existing_ids.append(int(match.group(1)))
    footer_id = f"rId{max(existing_ids or [0]) + 1}"
    ET.SubElement(relationships, f"{{{REL_NS}}}Relationship", {
        "Id": footer_id,
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer",
        "Target": "footer1.xml",
    })
    entries["word/_rels/document.xml.rels"] = ET.tostring(relationships, encoding="utf-8", xml_declaration=True)
    entries["word/footer1.xml"] = footer_xml()

    content_types = ET.fromstring(entries["[Content_Types].xml"])
    if not any(node.attrib.get("PartName") == "/word/footer1.xml" for node in content_types):
        ET.SubElement(content_types, f"{{{CT_NS}}}Override", {
            "PartName": "/word/footer1.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml",
        })
    entries["[Content_Types].xml"] = ET.tostring(content_types, encoding="utf-8", xml_declaration=True)

    # The final section uses Arabic numbering starting at Chapter 1. A section
    # break is inserted immediately before the Chapter 1 heading so that the
    # front matter remains lower-Roman numbered.
    chapter_index = None
    paragraphs = list(body.findall(w("p")))
    for index, paragraph in enumerate(paragraphs):
        text = "".join(node.text or "" for node in paragraph.iter(w("t")))
        if "CHAPTER 1: INTRODUCTION" in text.upper():
            chapter_index = index
            break

    front_sect = ET.Element(w("sectPr"))
    set_section_properties(front_sect, footer_id, "lowerRoman", 1, title_page=True, section_type="nextPage")
    if chapter_index is not None and chapter_index > 0:
        chapter_paragraph = paragraphs[chapter_index]
        all_children = list(body)
        body_position = all_children.index(chapter_paragraph)
        previous = all_children[body_position - 1]
        if previous.tag != w("p"):
            previous = ET.Element(w("p"))
            body.insert(body_position, previous)
        ppr = previous.find(w("pPr"))
        if ppr is None:
            ppr = ET.SubElement(previous, w("pPr"))
        for child in list(ppr):
            if child.tag == w("sectPr"):
                ppr.remove(child)
        ppr.append(front_sect)

    set_section_properties(final_sect, footer_id, "decimal", 1, title_page=False)
    patch_cover_page(body)
    patch_caption_fields(body)
    entries["word/document.xml"] = ET.tostring(document_root, encoding="utf-8", xml_declaration=True)

    settings_root = ET.fromstring(entries["word/settings.xml"])
    for node in list(settings_root):
        if node.tag == w("updateFields"):
            settings_root.remove(node)
    ET.SubElement(settings_root, w("updateFields"), {w("val"): "true"})
    entries["word/settings.xml"] = ET.tostring(settings_root, encoding="utf-8", xml_declaration=True)

    temp_output = REPORT_DOCX.with_suffix(".patched.docx")
    with zipfile.ZipFile(temp_output, "w", zipfile.ZIP_DEFLATED) as target:
        for name, data in entries.items():
            target.writestr(name, data)
    shutil.move(temp_output, REPORT_DOCX)


def build_docx() -> None:
    build_markdown()
    create_diagrams()
    create_ui_screenshots()
    patch_reference_docx()
    subprocess.run(
        [
            "pandoc",
            str(REPORT_MD),
            "--from=markdown+raw_attribute",
            "--reference-doc=" + str(REFERENCE_DOCX),
            "--resource-path=" + str(REPORT_DIR),
            "--standalone",
            "--wrap=none",
            "-o",
            str(REPORT_DOCX),
        ],
        check=True,
    )
    patch_output_docx()

    with zipfile.ZipFile(REPORT_DOCX, "r") as source:
        document_xml = source.read("word/document.xml").decode("utf-8")
    breaks = len(re.findall(r"w:type=\"page\"", document_xml))
    print(f"Generated {REPORT_DOCX}")
    print(f"Explicit page breaks: {breaks}; expected page count: {breaks + 1}")


if __name__ == "__main__":
    build_docx()
