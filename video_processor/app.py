import os
import shutil
import time
from contextlib import closing
from datetime import datetime, timezone
from errno import ENOSPC
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from .agent_tasks import (
    AgentTaskNotFound,
    cleanup_expired_agent_sources,
    create_record,
    delete_agent_task,
    load_record,
    record_supplement,
    save_record,
)
from .service import (
    check_runtime_dependencies,
    extract_frames,
    normalize_requested_timestamps,
    probe_duration,
    select_timestamps,
)


ALLOWED_EXTENSIONS = {".mp4", ".mov"}
CHUNK_SIZE = 1024 * 1024
DEFAULT_MAX_UPLOAD_BYTES = 500 * 1024 * 1024
DEFAULT_RETENTION_HOURS = 168
DEFAULT_AGENT_SOURCE_RETENTION_SECONDS = 7200
DEFAULT_DIFY_INTERNAL_BASE_URL = "http://localhost:18080"


class SupplementaryFramesRequest(BaseModel):
    timestamps: list[float]


def _positive_int_from_environment(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive integer")
    return value


def _is_uuid_directory(path: Path) -> bool:
    try:
        return (
            path.is_dir()
            and not path.is_symlink()
            and str(UUID(path.name)) == path.name
        )
    except ValueError:
        return False


def cleanup_expired_tasks(root: Path, retention_hours: int) -> None:
    cutoff = time.time() - retention_hours * 60 * 60
    for child in root.iterdir():
        if _is_uuid_directory(child) and child.stat().st_mtime < cutoff:
            shutil.rmtree(child)


async def _save_upload(
    video: UploadFile,
    video_path: Path,
    max_upload_bytes: int,
) -> None:
    uploaded_bytes = 0
    with video_path.open("wb") as destination:
        while chunk := await video.read(CHUNK_SIZE):
            uploaded_bytes += len(chunk)
            if uploaded_bytes > max_upload_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "Upload exceeds the configured size limit "
                        f"of {max_upload_bytes} bytes"
                    ),
                )
            destination.write(chunk)

    if video_path.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="Uploaded video is empty")


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _local_dify_preview_url(relative_url: str, base_url: str) -> str:
    parsed = urlsplit(relative_url)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or not parsed.path.startswith("/files/")
        or not parsed.path.endswith("/file-preview")
    ):
        raise HTTPException(
            status_code=400,
            detail="Only a local Dify file-preview path is allowed",
        )
    return urljoin(f"{base_url.rstrip('/')}/", relative_url.lstrip("/"))


def _detect_downloaded_video_extension(
    media_type: str,
    signature: bytes,
) -> str | None:
    declared_extension = {
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
    }.get(media_type)
    if declared_extension is not None:
        return declared_extension

    if media_type != "application/octet-stream" or signature[4:8] != b"ftyp":
        return None
    return ".mov" if signature[8:12] == b"qt  " else ".mp4"


def _download_dify_video(
    relative_url: str,
    destination: Path,
    max_upload_bytes: int,
    base_url: str,
) -> str:
    url = _local_dify_preview_url(relative_url, base_url)
    request = Request(url, headers={"User-Agent": "AI-Ad-QA/0.1"})
    try:
        with closing(build_opener(_RejectRedirects).open(request, timeout=30)) as response:
            media_type = response.headers.get_content_type().lower()
            if media_type not in {
                "video/mp4",
                "video/quicktime",
                "application/octet-stream",
            }:
                raise HTTPException(
                    status_code=415,
                    detail="Dify file-preview is not a supported video",
                )

            downloaded_bytes = 0
            signature = bytearray()
            with destination.open("wb") as output:
                while chunk := response.read(CHUNK_SIZE):
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > max_upload_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                "Upload exceeds the configured size limit "
                                f"of {max_upload_bytes} bytes"
                            ),
                        )
                    if len(signature) < 12:
                        signature.extend(chunk[: 12 - len(signature)])
                    output.write(chunk)

            extension = _detect_downloaded_video_extension(
                media_type,
                bytes(signature),
            )
            if extension is None:
                raise HTTPException(
                    status_code=415,
                    detail="Dify file-preview is not a supported video",
                )
    except HTTPException:
        raise
    except OSError as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to download the Dify video preview",
        ) from exc

    if not destination.is_file() or destination.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="Dify video preview is empty")
    return extension


