# FastAPI Hardening and Local Deployment Plan

**Goal:** Make the local video processor reliably report readiness, use an
isolated Python environment and portable FFmpeg, bound resource usage, and
remain compatible with the imported Dify workflow.

**Confirmed failures before implementation:**

- The machine Python is an Anaconda base interpreter without FastAPI.
- `ffmpeg` and `ffprobe` are unavailable.
- `/health` returns HTTP 200 while an MP4 upload returns HTTP 422 because
  `ffprobe` is missing.
- Launcher text tests pass even when the service cannot process video.

## Task 1: Isolated runtime and portable tools

- [ ] Create `.venv` from the available Python interpreter.
- [ ] Install runtime and test dependencies only inside `.venv`.
- [ ] Download a verified portable FFmpeg build to `E:\AI\Tools\ffmpeg`.
- [ ] Keep FFmpeg out of the system PATH and global Python untouched.

## Task 2: Failing tests for confirmed gaps

- [ ] Add a readiness test that expects HTTP 503 when FFmpeg is unavailable.
- [ ] Add a readiness test that expects HTTP 200 when dependencies are ready.
- [ ] Add a bounded-upload test that expects HTTP 413.
- [ ] Add a retention test restricted to expired UUID task directories.
- [ ] Add an FFmpeg timeout test.
- [ ] Strengthen launcher tests to require `.venv`, E-drive data, and explicit
  FFmpeg/FFprobe paths.
- [ ] Run the tests and verify that they fail for the intended missing
  behavior before changing production code.

## Task 3: Minimal production fixes

- [ ] Resolve FFmpeg and FFprobe from explicit environment variables, with
  PATH fallback for developer environments.
- [ ] Apply subprocess timeouts and actionable errors.
- [ ] Turn `/health` into a readiness check.
- [ ] Enforce a 500 MiB default upload limit.
- [ ] Delete the uploaded source after successful extraction.
- [ ] Clean only expired UUID task directories under the configured data root.
- [ ] Use `E:\AI\Data\AI-Ad-QA\video_processor_data`.
- [ ] Make the Windows launcher create/use `.venv` and fail before Uvicorn if
  portable FFmpeg is unavailable.

## Task 4: Verification and local integration

- [ ] Run the full unittest suite.
- [ ] Start FastAPI with the project launcher.
- [ ] Verify host `/health` returns HTTP 200 with dependency details.
- [ ] Upload a generated short MP4 and download all returned JPEG frames.
- [ ] Verify `docker-api-1` can access both `/health` and one frame URL through
  `host.docker.internal:8000`.
- [ ] Leave the service running for Dify testing; do not publish the Dify
  workflow.
