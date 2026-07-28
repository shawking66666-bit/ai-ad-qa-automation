# AI Ad QA Video Processor

Local FastAPI service used by the Dify workflow to extract fixed-time JPEG
frames from uploaded MP4 and MOV advertising videos.

## Start

On Windows, the easiest option is to double-click:

- `启动FastAPI.cmd` — start the service and keep its window open.
- `检查FastAPI状态.cmd` — verify `http://localhost:8000/health`.
- `停止FastAPI.cmd` — stop only this project's Uvicorn process.

The first start creates `D:\AI-Ad-QA-Data\video_processor_data` and installs
missing Python packages from `requirements.txt`.

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
`D:\AI-Ad-QA-Data\video_processor_data\<video_id>`.

## Personal PC and GitHub

Use a private GitHub repository. Do not commit `.env` files, model API keys,
uploaded videos, extracted frames, runtime outputs, or virtual environments.

After cloning on another Windows PC:

1. Install Python 3.11 or newer and FFmpeg.
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
- Email: `shaw.king.66666@gmail.com`

It does not change the company's global Git configuration.

## Test

```powershell
python -m unittest discover -s tests -v
```
