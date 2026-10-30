# AI-Ad-QA Project Rules

## Purpose

This project provides the local FastAPI video processor used by the Dify
`AI广告素材质量评估与优化系统` workflow.

## Directory contract

- `video_processor/`: FastAPI application and FFmpeg adapter.
- `tests/`: unit and integration tests.
- `workflow/`: exported Dify DSL files; never edit a current DSL in place.
- `demo/`: localhost-only portfolio page and its Dify Service API adapter; static assets live in `demo/static/`. Keep runtime uploads out of this directory.
- `docs/`: design notes, plans, and operating instructions.
- `.venv/`: project-local Python environment; never commit it.
- Runtime media: `E:\AI\Data\AI-Ad-QA\video_processor_data`.
- Portable FFmpeg: `E:\AI\Tools\ffmpeg`; do not add it to system PATH.

## Safety and secrets

- Never store API keys, tokens, passwords, uploaded videos, or extracted
  frames in Git.
- The demo reads `DIFY_DEMO_API_KEY` only from its process environment. Never echo it, expose it in browser responses, or write it to `.env` or logs. Bind the demo to `127.0.0.1:8001` only; accept no user-provided upstream URL.
- Do not modify global Python, Conda environments, system PATH, Docker
  settings, or Windows Firewall from this project.
- Bind FastAPI to `0.0.0.0:8000` only because Docker Desktop must reach it.
  Do not expose port 8000 through a router or public tunnel.
- File operations and cleanup must stay inside the configured runtime data
  root.

## Runtime rules

- Startup must use `.venv\Scripts\python.exe`, never an arbitrary global
  Python after the virtual environment has been created.
- Startup must fail before launching if FFmpeg, FFprobe, the data directory,
  or Python dependencies are unavailable.
- `/health` is a readiness endpoint: return success only when video
  processing dependencies are usable.
- Default upload limit: 500 MiB.
- Default generated-data retention: 7 days; cleanup is restricted to UUID
  task directories inside the runtime data root.
- FFmpeg subprocesses require an explicit timeout.

## Change discipline

- Use test-driven development for behavior changes: add a failing test,
  verify the failure, implement the smallest fix, then run the full suite.
- Do not change the FastAPI response contract without checking the current
  Dify DSL parser node.
- Do not publish the Dify workflow or push Git changes without explicit user
  approval.

## Verification

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Live checks require FastAPI to be running:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

The Dify container must also reach:

```text
http://host.docker.internal:8000/health
```
