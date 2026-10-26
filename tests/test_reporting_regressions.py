import csv
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image


BACKEND_DIR = Path(__file__).resolve().parents[1] / "deployment" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import reporting


def _image_bytes() -> bytes:
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    image[..., 0] = np.arange(64, dtype=np.uint8)[None, :]
    image[..., 1] = 80
    image[..., 2] = 150
    buffer = io.BytesIO()
    Image.fromarray(image).save(buffer, format="PNG")
    return buffer.getvalue()


class ReportArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.report_dir = Path(self.temp_dir.name) / "reports"
        self.environment = patch.dict(
            os.environ,
            {
                "RETINASCAN_REPORT_DIR": str(self.report_dir),
                "RETINASCAN_REPORT_TTL_SECONDS": "3600",
            },
            clear=False,
        )
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temp_dir.cleanup()

    def _create_report(self, *, created_at=None, prediction=None):
        created_at = created_at or datetime.now(timezone.utc)
        return reporting.create_report_artifact(
            image_bytes=_image_bytes(),
            original_filename="../../incoming\\ fundus   image.png",
            prediction=prediction
            or {
                "grade_idx": "99",
                "grade_name": "",
                "confidence": 125,
                "probabilities": [0.25, 25, -1, float("nan"), 2],
            },
            patient_id=" P007 ",
            scan_id=12,
            scan_date=" 2026-02-03 ",
            eye=" left ",
            notes="  synthetic notes  ",
            image_quality_score=125,
            attention_map=np.array([[0.0, 1.0], [0.5, np.nan]], dtype=np.float32),
            explanation_method="",
            model_version="",
            created_at=created_at,
        )

    def test_generates_all_artifacts_and_normalizes_metadata(self):
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        report = self._create_report(created_at=created_at)

        report_id = report["report_id"]
        artifact_dir = self.report_dir / report_id
        self.assertRegex(report_id, r"^[0-9a-f]{32}$")
        self.assertEqual(
            {path.name for path in artifact_dir.iterdir()},
            {"preview.jpg", "attention.jpg", "report.json", "report.csv", "report.pdf"},
        )

        self.assertEqual(report["patient_id"], "P007")
        self.assertEqual(report["patient_label"], "P007")
        self.assertEqual(report["filename"], "fundus image.png")
        self.assertEqual(report["scan_date"], "2026-02-03")
        self.assertEqual(report["eye"], "left")
        self.assertEqual(report["notes"], "synthetic notes")
        self.assertEqual(report["prediction"]["grade_idx"], 4)
        self.assertEqual(report["prediction"]["grade_name"], "Proliferative")
        self.assertEqual(report["prediction"]["confidence"], 1.0)
        self.assertEqual(
            report["prediction"]["probabilities"], [0.25, 0.25, 0.0, None, 0.02]
        )
        self.assertEqual(report["image_quality"], {"score": 100.0, "label": "Good"})
        self.assertEqual(report["model"]["version"], "EfficientNet-B4-NS")
        self.assertEqual(report["explanation"]["method"], "Attention map fallback")
        self.assertEqual(report["saved_to_patient"], True)
        self.assertEqual(
            report["expires_at"],
            (created_at + timedelta(hours=1)).isoformat(),
        )

        loaded = reporting.get_report_metadata(report_id)
        self.assertEqual(loaded, report)
        with (artifact_dir / "report.json").open(encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), report)
        with (artifact_dir / "report.csv").open(newline="", encoding="utf-8") as handle:
            csv_row = next(csv.DictReader(handle))
        self.assertEqual(csv_row["report_id"], report_id)
        self.assertEqual(csv_row["grade_idx"], "4")
        self.assertEqual(csv_row["probability_no_dr"], "0.25")
        self.assertGreater((artifact_dir / "report.pdf").stat().st_size, 0)

    def test_expired_artifacts_are_removed_on_next_report_creation(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        first = self._create_report(created_at=now - timedelta(hours=2))
        first_dir = self.report_dir / first["report_id"]
        old_timestamp = (now - timedelta(hours=2)).timestamp()
        os.utime(first_dir, (old_timestamp, old_timestamp))
        self.assertIsNone(reporting.get_report_metadata(first["report_id"]))

        second = self._create_report(created_at=now)

        self.assertIsNone(reporting.get_report_metadata(first["report_id"]))
        self.assertFalse(first_dir.exists())
        self.assertIsNotNone(reporting.get_report_metadata(second["report_id"]))

    def test_report_ids_and_artifact_paths_are_fail_closed(self):
        report = self._create_report(
            prediction={
                "grade_idx": 1,
                "grade_name": "Mild",
                "confidence": 0.5,
                "probabilities": [0, 0.5, 0, 0, 0],
            }
        )
        report_id = report["report_id"]

        json_path = reporting.get_report_file(report_id, "json")
        self.assertEqual(
            json_path, self.report_dir.resolve() / report_id / "report.json"
        )
        self.assertIsNone(reporting.get_report_file("../" + report_id, "json"))
        self.assertIsNone(reporting.get_report_file("not-a-report", "json"))
        self.assertIsNone(reporting.get_report_file(report_id, "../../etc/passwd"))
        self.assertIsNone(reporting.get_report_metadata("../../etc/passwd"))
        with self.assertRaises(ValueError):
            reporting._artifact_urls("../" + report_id)

        urls = report["urls"]
        self.assertTrue(all(url.startswith(f"/reports/{report_id}/") or url == f"/reports/{report_id}" for url in urls.values()))


if __name__ == "__main__":
    unittest.main()
