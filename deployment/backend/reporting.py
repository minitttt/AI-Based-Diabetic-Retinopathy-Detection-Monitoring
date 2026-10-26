"""Temporary report artifact generation for prediction results.

Reports are intentionally file-backed rather than database-backed.  A report
ID is generated once for an analysis, and the JSON, CSV, PDF, preview, and
attention-map resources all live under that ID until the temporary artifact is
expired.  Only generated IDs and relative URLs leave this module.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import shutil
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional
from uuid import uuid4

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

try:  # ReportLab is the preferred production PDF renderer.
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Image as ReportLabImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from xml.sax.saxutils import escape as xml_escape

    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in minimal environments
    REPORTLAB_AVAILABLE = False


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT_DIR = BACKEND_DIR / "report_artifacts"
REPORT_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
REPORT_SCHEMA_VERSION = "1.0"
DEFAULT_TTL_SECONDS = 24 * 60 * 60
CLASS_NAMES = ("No DR", "Mild", "Moderate", "Severe", "Proliferative")
CLINICAL_DISCLAIMER = (
    "This AI-generated screening report is for research and educational support "
    "only. It is not a diagnosis or a certified medical device. A qualified "
    "ophthalmologist or other licensed clinician must review the original image "
    "and all clinical context before making care decisions."
)


def _report_root() -> Path:
    configured = os.getenv("RETINASCAN_REPORT_DIR")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path.resolve()
    return DEFAULT_REPORT_DIR


def _ttl_seconds() -> int:
    try:
        value = int(os.getenv("RETINASCAN_REPORT_TTL_SECONDS", str(DEFAULT_TTL_SECONDS)))
    except ValueError:
        value = DEFAULT_TTL_SECONDS
    return max(60, value)


def _safe_report_id(report_id: str) -> Optional[str]:
    value = str(report_id or "").strip().lower()
    return value if REPORT_ID_PATTERN.fullmatch(value) else None


def _artifact_urls(report_id: str) -> dict[str, str]:
    """Return frontend-safe relative URLs for one generated artifact."""

    safe_id = _safe_report_id(report_id)
    if safe_id is None:
        raise ValueError("Invalid report identifier")
    base = f"/reports/{safe_id}"
    return {
        "metadata": base,
        "json": f"{base}/json",
        "csv": f"{base}/csv",
        "pdf": f"{base}/pdf",
        "preview": f"{base}/image",
        "image": f"{base}/image",
        "attention": f"{base}/attention",
        "explanation": f"{base}/attention",
    }


def _as_utc(value: Any) -> Optional[datetime]:
    """Parse a timestamp and normalise it to an aware UTC datetime."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith(("Z", "z")):
            raw = f"{raw[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resolved_report_root(root: Optional[Path] = None) -> Optional[Path]:
    """Resolve the configured root, rejecting an unusable filesystem path."""

    try:
        resolved = (root if root is not None else _report_root()).resolve()
        if resolved.exists() and not resolved.is_dir():
            return None
    except (OSError, RuntimeError):
        return None
    return resolved


def _safe_artifact_dir(report_id: str, root: Optional[Path] = None) -> Optional[Path]:
    """Return an existing, non-symlink artifact directory inside the root."""

    safe_id = _safe_report_id(report_id)
    root_path = _resolved_report_root(root)
    if safe_id is None or root_path is None:
        return None

    candidate = root_path / safe_id
    try:
        if candidate.is_symlink() or not candidate.is_dir():
            return None
        resolved_candidate = candidate.resolve()
        resolved_candidate.relative_to(root_path)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def _safe_artifact_file(
    report_id: str,
    filename: str,
    root: Optional[Path] = None,
) -> Optional[Path]:
    """Return a fixed-name regular file after checking path containment."""

    if not isinstance(filename, str) or Path(filename).name != filename:
        return None
    artifact_dir = _safe_artifact_dir(report_id, root)
    if artifact_dir is None:
        return None

    candidate = artifact_dir / filename
    try:
        if candidate.is_symlink() or not candidate.is_file():
            return None
        resolved_candidate = candidate.resolve()
        resolved_candidate.relative_to(artifact_dir.resolve())
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def _load_report_payload(path: Path) -> Optional[dict[str, Any]]:
    """Read one metadata file without following a metadata symlink."""

    try:
        if path.is_symlink() or not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _artifact_expires_at(
    payload: Mapping[str, Any],
    artifact_dir: Path,
) -> Optional[datetime]:
    """Return the advertised expiry, with a legacy filesystem fallback."""

    if "expires_at" in payload:
        return _as_utc(payload.get("expires_at"))

    for key in ("created_at", "timestamp"):
        created_at = _as_utc(payload.get(key))
        if created_at is not None:
            return created_at + timedelta(seconds=_ttl_seconds())

    try:
        created_at = datetime.fromtimestamp(artifact_dir.stat().st_mtime, timezone.utc)
    except OSError:
        return None
    return created_at + timedelta(seconds=_ttl_seconds())


