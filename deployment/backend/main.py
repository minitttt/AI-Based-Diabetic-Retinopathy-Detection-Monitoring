from datetime import date
from pathlib import Path
from pathlib import PurePosixPath
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import db
from utils import compute_image_quality_score, decode_image, load_and_preprocess
from inference import get_model_version, load_model, predict_with_explanation
from reporting import create_report_artifact, get_report_file, get_report_metadata
import uvicorn
from contextlib import asynccontextmanager


class PatientCreate(BaseModel):
    """JSON payload accepted when registering a patient profile."""

    patient_id: Optional[str] = None
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    diabetes_type: Optional[str] = None


def _normalise_patient_id(patient_id: Optional[str]) -> Optional[str]:
    if patient_id is None:
        return None
    normalized = str(patient_id).strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="patient_id cannot be blank")
    return normalized


def _normalise_scan_date(scan_date: Optional[str]) -> str:
    if scan_date is None or not str(scan_date).strip():
        return date.today().isoformat()
    value = str(scan_date).strip()
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="scan_date must be an ISO date in YYYY-MM-DD format",
        ) from exc


def _parse_boolean(value: object, *, default: bool) -> bool:
    """Parse common HTML/form boolean spellings without accepting ambiguity."""

    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise HTTPException(
        status_code=400,
        detail="save_scan must be a boolean value",
    )


def _store_uploaded_image(contents: bytes, original_filename: Optional[str]) -> str:
    """Write an attached image under a generated basename and return that name."""

    suffix = Path(original_filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        suffix = ".img"
    filename = f"{uuid4().hex}{suffix}"
    upload_dir = db.get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / filename).write_bytes(contents)
    return filename


def _safe_upload_filename(filename: Optional[str]) -> str:
    raw = str(filename or "").replace("\\", "/")
    safe = PurePosixPath(raw).name
    safe = " ".join(safe.replace("\x00", "").split())
    return safe[:255] or "fundus_image"


def _remove_uploaded_image(filename: Optional[str]) -> None:
    if not filename:
        return
    try:
        (db.get_upload_dir() / filename).unlink()
    except FileNotFoundError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.initialize_database()
    print("Loading model...")
    load_model()
    yield
    print("Shutting down...")

