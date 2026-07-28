import subprocess
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class VideoProcessorApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        from video_processor.app import create_app

        self.client = TestClient(
            create_app(
                data_root=self.root / "data",
                public_base_url="http://host.docker.internal:8000",
            )
        )

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def test_health_reports_ready(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_rejects_unsupported_file_extension(self):
        response = self.client.post(
            "/api/v1/videos/extract",
            files={"video": ("ad.avi", b"not-a-video", "video/x-msvideo")},
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()["detail"], "Only .mp4 and .mov files are supported")

    def test_extracts_uploaded_mp4_and_exposes_downloadable_frames(self):
        video_path = self.root / "sample.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=320x240:rate=10",
                "-t",
                "4",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-y",
                str(video_path),
            ],
            check=True,
        )

        with video_path.open("rb") as video_file:
            response = self.client.post(
                "/api/v1/videos/extract",
                files={"video": ("sample.mp4", video_file, "video/mp4")},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertGreaterEqual(payload["duration_seconds"], 4.0)
        self.assertEqual(
            [frame["timestamp_seconds"] for frame in payload["frames"]],
            [0.0, 3.0],
        )
        self.assertEqual(
            [frame["stage_hint"] for frame in payload["frames"]],
            ["hook", "intro"],
        )
        for frame in payload["frames"]:
            self.assertTrue(
                frame["url"].startswith("http://host.docker.internal:8000/files/")
            )
            download_path = frame["url"].split(":8000", maxsplit=1)[1]
            download = self.client.get(download_path)
            self.assertEqual(download.status_code, 200)
            self.assertEqual(download.headers["content-type"], "image/jpeg")
            self.assertGreater(len(download.content), 1000)


if __name__ == "__main__":
    unittest.main()
