import subprocess
from pathlib import Path


def create_test_video(path: Path, duration_seconds: float = 4.0) -> Path:
    from video_processor.service import resolve_executable

    subprocess.run(
        [
            resolve_executable("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x240:rate=10",
            "-t",
            f"{duration_seconds:g}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(path),
        ],
        check=True,
    )
    return path
