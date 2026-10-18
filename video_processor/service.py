import json
import math
import os
import shutil
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


def normalize_requested_timestamps(
    duration_seconds: float,
    requested: list[float],
    used: set[float],
    limit: int = 3,
) -> tuple[list[float], list[str]]:
    normalized_used = {round(float(value), 3) for value in used}
    accepted: list[float] = []
    accepted_set: set[float] = set()
    warnings: list[str] = []

    for raw_value in requested:
        if (
            isinstance(raw_value, bool)
            or not isinstance(raw_value, (int, float))
            or not math.isfinite(raw_value)
            or raw_value < 0
            or raw_value >= duration_seconds
        ):
            warnings.append(f"Ignored invalid timestamp: {raw_value!r}")
            continue

        timestamp = round(float(raw_value), 3)
        if timestamp in normalized_used:
            warnings.append(f"Ignored already used timestamp: {timestamp}")
            continue
        if timestamp in accepted_set:
            warnings.append(f"Ignored duplicate timestamp: {timestamp}")
            continue

        accepted.append(timestamp)
        accepted_set.add(timestamp)

    if len(accepted) > limit:
        raise ValueError(f"Request accepts at most {limit} new timestamps")
    return accepted, warnings


def stage_for_timestamp(timestamp: float) -> str:
    if timestamp < 3:
        return "hook"
    if timestamp < 10:
        return "intro"
    return "show"


def resolve_executable(name: str) -> str:
    environment_name = f"VIDEO_PROCESSOR_{name.upper()}_PATH"
    configured_path = os.getenv(environment_name)
    if configured_path:
        executable = Path(configured_path).expanduser().resolve()
        if executable.is_file():
            return str(executable)
        raise RuntimeError(
            f"{name} is unavailable: {environment_name} points to a missing file"
        )

    discovered_path = shutil.which(name)
    if discovered_path:
        return discovered_path
    raise RuntimeError(
        f"{name} is unavailable: set {environment_name} to the executable path"
    )


def _run(
    command: list[str],
    timeout_seconds: int = 120,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required executable is missing: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"{command[0]} failed: {detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"{command[0]} timed out after {timeout_seconds} seconds"
        ) from exc


def check_runtime_dependencies() -> None:
    for name in ("ffmpeg", "ffprobe"):
        executable = resolve_executable(name)
        _run([executable, "-version"], timeout_seconds=10)


def probe_duration(video_path: Path) -> float:
    result = _run(
        [
            resolve_executable("ffprobe"),
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
                resolve_executable("ffmpeg"),
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
