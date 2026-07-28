# Windows FastAPI Launcher Design

## Goal

Allow the AI Ad QA video processor to be started, stopped, and checked by
double-clicking files after the repository is cloned to another Windows PC.

## Design

- Keep the existing PowerShell launcher as the source of truth.
- Add thin `.cmd` wrappers so Windows users can double-click without changing
  their global PowerShell execution policy.
- Resolve the project directory relative to each script, so the repository can
  be cloned anywhere.
- Store generated media under
  `D:\AI-Ad-QA-Data\video_processor_data`, outside the Git repository.
- Install Python dependencies only when imports are missing.
- Refuse to stop an unrelated process that happens to use port 8000.
- Keep API keys, media, runtime outputs, and virtual environments out of Git.

## Operating model

1. Start Docker Desktop and wait for Dify.
2. Double-click `启动FastAPI.cmd`.
3. Keep its terminal window open while using Dify.
4. Double-click `检查FastAPI状态.cmd` when troubleshooting.
5. Use `停止FastAPI.cmd` or Ctrl+C to stop the service.

## GitHub update boundary

FastAPI code and scripts update through Git. Dify workflow DSL files are
versioned in Git but still need to be imported into Dify after pulling.
