import json
import os
import tempfile
import unittest
from pathlib import Path


VALID_VIDEO_ID = "11111111-1111-4111-8111-111111111111"


class AgentTaskLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_source(self, task_dir: Path, filename: str = "source.mp4") -> Path:
        task_dir.mkdir(parents=True, exist_ok=True)
        source = task_dir / filename
        source.write_bytes(b"video")
        return source

    def test_round_trips_record_and_derives_two_hour_expiry(self):
        from video_processor.agent_tasks import (
            create_record,
            load_record,
            save_record,
        )

        task_dir = self.root / VALID_VIDEO_ID
        self._make_source(task_dir)
        record = create_record(
            video_id=VALID_VIDEO_ID,
            duration_seconds=14.25,
            source_filename="source.mp4",
            used_timestamps=[0.0, 3.0],
            created_at=1_000.0,
            retention_seconds=7_200,
        )

        save_record(task_dir, record)
        loaded_dir, loaded = load_record(self.root, VALID_VIDEO_ID)

        self.assertEqual(loaded_dir, task_dir.resolve())
        self.assertEqual(loaded, record)
        self.assertEqual(loaded.expires_at, 8_200.0)
        self.assertEqual(loaded.used_timestamps, (0.0, 3.0))
        self.assertFalse((task_dir / "agent-task.json.tmp").exists())

    def test_rejects_ids_that_are_not_canonical_uuids(self):
        from video_processor.agent_tasks import AgentTaskNotFound, load_record

        for video_id in (
            "not-a-uuid",
            "../outside",
            VALID_VIDEO_ID.upper(),
            "11111111111141118111111111111111",
        ):
            with self.subTest(video_id=video_id):
                with self.assertRaises(AgentTaskNotFound):
                    load_record(self.root, video_id)

    def test_rejects_corrupt_metadata_and_missing_source(self):
        from video_processor.agent_tasks import AgentTaskNotFound, load_record

        task_dir = self.root / VALID_VIDEO_ID
        task_dir.mkdir()
        (task_dir / "agent-task.json").write_text("not-json", encoding="utf-8")

        with self.assertRaises(AgentTaskNotFound):
            load_record(self.root, VALID_VIDEO_ID)

        (task_dir / "agent-task.json").write_text(
            json.dumps(
                {
                    "video_id": VALID_VIDEO_ID,
                    "duration_seconds": 4.0,
                    "source_filename": "source.mp4",
                    "used_timestamps": [0.0, 3.0],
                    "supplementary_rounds": 0,
                    "created_at": 1_000.0,
                    "expires_at": 8_200.0,
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaises(AgentTaskNotFound):
            load_record(self.root, VALID_VIDEO_ID)

    def test_rejects_symlink_task_directory(self):
        from video_processor.agent_tasks import AgentTaskNotFound, load_record

        outside = self.root / "outside"
        self._make_source(outside)
        (outside / "agent-task.json").write_text("{}", encoding="utf-8")
        link = self.root / VALID_VIDEO_ID
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"Windows symlink creation unavailable: {exc}")

        with self.assertRaises(AgentTaskNotFound):
            load_record(self.root, VALID_VIDEO_ID)

    def test_delete_removes_only_validated_agent_task(self):
        from video_processor.agent_tasks import (
            create_record,
            delete_agent_task,
            save_record,
        )

        task_dir = self.root / VALID_VIDEO_ID
        self._make_source(task_dir)
        record = create_record(
            video_id=VALID_VIDEO_ID,
            duration_seconds=4.0,
            source_filename="source.mp4",
            used_timestamps=[0.0, 3.0],
            created_at=1_000.0,
            retention_seconds=7_200,
        )
        save_record(task_dir, record)
        unrelated = self.root / "keep-me"
        unrelated.mkdir()
        (unrelated / "file.txt").write_text("keep", encoding="utf-8")

        self.assertTrue(delete_agent_task(self.root, VALID_VIDEO_ID))

        self.assertFalse(task_dir.exists())
        self.assertEqual((unrelated / "file.txt").read_text(encoding="utf-8"), "keep")
        self.assertFalse(delete_agent_task(self.root, VALID_VIDEO_ID))
        self.assertFalse(delete_agent_task(self.root, "../keep-me"))


class SupplementaryTimestampTests(unittest.TestCase):
    def test_normalizes_preserves_order_and_warns_on_request_duplicate(self):
        from video_processor.service import normalize_requested_timestamps

        accepted, warnings = normalize_requested_timestamps(
            duration_seconds=20.0,
            requested=[8, 12.1234, 8.0],
            used=set(),
        )

        self.assertEqual(accepted, [8.0, 12.123])
        self.assertEqual(warnings, ["Ignored duplicate timestamp: 8.0"])

    def test_rejects_non_finite_non_numeric_and_out_of_range_values(self):
        from video_processor.service import normalize_requested_timestamps

        accepted, warnings = normalize_requested_timestamps(
            duration_seconds=10.0,
            requested=[True, "3", float("nan"), float("inf"), -1.0, 10.0, 11.0, 4.0],
            used=set(),
        )

        self.assertEqual(accepted, [4.0])
        self.assertEqual(len(warnings), 7)
        self.assertTrue(all(message.startswith("Ignored invalid timestamp:") for message in warnings))

    def test_rejects_more_than_three_unique_new_timestamps(self):
        from video_processor.service import normalize_requested_timestamps

        with self.assertRaisesRegex(ValueError, "at most 3"):
            normalize_requested_timestamps(
                duration_seconds=20.0,
                requested=[1.0, 2.0, 3.0, 4.0],
                used=set(),
            )

    def test_treats_rounded_timestamp_as_already_used(self):
        from video_processor.service import normalize_requested_timestamps

        accepted, warnings = normalize_requested_timestamps(
            duration_seconds=10.0,
            requested=[3.0004, 6.0],
            used={3.0},
        )

        self.assertEqual(accepted, [6.0])
        self.assertEqual(warnings, ["Ignored already used timestamp: 3.0"])


class AgentCleanupTests(unittest.TestCase):
    def test_removes_only_expired_valid_agent_tasks(self):
        from video_processor.agent_tasks import (
            cleanup_expired_agent_sources,
            create_record,
            save_record,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            active_id = "11111111-1111-4111-8111-111111111111"
            expired_id = "22222222-2222-4222-8222-222222222222"
            corrupt_id = "33333333-3333-4333-8333-333333333333"
            legacy_id = "44444444-4444-4444-8444-444444444444"

            for video_id, created_at in ((active_id, 9_500.0), (expired_id, 1_000.0)):
                task_dir = root / video_id
                task_dir.mkdir()
                (task_dir / "source.mp4").write_bytes(b"video")
                save_record(
                    task_dir,
                    create_record(
                        video_id=video_id,
                        duration_seconds=4.0,
                        source_filename="source.mp4",
                        used_timestamps=[0.0, 3.0],
                        created_at=created_at,
                        retention_seconds=1_000,
                    ),
                )

            corrupt = root / corrupt_id
            corrupt.mkdir()
            (corrupt / "source.mp4").write_bytes(b"video")
            (corrupt / "agent-task.json").write_text("bad-json", encoding="utf-8")
            legacy = root / legacy_id
            (legacy / "frames").mkdir(parents=True)
            (legacy / "frames" / "frame.jpg").write_bytes(b"frame")
            unrelated = root / "keep-me"
            unrelated.mkdir()

            cleaned = cleanup_expired_agent_sources(root, now=10_000.0)

            self.assertEqual(cleaned, [expired_id])
            self.assertFalse((root / expired_id).exists())
            self.assertTrue((root / active_id).is_dir())
            self.assertTrue(corrupt.is_dir())
            self.assertTrue(legacy.is_dir())
            self.assertTrue(unrelated.is_dir())


if __name__ == "__main__":
    unittest.main()
