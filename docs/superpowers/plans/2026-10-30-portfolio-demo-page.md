# Local Portfolio Demo Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a localhost-only page that accepts one advertising video, image, or script and displays only the readable Dify report.

**Architecture:** A separate FastAPI service on `127.0.0.1:8001` serves a small static UI and acts as the sole client of the published Dify Workflow Service API. It uploads one local file when needed, runs the workflow, and returns only `report_markdown` plus status to the browser. The existing processor on port 8000 and the Dify DSL remain unchanged.

**Tech Stack:** Existing Python virtual environment, FastAPI, Python standard library HTTP client, vanilla HTML/CSS/JavaScript, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-30-portfolio-demo-page-design.md`.

## Global Constraints

- First update root `CLAUDE.md` with `demo/` directory, port, secrets, and verification rules; then create `demo/` files.
- Bind demo service to `127.0.0.1:8001`; do not expose it through Docker, a LAN, or a tunnel.
- Read `DIFY_DEMO_API_KEY` from the process environment only; do not edit `.env`, credentials, CI/CD, or Dify settings.
- Do not put raw `evaluation_result`, `technical_details`, or `state_json` in the browser response.
- Keep the existing video processor and Dify workflow APIs unchanged.
- No file persistence in the repository; restrict upload type and size and forward it to the fixed local Dify origin.

## Review Focus

- Missing key: page loads with a clear local setup message; no fake successful report.
- Wrong file type or excessive size: reject before contacting Dify.
- Dify upload error, non-success workflow status, or missing `report_markdown`: show a safe actionable error, not raw response JSON.
- Long video run: explicit progress, bounded timeout, and no browser key exposure.
- Markdown containing HTML-like text: render as text, never execute markup or script.

---

## File Map

- `CLAUDE.md`: add `demo/` ownership and security constraints before implementation.
- `demo/__init__.py`: package marker.
- `demo/dify_client.py`: fixed-origin Dify file upload and workflow execution; functions `upload_file(...)` and `run_workflow(...)`.
- `demo/app.py`: FastAPI routes `GET /`, `GET /static/...`, `POST /api/evaluate`, input validation, output allowlist.
- `demo/static/index.html`, `demo/static/style.css`, `demo/static/app.js`: accessible input form, progress, safe report rendering.
- `start_demo.ps1`, `启动演示页.cmd`: process-only key prompt and local startup.
- `tests/test_demo_client.py`, `tests/test_demo_api.py`: mocked Dify I/O and contract tests.
- `README.md`, `workflow/README.md`, `docs/multimodal-v1-validation.md`: canonical startup and honest validation boundary.

### Task 1: Directory Rule and Dify Client

**Interfaces:** `upload_file(file_bytes: bytes, filename: str, user: str, key: str, base_url: str) -> str`; `run_workflow(inputs: dict, user: str, key: str, base_url: str) -> dict`.

- [ ] Update `CLAUDE.md` with the new directory, fixed origin, no-credential-logging, and command for full tests.
- [ ] Write `tests/test_demo_client.py` with mocked HTTP responses for upload ID, successful workflow output, 401, 413, timeout, malformed response, and missing report.
- [ ] Run the focused test and observe RED.
- [ ] Implement `demo/dify_client.py` using the local app's documented `/files/upload` and `/workflows/run` contract. Never log request headers or full Dify responses.
- [ ] Run the focused test and observe GREEN; commit this task.

### Task 2: Local API and Validation

**Interfaces:** `create_demo_app(client: DifyClient | None = None) -> FastAPI`; `POST /api/evaluate` receives one multipart file or script and context fields, returns `{report_markdown, final_status}`.

- [ ] Write `tests/test_demo_api.py` for valid video/image/script mapping, absent key, unsupported extension, size limit, missing input, Dify failure, and output allowlist.
- [ ] Run the focused test and observe RED.
- [ ] Implement `demo/app.py` with same-origin routes, fixed Dify base URL, and no uploaded-file persistence.
- [ ] Run the focused test and observe GREEN; commit this task.

### Task 3: Presentation UI and Launcher

**Interfaces:** `GET /` serves the UI; `demo/static/app.js` posts a form and renders only the report; `start_demo.ps1` starts `.venv\Scripts\python.exe -m uvicorn demo.app:app --host 127.0.0.1 --port 8001`.

- [ ] Add a test that static assets load and browser payload contains neither key nor technical JSON.
- [ ] Run the focused test and observe RED.
- [ ] Build a responsive single-page interface with type switch, relevant inputs, progress/error state, and safe heading/list rendering with DOM `textContent`.
- [ ] Add startup scripts that prompt for the key without echoing it when the process environment does not already contain it; do not save it to disk.
- [ ] Run focused tests and inspect the page in the browser; commit this task.

### Task 4: Documentation and End-to-End Gate

- [ ] Update README and workflow docs to describe local demo, API key input, and distinction from Dify's raw-JSON WebApp.
- [ ] Run `\.venv\Scripts\python.exe -m unittest discover -s tests -v` with project FFmpeg paths set; record results.
- [ ] Run the demo locally with a user-entered key and perform video, image, and script smoke tests with non-sensitive fixtures; report only completed checks.
- [ ] Check `git diff --check`, key scan, and no uploaded media in Git status; commit documentation.
- [ ] Ask separately before any Git push or public deployment if authorization is not already present in the session.
