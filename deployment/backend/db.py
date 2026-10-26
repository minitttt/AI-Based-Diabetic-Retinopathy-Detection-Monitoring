"""Small SQLite persistence layer for patient profiles and scan history.

The database lives beside the repository by default so starting the API from a
different working directory does not create a second, empty database.  The
``RETINASCAN_DB_PATH`` environment variable can be used by deployments and
tests that need a different database file.
"""

from __future__ import annotations

import math
import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping, Optional


BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "monitoring.db"
DEFAULT_UPLOAD_DIR = BACKEND_DIR / "uploads"

PROBABILITY_COLUMNS = (
    "conf_no_dr",
    "conf_mild",
    "conf_moderate",
    "conf_severe",
    "conf_pdr",
)


class DuplicatePatientError(Exception):
    """Raised when a caller tries to create an existing patient ID."""


def get_db_path() -> Path:
    """Return the configured database path, anchored to the repository."""

    configured = os.getenv("RETINASCAN_DB_PATH")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path.resolve()
    return DEFAULT_DB_PATH


def get_upload_dir() -> Path:
    """Return the local directory used for images attached to saved scans."""

    configured = os.getenv("RETINASCAN_UPLOAD_DIR")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path.resolve()
    return DEFAULT_UPLOAD_DIR


def _open_connection() -> sqlite3.Connection:
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    # Table names are fixed constants at every call site; values remain
    # parameterized in all data queries below.
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table_name}")')
    }


def initialize_database() -> None:
    """Create missing tables and apply additive migrations safely.

    Existing patient and scan rows are never replaced.  In particular, older
    databases may not have ``scans.eye``; the column is added as nullable so
    those historical rows remain valid.
    """

    connection = _open_connection()
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                patient_id    TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                age           INTEGER,
                gender        TEXT,
                diabetes_type TEXT,
                created_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
                scan_id         INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id      TEXT NOT NULL,
                scan_date       TEXT NOT NULL,
                eye             TEXT,
                image_path      TEXT,
                predicted_grade INTEGER NOT NULL,
                predicted_label TEXT NOT NULL,
                confidence      REAL NOT NULL,
                conf_no_dr      REAL,
                conf_mild       REAL,
                conf_moderate   REAL,
                conf_severe     REAL,
                conf_pdr        REAL,
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            )
            """
        )

        # The repository's existing database predates eye tracking.  This is
        # intentionally an ALTER, rather than a table rebuild, to preserve all
        # existing scan IDs and data.
        if "eye" not in _table_columns(connection, "scans"):
            try:
                connection.execute("ALTER TABLE scans ADD COLUMN eye TEXT")
            except sqlite3.OperationalError as exc:
                # Two workers can initialize at the same time.  If the other
                # worker won the ALTER race, the desired schema is already in
                # place; surface all other migration errors.
                if "duplicate column name" not in str(exc).lower():
                    raise

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_scans_patient_date "
            "ON scans(patient_id, scan_date, scan_id)"
        )
        connection.commit()
    finally:
        connection.close()


@contextmanager
def _session() -> Iterator[sqlite3.Connection]:
    initialize_database()
    connection = _open_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _patient_id_number(patient_id: str) -> Optional[int]:
    match = re.fullmatch(r"P(\d+)", patient_id.strip(), flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def _next_patient_id(connection: sqlite3.Connection) -> str:
    largest = 0
    for row in connection.execute("SELECT patient_id FROM patients"):
        number = _patient_id_number(str(row[0]))
        if number is not None:
            largest = max(largest, number)
    return f"P{largest + 1:03d}"


def _base_patient(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "patient_id": str(row["patient_id"]),
        "name": row["name"],
        "age": int(row["age"]) if row["age"] is not None else None,
        "gender": row["gender"],
        "diabetes_type": row["diabetes_type"],
        "created_at": row["created_at"],
    }


def _patient_summary_row_sql() -> str:
    return """
        SELECT
            p.patient_id,
            p.name,
            p.age,
            p.gender,
            p.diabetes_type,
            p.created_at,
            COUNT(s.scan_id) AS scan_count,
            (
                SELECT s2.scan_date
                FROM scans AS s2
                WHERE s2.patient_id = p.patient_id
                ORDER BY s2.scan_date DESC, s2.scan_id DESC
                LIMIT 1
            ) AS last_scan_date,
            (
                SELECT s3.predicted_grade
                FROM scans AS s3
                WHERE s3.patient_id = p.patient_id
                ORDER BY s3.scan_date DESC, s3.scan_id DESC
                LIMIT 1
            ) AS last_grade,
            (
                SELECT s4.predicted_label
                FROM scans AS s4
                WHERE s4.patient_id = p.patient_id
                ORDER BY s4.scan_date DESC, s4.scan_id DESC
                LIMIT 1
            ) AS last_label
        FROM patients AS p
        LEFT JOIN scans AS s ON s.patient_id = p.patient_id
    """


def _patient_summary(row: sqlite3.Row) -> dict[str, Any]:
    patient = _base_patient(row)
    patient.update(
        {
            "scan_count": int(row["scan_count"] or 0),
            "last_scan_date": row["last_scan_date"],
            "last_grade": (
                int(row["last_grade"])
                if row["last_grade"] is not None
                else None
            ),
            "last_label": row["last_label"],
        }
    )
    return patient


def create_patient(
    *,
    name: str,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    diabetes_type: Optional[str] = None,
    patient_id: Optional[str] = None,
) -> dict[str, Any]:
    """Insert a patient and return its persisted base profile."""

    with _session() as connection:
        # Serializes generated-ID selection with another creator, while still
        # allowing callers to provide their own human-readable IDs.
        connection.execute("BEGIN IMMEDIATE")
        normalized_id = patient_id.strip() if patient_id is not None else None
        if not normalized_id:
            normalized_id = _next_patient_id(connection)
        try:
            connection.execute(
                """
                INSERT INTO patients
                    (patient_id, name, age, gender, diabetes_type)
                VALUES (?, ?, ?, ?, ?)
                """,
                (normalized_id, name, age, gender, diabetes_type),
            )
        except sqlite3.IntegrityError as exc:
            if "unique" in str(exc).lower() or "primary key" in str(exc).lower():
                raise DuplicatePatientError(normalized_id) from exc
            raise

        row = connection.execute(
            """
            SELECT patient_id, name, age, gender, diabetes_type, created_at
            FROM patients
            WHERE patient_id = ?
            """,
            (normalized_id,),
        ).fetchone()
        if row is None:  # pragma: no cover - guarded by the INSERT above
            raise RuntimeError("Patient was inserted but could not be read back")
        return _base_patient(row)


def patient_exists(patient_id: str) -> bool:
    """Return whether a patient ID is present in the database."""

    with _session() as connection:
        row = connection.execute(
            "SELECT 1 FROM patients WHERE patient_id = ? LIMIT 1", (patient_id,)
        ).fetchone()
        return row is not None


def list_patients() -> list[dict[str, Any]]:
    """Return patient profiles with their latest scan summary."""

    with _session() as connection:
        rows = connection.execute(
            _patient_summary_row_sql()
            + " GROUP BY p.patient_id ORDER BY p.created_at ASC, p.patient_id ASC"
        ).fetchall()
        return [_patient_summary(row) for row in rows]


def get_patient_summary(patient_id: str) -> Optional[dict[str, Any]]:
    """Return one patient summary, or ``None`` when it does not exist."""

    with _session() as connection:
        row = connection.execute(
            _patient_summary_row_sql()
            + " WHERE p.patient_id = ? GROUP BY p.patient_id",
            (patient_id,),
        ).fetchone()
        return _patient_summary(row) if row is not None else None


def _safe_image_filename(image_path: Any) -> Optional[str]:
    if image_path is None:
        return None
    raw = str(image_path).replace("\\", "/")
    filename = PurePosixPath(raw).name
    return filename or None


def _json_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _scan_dict(row: sqlite3.Row) -> dict[str, Any]:
    probabilities = [_json_float(row[column]) for column in PROBABILITY_COLUMNS]
    grade = int(row["predicted_grade"])
    label = str(row["predicted_label"])
    return {
        "scan_id": int(row["scan_id"]),
        "patient_id": str(row["patient_id"]),
        "scan_date": row["scan_date"],
        "eye": row["eye"],
        # Only a generated basename is returned; the server's filesystem path
        # never crosses the API boundary.
        "image_filename": _safe_image_filename(row["image_path"]),
        "predicted_grade": grade,
        "predicted_label": label,
        "grade_idx": grade,
        "grade_name": label,
        "confidence": _json_float(row["confidence"]),
        "probabilities": probabilities,
        "conf_no_dr": probabilities[0],
        "conf_mild": probabilities[1],
        "conf_moderate": probabilities[2],
        "conf_severe": probabilities[3],
        "conf_pdr": probabilities[4],
        "notes": row["notes"],
        "created_at": row["created_at"],
    }


def get_scans(patient_id: str) -> list[dict[str, Any]]:
    """Return a patient's scans in chronological order."""

    with _session() as connection:
        rows = connection.execute(
            """
            SELECT scan_id, patient_id, scan_date, eye, image_path,
                   predicted_grade, predicted_label, confidence,
                   conf_no_dr, conf_mild, conf_moderate, conf_severe, conf_pdr,
                   notes, created_at
            FROM scans
            WHERE patient_id = ?
            ORDER BY scan_date ASC, scan_id ASC
            """,
            (patient_id,),
        ).fetchall()
        return [_scan_dict(row) for row in rows]