def _is_expired(
    payload: Mapping[str, Any],
    artifact_dir: Path,
    now: Optional[datetime] = None,
) -> bool:
    expires_at = _artifact_expires_at(payload, artifact_dir)
    if expires_at is None:
        # Invalid or unavailable expiry metadata must fail closed.
        return True
    current = _as_utc(now) or datetime.now(timezone.utc)
    return current >= expires_at


def _cleanup_expired(root: Path, now: Optional[datetime] = None) -> None:
    """Best-effort cleanup of old generated artifact directories."""

    root_path = _resolved_report_root(root)
    if root_path is None:
        return

    current = _as_utc(now) or datetime.now(timezone.utc)
    try:
        entries = tuple(root_path.iterdir())
    except OSError:
        return

    for entry in entries:
        try:
            if (
                entry.is_symlink()
                or not entry.is_dir()
                or not REPORT_ID_PATTERN.fullmatch(entry.name)
            ):
                continue

            payload = _load_report_payload(entry / "report.json")
            if payload is not None:
                expired = _is_expired(payload, entry, current)
            else:
                # A partially-written or legacy artifact has no trusted
                # metadata, so use its directory age for eventual cleanup.
                try:
                    expires_at = datetime.fromtimestamp(
                        entry.stat().st_mtime, timezone.utc
                    ) + timedelta(seconds=_ttl_seconds())
                except OSError:
                    continue
                expired = current >= expires_at

            if expired:
                shutil.rmtree(entry)
        except (OSError, RuntimeError, ValueError, TypeError):
            # A concurrent request may be writing/removing this artifact.
            continue


def _safe_display_filename(filename: Optional[str]) -> str:
    raw = str(filename or "").replace("\\", "/")
    safe = PurePosixPath(raw).name
    safe = " ".join(safe.replace("\x00", "").split())
    return safe[:255] or "fundus_image"


def _finite_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _normalise_prediction(prediction: Mapping[str, Any]) -> dict[str, Any]:
    try:
        grade_idx = int(prediction.get("grade_idx", 0))
    except (TypeError, ValueError):
        grade_idx = 0
    grade_idx = max(0, min(len(CLASS_NAMES) - 1, grade_idx))
    grade_name = str(prediction.get("grade_name") or CLASS_NAMES[grade_idx])
    confidence = _finite_float(prediction.get("confidence"), 0.0) or 0.0
    confidence = max(0.0, min(1.0, confidence if confidence <= 1 else confidence / 100.0))

    raw_probabilities = prediction.get("probabilities") or []
    probabilities: list[Optional[float]] = []
    for index in range(len(CLASS_NAMES)):
        raw = raw_probabilities[index] if index < len(raw_probabilities) else None
        value = _finite_float(raw)
        if value is not None and value > 1:
            value /= 100.0
        probabilities.append(
            max(0.0, min(1.0, value)) if value is not None else None
        )

    return {
        "grade_idx": grade_idx,
        "grade_name": grade_name,
        "confidence": confidence,
        "probabilities": probabilities,
        "class_probabilities": [
            {"class_name": name, "probability": probability}
            for name, probability in zip(CLASS_NAMES, probabilities)
        ],
    }


def _quality_label(score: Optional[float]) -> str:
    if score is None:
        return "Not available"
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Fair"
    return "Needs review"


def _normalise_quality(score: Any) -> Optional[float]:
    value = _finite_float(score)
    if value is None:
        return None
    return round(max(0.0, min(100.0, value)), 1)


