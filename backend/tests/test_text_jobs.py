import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase

os.environ.setdefault("OPENROUTER_API_KEY", "test-key")

from fastapi.testclient import TestClient  # noqa: E402

import fmsi_un_recommendations.db as db_module  # noqa: E402
from fmsi_un_recommendations import api as api_module  # noqa: E402
from fmsi_un_recommendations.api import create_app  # noqa: E402
from fmsi_un_recommendations.db import get_database  # noqa: E402
from fmsi_un_recommendations.settings import Settings  # noqa: E402


class TextJobTests(TestCase):
    def test_matches_enqueues_text_job_without_saving_payloads_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            previous_upload_root = api_module.UPLOAD_ROOT
            api_module.UPLOAD_ROOT = temp_path / "uploads"
            db_module._DB_INSTANCE = None
            try:
                settings = Settings(local_db_path=str(temp_path / "recommendations.db"))
                app = create_app(settings)
                client = TestClient(app)

                payload = {
                    "job_id": "job-text-test",
                    "source_filename": "fmsi.pdf",
                    "reference_filename": "upr.docx",
                    "fmsi_markdown": "## Recommendations\n\n- Protect children.",
                    "upr_rows": [
                        {
                            "Theme": "Children",
                            "Recommendation and recommending State": "Protect children in law.",
                            "Position of the State under review": "Supported",
                        }
                    ],
                }
                response = client.post("/matches", json=payload)

                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), {"job_id": "job-text-test"})

                db = get_database(settings)
                job = db.get_job("job-text-test")
                self.assertIsNotNone(job)
                assert job is not None
                self.assertEqual(job.status, "pending")
                self.assertIsNone(job.source_path)
                self.assertIsNone(job.reference_path)
                self.assertEqual(job.source_filename, payload["source_filename"])
                self.assertEqual(job.reference_filename, payload["reference_filename"])
                self.assertEqual(job.source_text, payload["fmsi_markdown"])
                self.assertEqual(job.reference_rows, payload["upr_rows"])
                self.assertFalse(api_module.UPLOAD_ROOT.exists())
            finally:
                api_module.UPLOAD_ROOT = previous_upload_root
                db_module._DB_INSTANCE = None

    def test_matches_can_save_text_payload_snapshots_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            previous_upload_root = api_module.UPLOAD_ROOT
            api_module.UPLOAD_ROOT = temp_path / "uploads"
            db_module._DB_INSTANCE = None
            try:
                settings = Settings(
                    local_db_path=str(temp_path / "recommendations.db"),
                    save_text_payloads=True,
                )
                app = create_app(settings)
                client = TestClient(app)

                payload = {
                    "job_id": "job-text-save-test",
                    "source_filename": "fmsi.pdf",
                    "reference_filename": "upr.docx",
                    "fmsi_markdown": "## Recommendations\n\n- Protect children.",
                    "upr_rows": [{"Theme": "Children", "Recommendation": "Protect children."}],
                }
                response = client.post("/matches", json=payload)

                self.assertEqual(response.status_code, 200, response.text)

                db = get_database(settings)
                job = db.get_job("job-text-save-test")
                self.assertIsNotNone(job)
                assert job is not None
                self.assertIsNotNone(job.source_path)
                self.assertIsNotNone(job.reference_path)
                assert job.source_path is not None
                assert job.reference_path is not None
                self.assertEqual(Path(job.source_path).read_text(encoding="utf-8"), payload["fmsi_markdown"])
                self.assertEqual(json.loads(Path(job.reference_path).read_text(encoding="utf-8")), payload["upr_rows"])
                self.assertEqual(job.source_text, payload["fmsi_markdown"])
                self.assertEqual(job.reference_rows, payload["upr_rows"])
            finally:
                api_module.UPLOAD_ROOT = previous_upload_root
                db_module._DB_INSTANCE = None
