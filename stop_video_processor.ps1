$ErrorActionPreference = "Stop"

$listeners = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $listeners) {
    Write-Host "FastAPI is not running on port 8000." -ForegroundColor Yellow
    exit 0
}

$stopped = $false
foreach ($listener in $listeners) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    $commandLine = [string]$process.CommandLine

    if ($commandLine -match "uvicorn" -and $commandLine -match "video_processor\.app:app") {
        Stop-Process -Id $listener.OwningProcess -Force
        Write-Host "Stopped FastAPI process $($listener.OwningProcess)." -ForegroundColor Green
        $stopped = $true
    }
}

if (-not $stopped) {
    throw "Port 8000 is used by another application. It was not stopped."
}