def _normalise_attention(attention_map: Any, height: int, width: int) -> np.ndarray:
    if attention_map is None:
        return np.zeros((height, width), dtype=np.float32)
    array = np.asarray(attention_map, dtype=np.float32)
    if array.ndim == 3:
        array = np.mean(np.abs(array), axis=-1)
    if array.ndim != 2 or array.size == 0:
        return np.zeros((height, width), dtype=np.float32)
    array = np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0)
    minimum = float(array.min())
    maximum = float(array.max())
    if maximum > minimum + 1e-8:
        array = (array - minimum) / (maximum - minimum)
    else:
        array = np.zeros_like(array)
    heat = Image.fromarray(np.uint8(np.clip(array, 0.0, 1.0) * 255))
    resampling = getattr(Image, "Resampling", Image)
    heat = heat.resize((width, height), resampling.BILINEAR)
    return np.asarray(heat, dtype=np.float32) / 255.0


def _colourise_attention(attention: np.ndarray) -> Image.Image:
    """Create a dependency-light blue-to-red heatmap from a 0-1 array."""

    value = np.clip(np.asarray(attention, dtype=np.float32), 0.0, 1.0)
    red = np.clip(2.0 * value, 0.0, 1.0)
    green = np.clip(2.0 * (1.0 - np.abs(value - 0.5) * 2.0), 0.0, 1.0)
    blue = np.clip(2.0 * (1.0 - value), 0.0, 1.0)
    rgb = np.stack([red, green, blue], axis=-1)
    return Image.fromarray(np.uint8(rgb * 255.0))


