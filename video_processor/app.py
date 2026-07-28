import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .service import extract_frames, probe_duration, select_timestamps


ALLOWED_EXTENSIONS = {".mp4", ".mov"}
CHUNK_SIZE = 1024 * 1024


def create_app(
    data_root: Path | None = None,
    public_base_url: str | None = None,
) -> FastAPI:
    root = Path(
        data_root
        or os.getenv("VIDEO_PROCESSOR_DATA_ROOT", "work/video_processor_data")
    ).resolve()
    base_url = (
        public_base_url
        or os.getenv(
            "VIDEO_PROCESSOR_PUBLIC_BASE_URL",
            "http://host.docker.internal:8000",
        )
    ).rstrip("/")
    root.mkdir(parents=True, exist_ok=True)

    application = FastAPI(
        title="AI Ad QA Video Processor",
        version="0.1.0",
    )

    @application.get("/health")
    def health() -> dict[str, str]:
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
            with video_path.open("wb") as destination:
                while chunk := await video.read(CHUNK_SIZE):
                    destination.write(chunk)

            if video_path.stat().st_size == 0:
                raise HTTPException(status_code=400, detail="Uploaded video is empty")

            duration = probe_duration(video_path)
            timestamps = select_timestamps(duration)
            frames = extract_frames(video_path, frames_dir, timestamps)
        except HTTPException:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise
        except RuntimeError as exc:
            shutil.rmtree(task_dir, ignore_errors=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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

    @application.get("/files/{video_id}/{filename}")
    def get_frame(video_id: str, filename: str) -> FileResponse:
        if not video_id or Path(video_id).name != video_id:
            raise HTTPException(status_code=404, detail="Frame not found")
        if not filename or Path(filename).name != filename:
            raise HTTPException(status_code=404, detail="Frame not found")

        frame_path = root / video_id / "frames" / filename
        if frame_path.suffix.lower() != ".jpg" or not frame_path.is_file():
            raise HTTPException(status_code=404, detail="Frame not found")
        return FileResponse(frame_path, media_type="image/jpeg", filename=filename)

    return application


app = create_app()
