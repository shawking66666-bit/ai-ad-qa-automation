import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


FIXED_TIMESTAMPS = (0.0, 3.0, 6.0, 10.0, 15.0, 20.0, 25.0, 30.0)


@dataclass(frozen=True)
class FrameResult:
    timestamp_seconds: float
    stage_hint: str
    path: Path


def select_timestamps(duration_seconds: float) -> list[float]:
    return [timestamp for timestamp in FIXED_TIMESTAMPS if timestamp < duration_seconds]


def stage_for_timestamp(timestamp: float) -> str:
    if timestamp < 3:
        return "hook"
    if timestamp < 10:
        return "intro"
    return "show"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required executable is missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"{command[0]} failed: {detail}") from exc


def probe_duration(video_path: Path) -> float:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ]
    )
    try:
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("ffprobe did not return a valid video duration") from exc
    if duration <= 0:
        raise RuntimeError("Video duration must be greater than zero")
    return duration


def extract_frames(
    video_path: Path,
    output_dir: Path,
    timestamps: list[float],
) -> list[FrameResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[FrameResult] = []

    for timestamp in timestamps:
        filename = f"frame_{round(timestamp * 1000):05d}ms.jpg"
        output_path = output_dir / filename
        _run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:g}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-vf",
                "scale='min(1280,iw)':-2",
                "-q:v",
                "2",
                "-y",
                str(output_path),
            ]
        )
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(f"FFmpeg did not create frame at {timestamp:g} seconds")
        frames.append(
            FrameResult(
                timestamp_seconds=timestamp,
                stage_hint=stage_for_timestamp(timestamp),
                path=output_path,
            )
        )

    return frames
