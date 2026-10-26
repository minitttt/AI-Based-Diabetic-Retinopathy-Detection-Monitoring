import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1] / "deployment" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import db


class DatabasePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "monitoring.sqlite3"
        self.upload_dir = Path(self.temp_dir.name) / "uploads"
        self.environment = patch.dict(
            os.environ,
            {
                "RETINASCAN_DB_PATH": str(self.db_path),
                "RETINASCAN_UPLOAD_DIR": str(self.upload_dir),
            },
            clear=False,
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp_dir.cleanup()

    def test_patient_and_scan_round_trip_uses_temp_database(self):
        db.initialize_database()
        patient = db.create_patient(
            name="Synthetic Patient",
            age=61,
            gender="F",
            diabetes_type="Type 2",
            patient_id=" P007 ",
        )

        self.assertEqual(patient["patient_id"], "P007")
        self.assertTrue(self.db_path.is_file())
        self.assertTrue(db.patient_exists("P007"))

        scan_id = db.insert_scan(
            patient_id="P007",
            scan_date="2026-02-03",
            eye="left",
            image_filename="/private/uploads/generated-image.jpg",
            notes="synthetic scan",
            prediction={
                "grade_idx": 2,
                "grade_name": "Moderate",
                "confidence": 0.81,
                "probabilities": [0.02, 0.03, 0.81, 0.10, 0.04],
            },
        )

        scans = db.get_scans("P007")
        self.assertEqual(len(scans), 1)
        self.assertEqual(scans[0]["scan_id"], scan_id)
        self.assertEqual(scans[0]["image_filename"], "generated-image.jpg")
        self.assertEqual(scans[0]["predicted_grade"], 2)
        self.assertEqual(scans[0]["probabilities"], [0.02, 0.03, 0.81, 0.10, 0.04])

        summary = db.get_patient_summary("P007")
        self.assertIsNotNone(summary)
        self.assertEqual(summary["scan_count"], 1)
        self.assertEqual(summary["last_scan_date"], "2026-02-03")
        self.assertEqual(summary["last_grade"], 2)
        self.assertEqual(summary["last_label"], "Moderate")
        self.assertEqual(db.progression(scans)["trend"], "stable")

        # A fresh connection sees the same rows, proving persistence beyond one call.
        self.assertEqual(db.list_patients()[0]["patient_id"], "P007")

    def test_generated_patient_ids_and_duplicate_ids_are_safe(self):
        first = db.create_patient(name="First Synthetic Patient")
        second = db.create_patient(name="Second Synthetic Patient")

        self.assertEqual(first["patient_id"], "P001")
        self.assertEqual(second["patient_id"], "P002")

        with self.assertRaises(db.DuplicatePatientError):
            db.create_patient(name="Duplicate", patient_id=" P001 ")

    def test_progression_reports_ordinal_change(self):
        scans = [
            {"predicted_grade": 3, "scan_date": "2026-01-01"},
            {"predicted_grade": 1, "scan_date": "2026-03-01"},
        ]

        self.assertEqual(
            db.progression(scans),
            {
                "baseline_grade": 3,
                "current_grade": 1,
                "change": -2,
                "trend": "improving",
                "latest_date": "2026-03-01",
                "scan_count": 2,
            },
        )
        self.assertEqual(db.progression([])["trend"], "stable")


if __name__ == "__main__":
    unittest.main()
