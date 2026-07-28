$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$env:VIDEO_PROCESSOR_DATA_ROOT = "D:\AI-Ad-QA-Data\video_processor_data"
$env:VIDEO_PROCESSOR_PUBLIC_BASE_URL = "http://host.docker.internal:8000"

Write-Host "AI Ad QA - FastAPI video processor" -ForegroundColor Cyan
Write-Host "Project: $projectRoot"
Write-Host "Data:    $env:VIDEO_PROCESSOR_DATA_ROOT"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found. Install Python 3.11 or newer and enable Add Python to PATH."
}

if (-not (Test-Path -LiteralPath $env:VIDEO_PROCESSOR_DATA_ROOT)) {
    New-Item -ItemType Directory -Force -Path $env:VIDEO_PROCESSOR_DATA_ROOT | Out-Null
    Write-Host "Created data directory." -ForegroundColor Green
}

for ($attempt = 1; $attempt -le 2; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
        if ($health.status -eq "ok") {
            Write-Host "FastAPI is already running at http://localhost:8000" -ForegroundColor Green
            exit 0
        }
    }
    catch {
        if ($attempt -lt 2) {
            Start-Sleep -Milliseconds 500
        }
    }
}

python -c "import fastapi, multipart, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Python dependencies from requirements.txt..." -ForegroundColor Yellow
    python -m pip install -r (Join-Path $projectRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed."
    }
}

Write-Host "Starting FastAPI at http://localhost:8000" -ForegroundColor Green
Write-Host "Keep this window open. Press Ctrl+C to stop." -ForegroundColor Yellow
python -m uvicorn video_processor.app:app --host 0.0.0.0 --port 8000

if ($LASTEXITCODE -ne 0) {
    throw "FastAPI exited with code $LASTEXITCODE."
}