def create_app(
    data_root: Path | None = None,
    public_base_url: str | None = None,
    dify_internal_base_url: str = DEFAULT_DIFY_INTERNAL_BASE_URL,
) -> FastAPI:
    root = Path(
        data_root
        or os.getenv(
            "VIDEO_PROCESSOR_DATA_ROOT",
            r"E:\AI\Data\AI-Ad-QA\video_processor_data",
        )
    ).resolve()
    base_url = (
        public_base_url
        or os.getenv(
            "VIDEO_PROCESSOR_PUBLIC_BASE_URL",
            "http://host.docker.internal:8000",
        )
    ).rstrip("/")
    root.mkdir(parents=True, exist_ok=True)
    retention_hours = _positive_int_from_environment(
        "VIDEO_PROCESSOR_RETENTION_HOURS",
        DEFAULT_RETENTION_HOURS,
    )
    max_upload_bytes = _positive_int_from_environment(
        "VIDEO_PROCESSOR_MAX_UPLOAD_BYTES",
        DEFAULT_MAX_UPLOAD_BYTES,
    )
    agent_source_retention_seconds = _positive_int_from_environment(
        "VIDEO_PROCESSOR_AGENT_SOURCE_RETENTION_SECONDS",
        DEFAULT_AGENT_SOURCE_RETENTION_SECONDS,
    )
    cleanup_expired_agent_sources(root)
    cleanup_expired_tasks(root, retention_hours)

    application = FastAPI(
        title="AI Ad QA Video Processor",
        version="0.1.0",
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        try:
            check_runtime_dependencies()
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"status": "ok"}

    @application.post("/api/v1/videos/extract")
    async def extract_video(video: UploadFile = File(...)) -> dict:
        original_name = video.filename or ""
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail="Only .mp4 and .mov files are supported",
            )

        video_id = str(uuid4())
        task_dir = root / video_id
        frames_dir = task_dir / "frames"
        task_dir.mkdir(parents=True)
        video_path = task_dir / f"source{extension}"

        try:
            await _save_upload(video, video_path, max_upload_bytes)
            duration = probe_duration(video_path)
            timestamps = select_timestamps(duration)
            frames = extract_frames(video_path, frames_dir, timestamps)
            video_path.unlink(missing_ok=True)
        except HTTPException:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise
        except RuntimeError as exc:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except OSError as exc:
            shutil.rmtree(task_dir, ignore_errors=True)
            status_code = 507 if exc.errno == ENOSPC else 500
            detail = (
                "Insufficient storage for video processing"
                if exc.errno == ENOSPC
                else "Local storage operation failed"
            )
            raise HTTPException(status_code=status_code, detail=detail) from exc
        finally:
            await video.close()

        return {
            "video_id": video_id,
            "duration_seconds": round(duration, 3),
            "frames": [
                {
                    "timestamp_seconds": frame.timestamp_seconds,
                    "stage_hint": frame.stage_hint,
                    "filename": frame.path.name,
                    "url": (
                        f"{base_url}/files/{video_id}/{frame.path.name}"
                    ),
                }
                for frame in frames
            ],
            "warnings": [],
        }

    @application.post("/api/v1/agent-videos")
    async def create_agent_video(
        video: UploadFile | None = File(None),
        video_url: str | None = Form(None),
    ) -> dict:
        if video is None and not video_url:
            raise HTTPException(status_code=400, detail="A video input is required")
        if video is not None and video_url:
            await video.close()
            raise HTTPException(status_code=400, detail="Provide only one video input")

        extension = ""
        if video is not None:
            original_name = video.filename or ""
            extension = Path(original_name).suffix.lower()
            if extension not in ALLOWED_EXTENSIONS:
                await video.close()
                raise HTTPException(
                    status_code=415,
                    detail="Only .mp4 and .mov files are supported",
                )
        else:
            _local_dify_preview_url(video_url or "", dify_internal_base_url)

        video_id = str(uuid4())
        task_dir = root / video_id
        frames_dir = task_dir / "frames"
        task_dir.mkdir(parents=True)
        source_filename = f"source{extension}" if extension else "source.download"
        video_path = task_dir / source_filename

        try:
            if video is not None:
                await _save_upload(video, video_path, max_upload_bytes)
            else:
                extension = _download_dify_video(
                    video_url or "",
                    video_path,
                    max_upload_bytes,
                    dify_internal_base_url,
                )
                source_filename = f"source{extension}"
                final_video_path = task_dir / source_filename
                video_path.replace(final_video_path)
                video_path = final_video_path
            duration = probe_duration(video_path)
            timestamps = select_timestamps(duration)
            frames = extract_frames(video_path, frames_dir, timestamps)
            created_at = time.time()
            record = create_record(
                video_id=video_id,
                duration_seconds=duration,
                source_filename=source_filename,
                used_timestamps=timestamps,
                created_at=created_at,
                retention_seconds=agent_source_retention_seconds,
            )
            save_record(task_dir, record)
        except HTTPException:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise
        except RuntimeError as exc:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except OSError as exc:
            shutil.rmtree(task_dir, ignore_errors=True)
            status_code = 507 if exc.errno == ENOSPC else 500
            detail = (
                "Insufficient storage for video processing"
                if exc.errno == ENOSPC
                else "Local storage operation failed"
            )
            raise HTTPException(status_code=status_code, detail=detail) from exc
        finally:
            if video is not None:
                await video.close()

        return {
            "video_id": video_id,
            "duration_seconds": round(duration, 3),
            "frames": [
                {
                    "timestamp_seconds": frame.timestamp_seconds,
                    "stage_hint": frame.stage_hint,
                    "filename": frame.path.name,
                    "url": f"{base_url}/files/{video_id}/{frame.path.name}",
                }
                for frame in frames
            ],
            "warnings": [],
            "source_retained_until": datetime.fromtimestamp(
                record.expires_at,
                tz=timezone.utc,
            ).isoformat(),
        }

    @application.post("/api/v1/agent-videos/{video_id}/frames")
    def create_supplementary_frames(
        video_id: str,
        request: SupplementaryFramesRequest,
    ) -> dict:
        try:
            task_dir, record = load_record(root, video_id)
        except AgentTaskNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail="Agent video task not found",
            ) from exc

        if time.time() >= record.expires_at:
            raise HTTPException(
                status_code=404,
                detail="Agent video task not found",
            )
        if record.supplementary_rounds >= 1:
            raise HTTPException(
                status_code=409,
                detail="Supplementary frame round already used",
            )

        try:
            timestamps, warnings = normalize_requested_timestamps(
                duration_seconds=record.duration_seconds,
                requested=request.timestamps,
                used=set(record.used_timestamps),
                limit=3,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not timestamps:
            raise HTTPException(
                status_code=422,
                detail="No new valid timestamps were accepted",
            )

        frames_dir = task_dir / "frames"
        frames_before = (
            {path.name for path in frames_dir.iterdir() if path.is_file()}
            if frames_dir.is_dir()
            else set()
        )
        try:
            frames = extract_frames(
                task_dir / record.source_filename,
                frames_dir,
                timestamps,
            )
            updated_record = record_supplement(record, timestamps)
            save_record(task_dir, updated_record)
        except RuntimeError as exc:
            if frames_dir.is_dir():
                for path in frames_dir.iterdir():
                    if path.is_file() and path.name not in frames_before:
                        path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except OSError as exc:
            if frames_dir.is_dir():
                for path in frames_dir.iterdir():
                    if path.is_file() and path.name not in frames_before:
                        path.unlink(missing_ok=True)
            status_code = 507 if exc.errno == ENOSPC else 500
            detail = (
                "Insufficient storage for video processing"
                if exc.errno == ENOSPC
                else "Local storage operation failed"
            )
            raise HTTPException(status_code=status_code, detail=detail) from exc

        return {
            "video_id": video_id,
            "frames": [
                {
                    "timestamp_seconds": frame.timestamp_seconds,
                    "stage_hint": frame.stage_hint,
                    "filename": frame.path.name,
                    "url": f"{base_url}/files/{video_id}/{frame.path.name}",
                }
                for frame in frames
            ],
            "warnings": warnings,
            "supplementary_rounds": updated_record.supplementary_rounds,
        }

    @application.get("/files/{video_id}/{filename}")
    def get_frame(video_id: str, filename: str) -> FileResponse:
        try:
            UUID(video_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Frame not found")
        if not filename or Path(filename).name != filename:
            raise HTTPException(status_code=404, detail="Frame not found")

        frame_path = root / video_id / "frames" / filename
        if frame_path.suffix.lower() != ".jpg" or not frame_path.is_file():
            raise HTTPException(status_code=404, detail="Frame not found")
        return FileResponse(frame_path, media_type="image/jpeg", filename=filename)

    @application.delete("/api/v1/agent-videos/{video_id}", status_code=204)
    def delete_agent_video(video_id: str) -> Response:
        if not delete_agent_task(root, video_id):
            raise HTTPException(
                status_code=404,
                detail="Agent video task not found",
            )
        return Response(status_code=204)

    return application


app = create_app()