app = FastAPI(title="DR Detection API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "DR Detection API is running"}


@app.get("/patients")
def get_patients():
    """List profiles and the latest saved-scan summary for each patient."""

    return {"patients": db.list_patients()}


@app.post("/patients", status_code=201)
def create_patient(payload: PatientCreate):
    """Create a patient, generating a stable P### ID when omitted."""

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name cannot be blank")

    provided_id = payload.patient_id is not None
    patient_id = _normalise_patient_id(payload.patient_id)
    if provided_id and patient_id is None:  # Defensive; handled above.
        raise HTTPException(status_code=400, detail="patient_id cannot be blank")

    def clean_optional(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    try:
        return db.create_patient(
            patient_id=patient_id,
            name=name,
            age=payload.age,
            gender=clean_optional(payload.gender),
            diabetes_type=clean_optional(payload.diabetes_type),
        )
    except db.DuplicatePatientError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"patient_id already exists: {exc}",
        ) from exc


@app.get("/patients/{patient_id}/scans")
def get_patient_scans(patient_id: str):
    """Return all scans for one patient in chronological order."""

    patient_id = _normalise_patient_id(patient_id)
    if patient_id is None or not db.patient_exists(patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"scans": db.get_scans(patient_id)}


@app.get("/patients/{patient_id}")
def get_patient(patient_id: str):
    """Return a patient, scan history, and ordinal progression summary."""

    patient_id = _normalise_patient_id(patient_id)
    if patient_id is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient = db.get_patient_summary(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    scans = db.get_scans(patient_id)
    return {
        "patient": patient,
        "scans": scans,
        "progression": db.progression(scans),
    }


def _report_download(report_id: str, kind: str, media_type: str, extension: str):
    path = get_report_file(report_id, kind)
    if path is None:
        raise HTTPException(status_code=404, detail="Report artifact not found or expired")
    # get_report_file validates the ID and only returns fixed names.  Keeping
    # the download name generated from that ID avoids leaking server paths.
    safe_id = str(report_id).strip().lower()
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=f"retinascan_report_{safe_id}.{extension}",
    )


@app.get("/reports/{report_id}/json")
def get_report_json(report_id: str):
    return _report_download(report_id, "json", "application/json", "json")


@app.get("/reports/{report_id}/csv")
def get_report_csv(report_id: str):
    return _report_download(report_id, "csv", "text/csv", "csv")


@app.get("/reports/{report_id}/pdf")
def get_report_pdf(report_id: str):
    return _report_download(report_id, "pdf", "application/pdf", "pdf")


@app.get("/reports/{report_id}/image")
def get_report_image(report_id: str):
    return _report_download(report_id, "image", "image/jpeg", "jpg")


@app.get("/reports/{report_id}/attention")
def get_report_attention(report_id: str):
    return _report_download(report_id, "attention", "image/jpeg", "jpg")


@app.get("/reports/{report_id}")
def get_report(report_id: str):
    report = get_report_metadata(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report artifact not found or expired")
    return report


@app.post("/predict")
async def predict_image(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    scan_date: Optional[str] = Form(None),
    eye: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    save_scan: Optional[str] = Form(None),
):
    """Predict an image, optionally attaching the result to a patient."""

    normalized_patient_id = _normalise_patient_id(patient_id)
    normalized_date = _normalise_scan_date(scan_date)
    save_requested = _parse_boolean(
        save_scan,
        default=normalized_patient_id is not None,
    )
    if normalized_patient_id is not None and not db.patient_exists(normalized_patient_id):
        raise HTTPException(status_code=404, detail="Patient not found")

    contents = await file.read()
    try:
        source_image = decode_image(contents)
        image_quality_score = compute_image_quality_score(source_image)
        img_np = load_and_preprocess(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result, attention_map, explanation_method = predict_with_explanation(img_np)

    # A patient ID opts into persistence by default.  An explicit
    # save_scan=false is useful for previewing a prediction before committing
    # it; legacy file-only callers remain stateless.
    should_save = normalized_patient_id is not None and save_requested
    normalized_eye = eye.strip() if eye and eye.strip() else None
    normalized_notes = notes.strip() if notes and notes.strip() else None
    stored_filename: Optional[str] = None
    scan_id: Optional[int] = None
    try:
        if should_save:
            stored_filename = _store_uploaded_image(contents, file.filename)
            scan_id = db.insert_scan(
                patient_id=normalized_patient_id,
                scan_date=normalized_date,
                eye=normalized_eye,
                image_filename=stored_filename,
                notes=normalized_notes,
                prediction=result,
            )
    except OSError as exc:
        _remove_uploaded_image(stored_filename)
        raise HTTPException(status_code=500, detail="Could not store the scan image") from exc
    except Exception:
        _remove_uploaded_image(stored_filename)
        raise

    scan_metadata = None
    if normalized_patient_id is not None:
        scan_metadata = {
            "scan_id": scan_id,
            "patient_id": normalized_patient_id,
            "scan_date": normalized_date,
            "eye": normalized_eye,
            "saved": should_save,
        }

    try:
        report = create_report_artifact(
            image_bytes=contents,
            original_filename=file.filename,
            prediction=result,
            patient_id=normalized_patient_id,
            scan_id=scan_id,
            scan_date=normalized_date,
            eye=normalized_eye,
            notes=normalized_notes,
            image_quality_score=image_quality_score,
            attention_map=attention_map,
            explanation_method=explanation_method,
            model_version=get_model_version(),
        )
    except Exception as exc:
        # Persistence remains intact for saved scans, but report creation is a
        # required part of the analysis contract, so surface a clear API error.
        raise HTTPException(status_code=500, detail="Could not create the report artifact") from exc

    response = {
        "filename": _safe_upload_filename(file.filename),
        "prediction": result,
        "saved": should_save,
        "scan": scan_metadata,
        "report_id": report["report_id"],
        "report_artifact_id": report["report_id"],
        "report": report,
        "report_urls": report["urls"],
    }
    if scan_metadata is not None:
        scan_metadata["report_id"] = report["report_id"]
        response.update(scan_metadata)
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
