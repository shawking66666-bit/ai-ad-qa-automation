# Video Processor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and start a Windows FastAPI service that accepts MP4/MOV uploads, extracts fixed-time JPEG frames with FFmpeg, and exposes Dify-accessible frame URLs.

**Architecture:** FastAPI owns upload validation, task directories, JSON responses, and static frame delivery. A focused FFmpeg adapter probes duration and extracts frames at 0, 3, 6, 10, 15, 20, 25, and 30 seconds while skipping timestamps beyond the video duration.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, Python standard-library `unittest`, FFmpeg/ffprobe 8.1.

## Global Constraints

- Accept only `.mp4` and `.mov`.
- Listen on `0.0.0.0:8000` so Docker Desktop can reach the service.
- Return frame URLs rooted at `http://host.docker.internal:8000`.
- Preserve ordered timestamps and Hook/Intro/Show stage hints.
- Do not require OpenCV for the MVP.
- Keep generated media under `work/video_processor_data`, not in source directories.

---

### Task 1: FFmpeg processing contract

**Files:**
- Create: `video_processor/service.py`
- Test: `tests/test_video_service.py`

**Interfaces:**
- Produces: `select_timestamps(duration_seconds: float) -> list[float]`
- Produces: `stage_for_timestamp(timestamp: float) -> str`
- Produces: `probe_duration(video_path: Path) -> float`
- Produces: `extract_frames(video_path: Path, output_dir: Path, timestamps: list[float]) -> list[FrameResult]`

- [ ] Write tests asserting fixed timestamps are clipped to video duration and stage boundaries are Hook `<3`, Intro `<10`, Show otherwise.
- [ ] Run `python -m unittest discover -s tests -v` and confirm failure because `video_processor.service` does not exist.
- [ ] Implement the minimal timestamp and stage functions.
- [ ] Run the tests and confirm they pass.
- [ ] Add a test using a generated 4-second FFmpeg video and assert real JPEG frames exist at 0 and 3 seconds.
- [ ] Run the test and confirm failure before adding the FFmpeg adapter.
- [ ] Implement probe and extraction with explicit subprocess errors.
- [ ] Run the complete test module.

### Task 2: FastAPI upload and file delivery

**Files:**
- Create: `video_processor/app.py`
- Create: `video_processor/__init__.py`
- Create: `tests/test_api.py`

**Interfaces:**
- Consumes: `probe_duration`, `select_timestamps`, and `extract_frames`.
- Produces: `GET /health`, `POST /api/v1/videos/extract`, and `GET /files/{video_id}/{filename}`.

- [ ] Write API tests for health, unsupported extensions, and a real short MP4 upload.
- [ ] Run the API tests and confirm failure because `video_processor.app` does not exist.
- [ ] Implement upload validation, UUID task directories, extraction, response serialization, and static file delivery.
- [ ] Run all tests and confirm they pass.
- [ ] Confirm every frame URL uses `http://host.docker.internal:8000`.

### Task 3: Windows startup and Dify connectivity

**Files:**
- Create: `start_video_processor.ps1`
- Create: `requirements.txt`
- Create: `README.md`

**Interfaces:**
- Consumes: `video_processor.app:app`.
- Produces: a background Uvicorn listener on `0.0.0.0:8000`.

- [ ] Add the pinned runtime dependencies and startup command.
- [ ] Start Uvicorn with the workspace Python interpreter.
- [ ] Verify `http://localhost:8000/health` returns HTTP 200.
- [ ] Verify a real multipart upload returns ordered frame metadata and downloadable JPEG files.
- [ ] Verify from `docker-api-1` that `http://host.docker.internal:8000/health` returns HTTP 200.
- [ ] Run the full unittest suite once more before reporting completion.
