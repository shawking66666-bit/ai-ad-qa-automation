import json
import shutil
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from uuid import UUID


METADATA_FILENAME = "agent-task.json"


class AgentTaskNotFound(RuntimeError):
    """Raised when an Agent task cannot be loaded through the safe boundary."""


@dataclass(frozen=True)
class AgentTaskRecord:
    video_id: str
    duration_seconds: float
    source_filename: str
    used_timestamps: tuple[float, ...]
    supplementary_rounds: int
    created_at: float
    expires_at: float


def create_record(
    video_id: str,
    duration_seconds: float,
    source_filename: str,
    used_timestamps: list[float],
    created_at: float,
    retention_seconds: int,
) -> AgentTaskRecord:
    return AgentTaskRecord(
        video_id=video_id,
        duration_seconds=float(duration_seconds),
        source_filename=source_filename,
        used_timestamps=tuple(float(value) for value in used_timestamps),
        supplementary_rounds=0,
        created_at=float(created_at),
        expires_at=float(created_at + retention_seconds),
    )


def save_record(task_dir: Path, record: AgentTaskRecord) -> None:
    metadata_path = task_dir / METADATA_FILENAME
    temporary_path = task_dir / f"{METADATA_FILENAME}.tmp"
    payload = asdict(record)
    payload["used_timestamps"] = list(record.used_timestamps)
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    temporary_path.replace(metadata_path)


def record_supplement(
    record: AgentTaskRecord,
    new_timestamps: list[float],
) -> AgentTaskRecord:
    return replace(
        record,
        used_timestamps=record.used_timestamps
        + tuple(float(value) for value in new_timestamps),
        supplementary_rounds=record.supplementary_rounds + 1,
    )


def _canonical_task_dir(root: Path, video_id: str) -> Path:
    try:
        parsed = UUID(video_id)
    except (TypeError, ValueError, AttributeError) as exc:
        raise AgentTaskNotFound("Agent video task not found") from exc
    if str(parsed) != video_id:
        raise AgentTaskNotFound("Agent video task not found")

    resolved_root = root.resolve()
    candidate = resolved_root / video_id
    if candidate.is_symlink() or not candidate.is_dir():
        raise AgentTaskNotFound("Agent video task not found")
    try:
        candidate.resolve().relative_to(resolved_root)
    except ValueError as exc:
        raise AgentTaskNotFound("Agent video task not found") from exc
    return candidate.resolve()


def load_record(root: Path, video_id: str) -> tuple[Path, AgentTaskRecord]:
    task_dir = _canonical_task_dir(root, video_id)
    try:
        payload = json.loads(
            (task_dir / METADATA_FILENAME).read_text(encoding="utf-8")
        )
        record = AgentTaskRecord(
            video_id=str(payload["video_id"]),
            duration_seconds=float(payload["duration_seconds"]),
            source_filename=str(payload["source_filename"]),
            used_timestamps=tuple(float(value) for value in payload["used_timestamps"]),
            supplementary_rounds=int(payload["supplementary_rounds"]),
            created_at=float(payload["created_at"]),
            expires_at=float(payload["expires_at"]),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AgentTaskNotFound("Agent video task not found") from exc

    if record.video_id != video_id:
        raise AgentTaskNotFound("Agent video task not found")
    if not record.source_filename or Path(record.source_filename).name != record.source_filename:
        raise AgentTaskNotFound("Agent video task not found")
    if not (task_dir / record.source_filename).is_file():
        raise AgentTaskNotFound("Agent video task not found")
    return task_dir, record


def delete_agent_task(root: Path, video_id: str) -> bool:
    try:
        task_dir, _ = load_record(root, video_id)
    except AgentTaskNotFound:
        return False
    shutil.rmtree(task_dir)
    return True


def cleanup_expired_agent_sources(
    root: Path,
    now: float | None = None,
) -> list[str]:
    current_time = time.time() if now is None else float(now)
    cleaned: list[str] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        try:
            task_dir, record = load_record(root, child.name)
        except AgentTaskNotFound:
            continue
        if record.expires_at <= current_time:
            shutil.rmtree(task_dir)
            cleaned.append(record.video_id)
    return cleaned
