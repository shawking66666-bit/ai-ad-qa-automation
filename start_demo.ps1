$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Project virtual environment not found. Run the FastAPI launcher first."
}

if ([string]::IsNullOrWhiteSpace($env:DIFY_DEMO_API_KEY)) {
    $secureKey = Read-Host "Enter the Dify app API key (hidden, current process only)" -AsSecureString
    $credential = [System.Net.NetworkCredential]::new("", $secureKey)
    $env:DIFY_DEMO_API_KEY = $credential.Password
    Remove-Variable secureKey, credential
}

if ([string]::IsNullOrWhiteSpace($env:DIFY_DEMO_API_KEY)) {
    throw "Dify app API key is required."
}

Write-Host "Demo page starting: http://127.0.0.1:8001"
Push-Location $projectRoot
try {
    & $pythonPath -m uvicorn demo.app:app --host 127.0.0.1 --port 8001
} finally {
    Pop-Location
    Remove-Item Env:DIFY_DEMO_API_KEY -ErrorAction SilentlyContinue
}
