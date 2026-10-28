# AI Ad QA Video Processor

## AIGC 多模态内容质检 V1（候选）

当前功能分支新增一个作品集级候选工作流，统一审核广告视频、广告图片和广告脚本，并输出结构化评分、可追溯证据、问题清单、优化建议和人类可读 Markdown 报告。

- 候选 DSL：`workflow/candidate/AIGC-Multimodal-QA-v1.yml`
- 确定性生成器：`workflow/tools/build_multimodal_v1.py`
- 公开测试素材：`tests/fixtures/multimodal/`
- 验证边界：`docs/multimodal-v1-validation.md`

该版本不会自动替换 current。当前状态为自动化测试和本地 FastAPI 报告接口已验证，Dify 三素材端到端 live run 尚未完成。

Local FastAPI service used by the Dify workflow to extract fixed-time JPEG
frames from uploaded MP4 and MOV advertising videos.

## Start

On Windows, the easiest option is to double-click:

- `启动FastAPI.cmd` — start the service and keep its window open.
- `检查FastAPI状态.cmd` — verify `http://localhost:8000/health`.
- `停止FastAPI.cmd` — stop only this project's Uvicorn process.

The first start creates the project-local `.venv`, installs missing packages
there, checks the portable FFmpeg executables, and creates
`E:\AI\Data\AI-Ad-QA\video_processor_data`.

Portable FFmpeg is expected at `E:\AI\Tools\ffmpeg`. The launcher references
the executables directly and does not modify the Windows system `PATH`.

The equivalent PowerShell command is:

```powershell
powershell -ExecutionPolicy Bypass -File .\start_video_processor.ps1
```

The service listens on `0.0.0.0:8000`.

- Windows health check: `http://localhost:8000/health`
- Dify URL: `http://host.docker.internal:8000/api/v1/videos/extract`
- API documentation: `http://localhost:8000/docs`

## API

Upload a video as multipart form data with the field name `video`:

```powershell
curl.exe -X POST `
  -F "video=@C:\path\to\video.mp4" `
  http://localhost:8000/api/v1/videos/extract
```

Generated data is stored under
`E:\AI\Data\AI-Ad-QA\video_processor_data\<video_id>`.

Runtime safeguards:

- Maximum upload size: 500 MiB.
- FFmpeg and FFprobe calls have explicit timeouts.
- Successfully processed source videos are removed; extracted JPEG frames are
  retained for Dify access.
- UUID task directories older than 7 days are removed on startup. Unrelated
  directories are not touched.
- `/health` returns success only when FFmpeg and FFprobe are usable.

## Personal PC and GitHub

Use a private GitHub repository. Do not commit `.env` files, model API keys,
uploaded videos, extracted frames, runtime outputs, or virtual environments.

After cloning on another Windows PC:

1. Install Python 3.11 or newer and place portable FFmpeg under
   `E:\AI\Tools\ffmpeg`.
2. Start Docker Desktop and wait for Dify.
3. Double-click `启动FastAPI.cmd`.
4. Import the current workflow DSL into Dify and configure model credentials.

FastAPI source updates can be applied with `git pull` and a service restart.
Dify workflow DSL updates are versioned in Git but must still be imported into
Dify manually.

### First GitHub push

Create a **Private** GitHub repository named `ai-ad-qa-automation` under
`shawking66666-bit`, then double-click `Push-to-GitHub.cmd`. The script uses
repository-local Git identity settings:

- User: `shawking66666-bit`
- Email: `272393408+shawking66666-bit@users.noreply.github.com`

It does not change the company's global Git configuration.

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
