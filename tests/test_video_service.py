import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.video_fixtures import create_test_video


class TimestampSelectionTests(unittest.TestCase):
    def test_clips_fixed_timestamps_to_video_duration(self):
        from video_processor.service import select_timestamps

        self.assertEqual(select_timestamps(4.0), [0.0, 3.0])
        self.assertEqual(
            select_timestamps(30.0),
            [0.0, 3.0, 6.0, 10.0, 15.0, 20.0, 25.0],
        )
        self.assertEqual(
            select_timestamps(30.1),
            [0.0, 3.0, 6.0, 10.0, 15.0, 20.0, 25.0, 30.0],
        )

    def test_assigns_hook_intro_and_show_boundaries(self):
        from video_processor.service import stage_for_timestamp

        self.assertEqual(stage_for_timestamp(0.0), "hook")
        self.assertEqual(stage_for_timestamp(2.99), "hook")
        self.assertEqual(stage_for_timestamp(3.0), "intro")
        self.assertEqual(stage_for_timestamp(9.99), "intro")
        self.assertEqual(stage_for_timestamp(10.0), "show")


class FfmpegIntegrationTests(unittest.TestCase):
    def test_extracts_real_jpeg_frames_from_short_video(self):
        from video_processor.service import (
            extract_frames,
            probe_duration,
            resolve_executable,
            select_timestamps,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = create_test_video(root / "sample.mp4")
            frames_dir = root / "frames"

            duration = probe_duration(video_path)
            frames = extract_frames(
                video_path,
                frames_dir,
                select_timestamps(duration),
            )

            self.assertGreaterEqual(duration, 4.0)
            self.assertEqual([frame.timestamp_seconds for frame in frames], [0.0, 3.0])
            self.assertEqual(
                [frame.path.name for frame in frames],
                ["frame_00000ms.jpg", "frame_03000ms.jpg"],
            )
            for frame in frames:
                self.assertTrue(frame.path.is_file())
                self.assertGreater(frame.path.stat().st_size, 1000)


class SubprocessSafetyTests(unittest.TestCase):
    def test_reports_ffmpeg_timeout_as_runtime_error(self):
        from video_processor.service import _run

        with patch(
            "video_processor.service.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["ffmpeg"], 1),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                _run(["ffmpeg", "-version"], timeout_seconds=1)


if __name__ == "__main__":
    unittest.main()
