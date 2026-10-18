$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$env:VIDEO_PROCESSOR_DATA_ROOT = "E:\AI\Data\AI-Ad-QA\video_processor_data"
$env:VIDEO_PROCESSOR_PUBLIC_BASE_URL = "http://host.docker.internal:8000"
$env:VIDEO_PROCESSOR_FFMPEG_PATH = "E:\AI\Tools\ffmpeg\bin\ffmpeg.exe"
$env:VIDEO_PROCESSOR_FFPROBE_PATH = "E:\AI\Tools\ffmpeg\bin\ffprobe.exe"
$env:VIDEO_PROCESSOR_MAX_UPLOAD_BYTES = "524288000"
$env:VIDEO_PROCESSOR_RETENTION_HOURS = "168"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

Write-Host "AI Ad QA - FastAPI video processor" -ForegroundColor Cyan
Write-Host "Project: $projectRoot"
Write-Host "Data:    $env:VIDEO_PROCESSOR_DATA_ROOT"

foreach ($executable in @(
    $env:VIDEO_PROCESSOR_FFMPEG_PATH,
    $env:VIDEO_PROCESSOR_FFPROBE_PATH
)) {
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "Required portable FFmpeg executable is missing: $executable"
    }
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

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    $systemPython = Get-Command python -ErrorAction SilentlyContinue
    if (-not $systemPython) {
        throw "Python was not found. Install Python 3.11 or newer."
    }
    Write-Host "Creating project virtual environment..." -ForegroundColor Yellow
    & $systemPython.Source -m venv (Join-Path $projectRoot ".venv")
    if ($LASTEXITCODE -ne 0) {
        throw "Virtual environment creation failed."
    }
}

$ErrorActionPreference = "Continue"
& $venvPython -c "import fastapi, multipart, uvicorn" 2>$null
$dependencyCheckExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($dependencyCheckExitCode -ne 0) {
    Write-Host "Installing dependencies into the project virtual environment..." -ForegroundColor Yellow
    $ErrorActionPreference = "Continue"
    & $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt")
    $dependencyInstallExitCode = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($dependencyInstallExitCode -ne 0) {
        throw "Dependency installation failed."
    }
}

$ErrorActionPreference = "Continue"
& $venvPython -c "from video_processor.service import check_runtime_dependencies; check_runtime_dependencies()"
$runtimeCheckExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($runtimeCheckExitCode -ne 0) {
    throw "FFmpeg dependency check failed."
}

Write-Host "Starting FastAPI at http://localhost:8000" -ForegroundColor Green
Write-Host "Keep this window open. Press Ctrl+C to stop." -ForegroundColor Yellow
$ErrorActionPreference = "Continue"
& $venvPython -m uvicorn video_processor.app:app --host 0.0.0.0 --port 8000
$serverExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"

if ($serverExitCode -ne 0) {
    throw "FastAPI exited with code $serverExitCode."
}
