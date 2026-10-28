import os
import tempfile
import time
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from errno import ENOSPC
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from tests.video_fixtures import create_test_video


class DifyPreviewMediaTests(unittest.TestCase):
    def test_detects_mp4_when_dify_uses_generic_binary_content_type(self):
        from video_processor.app import _detect_downloaded_video_extension

        self.assertEqual(
            _detect_downloaded_video_extension(
                "application/octet-stream",
                b"\x00\x00\x00\x18ftypisom",
            ),
            ".mp4",
        )

    def test_rejects_non_video_generic_binary_content(self):
        from video_processor.app import _detect_downloaded_video_extension

        self.assertIsNone(
            _detect_downloaded_video_extension(
                "application/octet-stream",
                b"not-a-video",
            )
        )


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

    def test_render_endpoint_separates_report_and_technical_details(self):
        response = self.client.post(
            "/api/v1/evaluations/render",
            json={
                "asset_type": "script",
                "profile": "ad_script_v1",
                "summary": "结构完整。",
                "dimensions": [
                    {
                        "dimension": "structure",
                        "label": "信息结构",
                        "score": 8,
                        "status": "evaluated",
                        "reason": "钩子、卖点和CTA完整",
                    }
                ],
                "confidence": 0.9,
                "technical_details": {
                    "state_json": "secret-debug-state",
                    "steps": 1,
                },
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["result"]["status"], "completed")
        self.assertIn("总体结论", payload["report_markdown"])
        self.assertNotIn("secret-debug-state", payload["report_markdown"])
        self.assertEqual(
            payload["technical_details"]["state_json"],
            "secret-debug-state",
        )

    def test_render_endpoint_rejects_unknown_evidence_reference_with_422(self):
        response = self.client.post(
            "/api/v1/evaluations/render",
            json={
                "asset_type": "image",
                "profile": "ad_image_v1",
                "summary": "主体不突出。",
                "dimensions": [],
                "issues": [
                    {
                        "priority": "P1",
                        "dimension": "subject",
                        "problem": "主体较小",
                        "impact": "用户难以识别商品",
                        "evidence_refs": ["missing-evidence"],
                        "suggestion": "放大商品",
                    }
                ],
                "confidence": 0.8,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_rejects_unsupported_file_extension(self):
        response = self.client.post(
            "/api/v1/videos/extract",
            files={"video": ("ad.avi", b"not-a-video", "video/x-msvideo")},
        )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()["detail"], "Only .mp4 and .mov files are supported")

    def test_extracts_uploaded_mp4_and_exposes_downloadable_frames(self):
        video_path = create_test_video(self.root / "sample.mp4")

        with video_path.open("rb") as video_file:
            response = self.client.post(
                "/api/v1/videos/extract",
                files={"video": ("sample.mp4", video_file, "video/mp4")},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertGreaterEqual(payload["duration_seconds"], 4.0)
        self.assertFalse(
            (self.root / "data" / payload["video_id"] / "source.mp4").exists()
        )
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


class AgentVideoTaskApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_root = self.root / "data"
        self.unrelated = self.data_root / str(uuid4())
        self.unrelated.mkdir(parents=True)
        from video_processor.app import create_app

        self.client = TestClient(
            create_app(
                data_root=self.data_root,
                public_base_url="http://host.docker.internal:8000",
            )
        )

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def _assert_only_unrelated_task_remains(self):
        self.assertEqual(set(self.data_root.iterdir()), {self.unrelated})

    def test_creates_agent_task_and_retains_source_for_two_hours(self):
        from video_processor.agent_tasks import load_record

        video_path = create_test_video(self.root / "sample.mp4")
        with video_path.open("rb") as video_file:
            response = self.client.post(
                "/api/v1/agent-videos",
                files={"video": ("sample.mp4", video_file, "video/mp4")},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        task_dir, record = load_record(self.data_root, payload["video_id"])
        self.assertEqual(payload["duration_seconds"], round(record.duration_seconds, 3))
        self.assertEqual(
            [frame["timestamp_seconds"] for frame in payload["frames"]],
            [0.0, 3.0],
        )
        self.assertTrue((task_dir / "source.mp4").is_file())
        self.assertTrue((task_dir / "agent-task.json").is_file())
        retained_until = datetime.fromisoformat(payload["source_retained_until"])
        self.assertEqual(retained_until.tzinfo, timezone.utc)
        self.assertAlmostEqual(retained_until.timestamp(), record.expires_at, places=3)
        self.assertAlmostEqual(record.expires_at - record.created_at, 7200, places=3)
        for frame in payload["frames"]:
            download_path = frame["url"].split(":8000", maxsplit=1)[1]
            download = self.client.get(download_path)
            self.assertEqual(download.status_code, 200)
            self.assertEqual(download.headers["content-type"], "image/jpeg")

    def test_creates_agent_task_from_local_dify_file_preview(self):
        video_path = create_test_video(self.root / "sample.mp4")

        def copy_dify_video(relative_url, destination, max_bytes, base_url):
            self.assertEqual(
                relative_url,
                "/files/example/file-preview?timestamp=1&nonce=signed",
            )
            self.assertEqual(base_url, "http://localhost:18080")
            destination.write_bytes(video_path.read_bytes())
            return ".mp4"

        with patch(
            "video_processor.app._download_dify_video",
            side_effect=copy_dify_video,
        ):
            response = self.client.post(
                "/api/v1/agent-videos",
                data={
                    "video_url": (
                        "/files/example/file-preview?timestamp=1&nonce=signed"
                    )
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(
            (self.data_root / payload["video_id"] / "source.mp4").is_file()
        )

    def test_rejects_external_video_url_without_creating_task(self):
        response = self.client.post(
            "/api/v1/agent-videos",
            data={"video_url": "https://example.com/files/x/file-preview"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Only a local Dify file-preview path is allowed",
        )
        self._assert_only_unrelated_task_remains()

    def test_rejects_unsupported_extension_without_creating_task(self):
        response = self.client.post(
            "/api/v1/agent-videos",
            files={"video": ("ad.avi", b"video", "video/x-msvideo")},
        )

        self.assertEqual(response.status_code, 415)
        self._assert_only_unrelated_task_remains()

    def test_removes_new_task_after_empty_upload(self):
        response = self.client.post(
            "/api/v1/agent-videos",
            files={"video": ("empty.mp4", b"", "video/mp4")},
        )

        self.assertEqual(response.status_code, 400)
        self._assert_only_unrelated_task_remains()

    def test_removes_new_task_after_upload_limit_breach(self):
        from video_processor.app import create_app

        self.client.close()
        with patch.dict(os.environ, {"VIDEO_PROCESSOR_MAX_UPLOAD_BYTES": "3"}):
            self.client = TestClient(create_app(data_root=self.data_root))
        response = self.client.post(
            "/api/v1/agent-videos",
            files={"video": ("sample.mp4", b"four", "video/mp4")},
        )

        self.assertEqual(response.status_code, 413)
        self._assert_only_unrelated_task_remains()

    def test_removes_new_task_after_ffprobe_failure(self):
        with patch("video_processor.app.probe_duration", side_effect=RuntimeError("probe failed")):
            response = self.client.post(
                "/api/v1/agent-videos",
                files={"video": ("sample.mp4", b"video", "video/mp4")},
            )

        self.assertEqual(response.status_code, 422)
        self._assert_only_unrelated_task_remains()

    def test_removes_new_task_after_ffmpeg_failure(self):
        with (
            patch("video_processor.app.probe_duration", return_value=4.0),
            patch("video_processor.app.extract_frames", side_effect=RuntimeError("ffmpeg failed")),
        ):
            response = self.client.post(
                "/api/v1/agent-videos",
                files={"video": ("sample.mp4", b"video", "video/mp4")},
            )

        self.assertEqual(response.status_code, 422)
        self._assert_only_unrelated_task_remains()

    def test_removes_new_task_after_storage_exhaustion(self):
        with patch("video_processor.app.probe_duration", side_effect=OSError(ENOSPC, "full")):
            response = self.client.post(
                "/api/v1/agent-videos",
                files={"video": ("sample.mp4", b"video", "video/mp4")},
            )

        self.assertEqual(response.status_code, 507)
        self._assert_only_unrelated_task_remains()


class AgentSupplementApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_root = self.root / "data"
        from video_processor.app import create_app

        self.client = TestClient(
            create_app(
                data_root=self.data_root,
                public_base_url="http://host.docker.internal:8000",
            )
        )

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def _seed_task(self, duration=14.0, *, expired=False, rounds=0):
        from video_processor.agent_tasks import create_record, save_record

        video_id = str(uuid4())
        task_dir = self.data_root / video_id
        task_dir.mkdir(parents=True)
        (task_dir / "source.mp4").write_bytes(b"source")
        created_at = time.time() - 8000 if expired else time.time()
        record = create_record(
            video_id=video_id,
            duration_seconds=duration,
            source_filename="source.mp4",
            used_timestamps=[0.0, 3.0],
            created_at=created_at,
            retention_seconds=7200,
        )
        if rounds:
            record = replace(record, supplementary_rounds=rounds)
        save_record(task_dir, record)
        return video_id, task_dir

    def test_extracts_one_supplement_round_and_updates_metadata(self):
        from video_processor.agent_tasks import load_record

        video_path = create_test_video(self.root / "sample.mp4", duration_seconds=14.0)
        with video_path.open("rb") as video_file:
            created = self.client.post(
                "/api/v1/agent-videos",
                files={"video": ("sample.mp4", video_file, "video/mp4")},
            )
        video_id = created.json()["video_id"]

        response = self.client.post(
            f"/api/v1/agent-videos/{video_id}/frames",
            json={"timestamps": [8.0, 12.0]},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(
            [frame["timestamp_seconds"] for frame in payload["frames"]],
            [8.0, 12.0],
        )
        _, record = load_record(self.data_root, video_id)
        self.assertEqual(record.supplementary_rounds, 1)
        self.assertEqual(record.used_timestamps[-2:], (8.0, 12.0))
        for frame in payload["frames"]:
            download_path = frame["url"].split(":8000", maxsplit=1)[1]
            self.assertEqual(self.client.get(download_path).status_code, 200)

    def test_returns_404_for_invalid_missing_expired_or_missing_source_task(self):
        expired_id, _ = self._seed_task(expired=True)
        missing_source_id, missing_source_dir = self._seed_task()
        (missing_source_dir / "source.mp4").unlink()

        for video_id in ("invalid", str(uuid4()), expired_id, missing_source_id):
            with self.subTest(video_id=video_id):
                response = self.client.post(
                    f"/api/v1/agent-videos/{video_id}/frames",
                    json={"timestamps": [8.0]},
                )
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["detail"], "Agent video task not found")

    def test_rejects_invalid_empty_and_excess_timestamp_sets(self):
        cases = (
            ([-1.0], "No new valid timestamps were accepted"),
            ([14.0], "No new valid timestamps were accepted"),
            ([15.0], "No new valid timestamps were accepted"),
            ([0.0, 3.0], "No new valid timestamps were accepted"),
            ([4.0, 5.0, 6.0, 7.0], "Request accepts at most 3 new timestamps"),
        )
        for timestamps, expected_detail in cases:
            video_id, _ = self._seed_task()
            with self.subTest(timestamps=timestamps):
                response = self.client.post(
                    f"/api/v1/agent-videos/{video_id}/frames",
                    json={"timestamps": timestamps},
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["detail"], expected_detail)

    def test_second_round_is_conflict_without_calling_ffmpeg(self):
        video_id, _ = self._seed_task(rounds=1)
        with patch("video_processor.app.extract_frames") as extract_mock:
            response = self.client.post(
                f"/api/v1/agent-videos/{video_id}/frames",
                json={"timestamps": [8.0]},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Supplementary frame round already used")
        extract_mock.assert_not_called()

    def test_repeated_request_does_not_report_old_frames_as_new(self):
        video_id, _ = self._seed_task(rounds=1)
        with patch("video_processor.app.extract_frames") as extract_mock:
            response = self.client.post(
                f"/api/v1/agent-videos/{video_id}/frames",
                json={"timestamps": [8.0, 12.0]},
            )

        self.assertEqual(response.status_code, 409)
        extract_mock.assert_not_called()

    def test_partial_ffmpeg_failure_removes_only_new_frames_and_keeps_metadata(self):
        from video_processor.agent_tasks import load_record

        video_id, task_dir = self._seed_task()
        frames_dir = task_dir / "frames"
        frames_dir.mkdir()
        existing = frames_dir / "frame_00000ms.jpg"
        existing.write_bytes(b"existing")

        def fail_after_first(video_path, output_dir, timestamps):
            (output_dir / "frame_08000ms.jpg").write_bytes(b"new")
            raise RuntimeError("ffmpeg failed on second timestamp")

        with patch("video_processor.app.extract_frames", side_effect=fail_after_first):
            response = self.client.post(
                f"/api/v1/agent-videos/{video_id}/frames",
                json={"timestamps": [8.0, 12.0]},
            )

        self.assertEqual(response.status_code, 422)
        self.assertTrue(existing.is_file())
        self.assertFalse((frames_dir / "frame_08000ms.jpg").exists())
        _, record = load_record(self.data_root, video_id)
        self.assertEqual(record.supplementary_rounds, 0)
        self.assertEqual(record.used_timestamps, (0.0, 3.0))


class AgentDeleteApiTests(unittest.TestCase):
    def test_deletes_valid_task_and_then_returns_not_found(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_root = root / "data"
            from video_processor.app import create_app

            client = TestClient(
                create_app(
                    data_root=data_root,
                    public_base_url="http://host.docker.internal:8000",
                )
            )
            video_path = create_test_video(root / "sample.mp4")
            with video_path.open("rb") as video_file:
                created = client.post(
                    "/api/v1/agent-videos",
                    files={"video": ("sample.mp4", video_file, "video/mp4")},
                )
            payload = created.json()
            video_id = payload["video_id"]
            frame_path = payload["frames"][0]["url"].split(":8000", maxsplit=1)[1]
            unrelated = data_root / str(uuid4())
            unrelated.mkdir()

            deleted = client.delete(f"/api/v1/agent-videos/{video_id}")
            missing_frame = client.get(frame_path)
            repeated = client.delete(f"/api/v1/agent-videos/{video_id}")
            invalid = client.delete("/api/v1/agent-videos/not-a-uuid")
            client.close()

            self.assertEqual(deleted.status_code, 204)
            self.assertFalse((data_root / video_id).exists())
            self.assertEqual(missing_frame.status_code, 404)
            self.assertEqual(repeated.status_code, 404)
            self.assertEqual(invalid.status_code, 404)
            self.assertTrue(unrelated.is_dir())


if __name__ == "__main__":
    unittest.main()
