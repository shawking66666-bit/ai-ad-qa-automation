$ErrorActionPreference = "Stop"
$healthUrl = "http://localhost:8000/health"

try {
    $response = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 5
    if ($response.status -ne "ok") {
        throw "Unexpected response: $($response | ConvertTo-Json -Compress)"
    }

    Write-Host "FastAPI is running normally." -ForegroundColor Green
    Write-Host "Health URL: $healthUrl"
    exit 0
}
catch {
    Write-Host "FastAPI is not available." -ForegroundColor Red
    Write-Host "Double-click Start-FastAPI.cmd first."
    Write-Host "Details: $($_.Exception.Message)"
    exit 1
}