def _write_preview_and_attention(
    image_bytes: bytes,
    attention_map: Any,
    preview_path: Path,
    attention_path: Path,
) -> None:
    with Image.open(io.BytesIO(image_bytes)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
    preview = image.copy()
    preview.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    preview.save(preview_path, format="JPEG", quality=92, optimize=True)

    attention = _normalise_attention(attention_map, preview.height, preview.width)
    heatmap = _colourise_attention(attention)
    overlay = Image.blend(preview, heatmap, alpha=0.45)
    overlay.save(attention_path, format="JPEG", quality=92, optimize=True)


def _report_json_path(report_id: str) -> Optional[Path]:
    return _safe_artifact_file(report_id, "report.json")


def _read_live_report(
    report_id: str,
    root: Path,
) -> Optional[tuple[Path, dict[str, Any]]]:
    """Read metadata only when the artifact is present and unexpired."""

    artifact_dir = _safe_artifact_dir(report_id, root)
    metadata_path = _safe_artifact_file(report_id, "report.json", root)
    if artifact_dir is None or metadata_path is None:
        return None

    payload = _load_report_payload(metadata_path)
    if payload is None:
        return None
    if _is_expired(payload, artifact_dir):
        try:
            shutil.rmtree(artifact_dir)
        except OSError:
            pass
        return None
    return artifact_dir, payload


def get_report_metadata(report_id: str) -> Optional[dict[str, Any]]:
    """Read report metadata without exposing its filesystem location."""

    if _safe_report_id(report_id) is None:
        return None

    root = _report_root()
    _cleanup_expired(root)
    live_report = _read_live_report(report_id, root)
    if live_report is None:
        return None
    return live_report[1]


def get_report_file(report_id: str, kind: str) -> Optional[Path]:
    """Return a fixed-name artifact path after validating the generated ID."""

    safe_id = _safe_report_id(report_id)
    filename = {
        "json": "report.json",
        "csv": "report.csv",
        "pdf": "report.pdf",
        "image": "preview.jpg",
        "attention": "attention.jpg",
    }.get(kind) if isinstance(kind, str) else None
    if safe_id is None or filename is None:
        return None

    root = _report_root()
    _cleanup_expired(root)
    if _read_live_report(safe_id, root) is None:
        return None
    return _safe_artifact_file(safe_id, filename, root)


def _xml(value: Any) -> str:
    return xml_escape(str(value)) if REPORTLAB_AVAILABLE else str(value)


def _reportlab_image(path: Path, max_width: float, max_height: float) -> Any:
    with Image.open(path) as image:
        width, height = image.size
    scale = min(max_width / max(width, 1), max_height / max(height, 1))
    return ReportLabImage(str(path), width=width * scale, height=height * scale)


def _build_reportlab_pdf(
    pdf_path: Path,
    report: Mapping[str, Any],
    preview_path: Path,
    attention_path: Path,
) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#123047"),
        alignment=TA_LEFT,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#557083"),
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#123047"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#2c4050"),
    )
    small_style = ParagraphStyle(
        "ReportSmall",
        parent=body_style,
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#557083"),
    )

    def cell(label: str, value: Any) -> Paragraph:
        return Paragraph(f"<b>{_xml(label)}</b><br/>{_xml(value)}", body_style)

    prediction = report["prediction"]
    quality = report["image_quality"]
    patient_id = report["patient_label"]
    model = report["model"]
    explanation = report["explanation"]

    document = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="RetinaScan AI diabetic retinopathy report",
        author="RetinaScan AI",
    )

    story: list[Any] = [
        Paragraph("RetinaScan AI", title_style),
        Paragraph(
            "Diabetic retinopathy screening report · clinician review required",
            subtitle_style,
        ),
    ]

    overview = [
        [cell("Patient ID", patient_id), cell("Scan date", report["scan_date"] or "Not recorded")],
        [cell("Eye", report["eye"] or "Not recorded"), cell("Report timestamp", report["timestamp"])],
        [cell("Model version", model["version"]), cell("Source image", report["filename"])],
    ]
    overview_table = Table(overview, colWidths=[3.65 * inch, 3.65 * inch], hAlign="LEFT")
    overview_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f2f7fa")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9dbe5")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8e5eb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([overview_table, Spacer(1, 10), Paragraph("Clinical image review", heading_style)])

    preview = _reportlab_image(preview_path, 3.35 * inch, 2.55 * inch)
    attention = _reportlab_image(attention_path, 3.35 * inch, 2.55 * inch)
    image_table = Table(
        [
            [
                Paragraph("<b>Image preview</b>", body_style),
                Paragraph("<b>Model attention map</b>", body_style),
            ],
            [preview, attention],
            [
                Paragraph("Original uploaded image", small_style),
                Paragraph(_xml(explanation["method"]), small_style),
            ],
        ],
        colWidths=[3.65 * inch, 3.65 * inch],
        hAlign="LEFT",
    )
    image_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf3f6")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9dbe5")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8e5eb")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(image_table)

    story.append(Paragraph("AI screening result", heading_style))
    grade = f"{prediction['grade_name']} (Grade {prediction['grade_idx']})"
    result_table = Table(
        [
            [cell("Predicted DR grade", grade), cell("Confidence", f"{prediction['confidence'] * 100:.1f}%")],
            [cell("Image quality", f"{quality['score'] if quality['score'] is not None else 'Not available'} / 100 ({quality['label']})"), cell("Model", model["version"])],
        ],
        colWidths=[3.65 * inch, 3.65 * inch],
        hAlign="LEFT",
    )
    result_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fbfc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9dbe5")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8e5eb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(result_table)

    story.append(Paragraph("Class probabilities", heading_style))
    probability_rows = [["Class", "Probability"]]
    for item in prediction["class_probabilities"]:
        probability = item["probability"]
        probability_rows.append(
            [item["class_name"], "Not available" if probability is None else f"{probability * 100:.2f}%"]
        )
    probability_table = Table(probability_rows, colWidths=[5.3 * inch, 2.0 * inch], hAlign="LEFT")
    probability_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123047")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c9dbe5")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f7fa")]),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(probability_table)

    story.append(Paragraph("Review and sign-off", heading_style))
    review_table = Table(
        [
            [cell("Clinician name", "____________________________________________")],
            [cell("Clinician signature", "____________________________________________")],
            [cell("Review date", "____________________")],
        ],
        colWidths=[7.3 * inch],
        hAlign="LEFT",
    )
    review_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fbfc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9dbe5")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d8e5eb")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(review_table)
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>Clinical disclaimer:</b> {_xml(CLINICAL_DISCLAIMER)}", small_style))

    def footer(canvas: Any, document: Any) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#c9dbe5"))
        canvas.line(0.55 * inch, 0.42 * inch, 8.0 * inch, 0.42 * inch)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#557083"))
        canvas.drawString(0.55 * inch, 0.27 * inch, "RetinaScan AI · AI screening support")
        canvas.drawRightString(8.0 * inch, 0.27 * inch, f"Page {document.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except (OSError, IOError):
        return ImageFont.load_default()


def _draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], width: int, font: ImageFont.ImageFont, fill: str = "#253746") -> int:
    line_height = max(16, int(font.getbbox("Ag")[3] - font.getbbox("Ag")[1] + 5))
    lines = textwrap.wrap(str(text), width=max(20, width // max(1, int(font.size * 0.55))))
    y = xy[1]
    for line in lines:
        draw.text((xy[0], y), line, font=font, fill=fill)
        y += line_height
    return y


def _build_fallback_pdf(pdf_path: Path, report: Mapping[str, Any], preview_path: Path, attention_path: Path) -> None:
    """Produce a valid image-based PDF when ReportLab is unavailable."""

    page = Image.new("RGB", (1275, 1650), "white")
    draw = ImageDraw.Draw(page)
    title_font = _font(34)
    heading_font = _font(21)
    body_font = _font(16)
    small_font = _font(13)
    margin = 70
    draw.text((margin, 55), "RetinaScan AI", font=title_font, fill="#123047")
    draw.text((margin, 105), "Diabetic retinopathy screening report · clinician review required", font=small_font, fill="#557083")
    draw.line((margin, 140, page.width - margin, 140), fill="#c9dbe5", width=2)

    report_prediction = report["prediction"]
    quality = report["image_quality"]
    model = report["model"]
    lines = [
        f"Patient ID: {report['patient_label']}    Scan date: {report['scan_date'] or 'Not recorded'}",
        f"Eye: {report['eye'] or 'Not recorded'}    Timestamp: {report['timestamp']}",
        f"Model version: {model['version']}    Source image: {report['filename']}",
        f"Predicted DR grade: {report_prediction['grade_name']} (Grade {report_prediction['grade_idx']})",
        f"Confidence: {report_prediction['confidence'] * 100:.1f}%",
        f"Image quality: {quality['score'] if quality['score'] is not None else 'Not available'} / 100 ({quality['label']})",
    ]
    y = 175
    for line in lines:
        y = _draw_wrapped(draw, line, (margin, y), page.width - 2 * margin, body_font) + 3

    draw.text((margin, y + 10), "Image preview", font=heading_font, fill="#123047")
    y += 50
    with Image.open(preview_path) as source:
        preview = source.convert("RGB")
    preview.thumbnail((500, 360), Image.Resampling.LANCZOS)
    page.paste(preview, (margin, y))
    draw.text((650, y), "Model attention map", font=heading_font, fill="#123047")
    with Image.open(attention_path) as source:
        attention = source.convert("RGB")
    attention.thumbnail((500, 360), Image.Resampling.LANCZOS)
    page.paste(attention, (650, y + 45))
    y += 390

    draw.text((margin, y), "Class probabilities", font=heading_font, fill="#123047")
    y += 35
    for item in report_prediction["class_probabilities"]:
        probability = item["probability"]
        value = "Not available" if probability is None else f"{probability * 100:.2f}%"
        draw.text((margin, y), f"{item['class_name']}: {value}", font=body_font, fill="#253746")
        y += 25
    y += 15
    draw.text((margin, y), "Review and sign-off", font=heading_font, fill="#123047")
    y += 35
    for label in ("Clinician name", "Clinician signature", "Review date"):
        draw.text((margin, y), f"{label}: ______________________________________________", font=body_font, fill="#253746")
        y += 34
    y += 10
    _draw_wrapped(draw, f"Clinical disclaimer: {CLINICAL_DISCLAIMER}", (margin, y), page.width - 2 * margin, small_font, "#557083")
    page.save(pdf_path, format="PDF", resolution=150.0)


def _build_pdf(pdf_path: Path, report: Mapping[str, Any], preview_path: Path, attention_path: Path) -> None:
    if REPORTLAB_AVAILABLE:
        _build_reportlab_pdf(pdf_path, report, preview_path, attention_path)
    else:
        _build_fallback_pdf(pdf_path, report, preview_path, attention_path)


def _csv_row(report: Mapping[str, Any]) -> dict[str, Any]:
    prediction = report["prediction"]
    probabilities = prediction["probabilities"]
    row: dict[str, Any] = {
        "report_id": report["report_id"],
        "timestamp": report["timestamp"],
        "patient_id": report["patient_id"] or "",
        "patient_label": report["patient_label"],
        "scan_id": report["scan_id"] if report["scan_id"] is not None else "",
        "saved_to_patient": report["saved_to_patient"],
        "scan_date": report["scan_date"] or "",
        "eye": report["eye"] or "",
        "filename": report["filename"],
        "model_version": report["model"]["version"],
        "grade_idx": prediction["grade_idx"],
        "grade_name": prediction["grade_name"],
        "confidence": prediction["confidence"],
        "image_quality_score": report["image_quality"]["score"] if report["image_quality"]["score"] is not None else "",
        "image_quality_label": report["image_quality"]["label"],
        "explanation_method": report["explanation"]["method"],
        "clinical_disclaimer": report["clinical_disclaimer"],
        "clinician_name": "",
        "clinician_signature": "",
        "clinician_review_date": "",
    }
    for index, name in enumerate(CLASS_NAMES):
        key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        row[f"probability_{key}"] = probabilities[index] if index < len(probabilities) and probabilities[index] is not None else ""
    return row


def create_report_artifact(
    *,
    image_bytes: bytes,
    original_filename: Optional[str],
    prediction: Mapping[str, Any],
    patient_id: Optional[str],
    scan_id: Optional[int],
    scan_date: Optional[str],
    eye: Optional[str],
    notes: Optional[str],
    image_quality_score: Any,
    attention_map: Any,
    explanation_method: str,
    model_version: str,
    created_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Create all report formats and return frontend-safe metadata."""

    now = created_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    report_id = uuid4().hex
    root = _report_root()
    root.mkdir(parents=True, exist_ok=True)
    _cleanup_expired(root, now)
    artifact_dir = root / report_id
    artifact_dir.mkdir(mode=0o700)

    safe_filename = _safe_display_filename(original_filename)
    normalised_prediction = _normalise_prediction(prediction)
    quality_score = _normalise_quality(image_quality_score)
    urls = _artifact_urls(report_id)
    expires_at = now + timedelta(seconds=_ttl_seconds())
    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": report_id,
        "artifact_id": report_id,
        "report_artifact_id": report_id,
        "created_at": now.isoformat(),
        "timestamp": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "patient_id": str(patient_id).strip() if patient_id is not None else None,
        "patient_label": str(patient_id).strip() if patient_id is not None and str(patient_id).strip() else "Not assigned",
        "scan_id": int(scan_id) if scan_id is not None else None,
        "saved_to_patient": scan_id is not None,
        "scan_date": str(scan_date).strip() if scan_date else None,
        "eye": str(eye).strip() if eye else None,
        "filename": safe_filename,
        "notes": str(notes).strip()[:2000] if notes else None,
        "model": {
            "name": "EfficientNet-B4-NS",
            "version": str(model_version or "EfficientNet-B4-NS"),
            "input_size": "380x380",
        },
        "prediction": normalised_prediction,
        "predicted_grade": normalised_prediction["grade_name"],
        "predicted_grade_index": normalised_prediction["grade_idx"],
        "confidence": normalised_prediction["confidence"],
        "probabilities": normalised_prediction["probabilities"],
        "image_quality": {
            "score": quality_score,
            "label": _quality_label(quality_score),
        },
        "image_quality_score": quality_score,
        "model_version": str(model_version or "EfficientNet-B4-NS"),
        "explanation": {
            "method": str(explanation_method or "Attention map fallback"),
            "description": "Heatmap indicates image regions that contributed most to the model screening signal; it is not a lesion segmentation or diagnosis.",
        },
        "clinical_disclaimer": CLINICAL_DISCLAIMER,
        "clinician_review": {
            "name": "",
            "signature": "",
            "date": "",
        },
        "urls": urls,
        "metadata_url": urls["metadata"],
        "json_url": urls["json"],
        "csv_url": urls["csv"],
        "pdf_url": urls["pdf"],
        "preview_url": urls["preview"],
        "image_url": urls["image"],
        "attention_url": urls["attention"],
        "gradcam_url": urls["attention"],
        "explanation_url": urls["explanation"],
        "explanation_image_url": urls["explanation"],
        "download_urls": {
            "pdf": urls["pdf"],
            "json": urls["json"],
            "csv": urls["csv"],
        },
    }

    preview_path = artifact_dir / "preview.jpg"
    attention_path = artifact_dir / "attention.jpg"
    json_path = artifact_dir / "report.json"
    csv_path = artifact_dir / "report.csv"
    pdf_path = artifact_dir / "report.pdf"
    try:
        _write_preview_and_attention(image_bytes, attention_map, preview_path, attention_path)
        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)

        row = _csv_row(report)
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
            writer.writeheader()
            writer.writerow(row)

        _build_pdf(pdf_path, report, preview_path, attention_path)
    except Exception:
        shutil.rmtree(artifact_dir, ignore_errors=True)
        raise

    return report
