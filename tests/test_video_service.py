import subprocess
import tempfile
import unittest
from pathlib import Path


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
            select_timestamps,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video_path = root / "sample.mp4"
            frames_dir = root / "frames"
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


if __name__ == "__main__":
    unittest.main()
