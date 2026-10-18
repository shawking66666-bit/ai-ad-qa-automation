import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from video_processor.app import create_app


class ReadinessTests(unittest.TestCase):
    def test_health_is_unavailable_when_configured_ffmpeg_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_root = Path(temp_dir) / "missing-tools"
            environment = {
                "VIDEO_PROCESSOR_FFMPEG_PATH": str(missing_root / "ffmpeg.exe"),
                "VIDEO_PROCESSOR_FFPROBE_PATH": str(missing_root / "ffprobe.exe"),
            }
            with patch.dict(os.environ, environment, clear=False):
                client = TestClient(create_app(data_root=Path(temp_dir) / "data"))
                response = client.get("/health")
                client.close()

        self.assertEqual(response.status_code, 503)
        self.assertIn("ffmpeg", response.json()["detail"].lower())


class UploadLimitTests(unittest.TestCase):
    def test_rejects_upload_larger_than_configured_limit_before_ffprobe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            environment = {
                "VIDEO_PROCESSOR_MAX_UPLOAD_BYTES": "3",
                "VIDEO_PROCESSOR_FFMPEG_PATH": str(Path(temp_dir) / "ffmpeg.exe"),
                "VIDEO_PROCESSOR_FFPROBE_PATH": str(Path(temp_dir) / "ffprobe.exe"),
            }
            with patch.dict(os.environ, environment, clear=False):
                client = TestClient(create_app(data_root=Path(temp_dir) / "data"))
                response = client.post(
                    "/api/v1/videos/extract",
                    files={"video": ("sample.mp4", b"four", "video/mp4")},
                )
                client.close()

        self.assertEqual(response.status_code, 413)
        self.assertIn("limit", response.json()["detail"].lower())


class RetentionTests(unittest.TestCase):
    def test_startup_removes_only_expired_uuid_task_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir) / "data"
            expired = data_root / str(uuid4())
            fresh = data_root / str(uuid4())
            unrelated = data_root / "keep-me"
            for path in (expired, fresh, unrelated):
                path.mkdir(parents=True)

            old_time = time.time() - 7200
            os.utime(expired, (old_time, old_time))
            os.utime(unrelated, (old_time, old_time))

            with patch.dict(
                os.environ,
                {"VIDEO_PROCESSOR_RETENTION_HOURS": "1"},
                clear=False,
            ):
                application = create_app(data_root=data_root)

            self.assertIsNotNone(application)
            self.assertFalse(expired.exists())
            self.assertTrue(fresh.exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