def insert_scan(
    *,
    patient_id: str,
    scan_date: str,
    eye: Optional[str],
    image_filename: Optional[str],
    notes: Optional[str],
    prediction: Mapping[str, Any],
) -> int:
    """Persist a prediction and its per-class probabilities for a patient."""

    grade = int(prediction["grade_idx"])
    label = str(prediction["grade_name"])
    confidence = float(prediction["confidence"])
    probabilities = list(prediction.get("probabilities") or [])
    probabilities = (probabilities + [None] * len(PROBABILITY_COLUMNS))[
        : len(PROBABILITY_COLUMNS)
    ]

    with _session() as connection:
        cursor = connection.execute(
            """
            INSERT INTO scans (
                patient_id, scan_date, eye, image_path,
                predicted_grade, predicted_label, confidence,
                conf_no_dr, conf_mild, conf_moderate, conf_severe, conf_pdr,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                scan_date,
                eye,
                image_filename,
                grade,
                label,
                confidence,
                *probabilities,
                notes,
            ),
        )
        return int(cursor.lastrowid)


def progression(scans: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute ordinal baseline-to-latest change and its direction."""

    if not scans:
        return {
            "baseline_grade": None,
            "current_grade": None,
            "change": 0,
            "trend": "stable",
            "latest_date": None,
            "scan_count": 0,
        }

    baseline_grade = int(scans[0]["predicted_grade"])
    current_grade = int(scans[-1]["predicted_grade"])
    change = current_grade - baseline_grade
    trend = "worsening" if change > 0 else "improving" if change < 0 else "stable"
    return {
        "baseline_grade": baseline_grade,
        "current_grade": current_grade,
        "change": change,
        "trend": trend,
        "latest_date": scans[-1]["scan_date"],
        "scan_count": len(scans),
    }
