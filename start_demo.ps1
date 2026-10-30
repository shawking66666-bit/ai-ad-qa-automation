$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "未找到项目虚拟环境。请先运行 启动FastAPI.cmd 完成初始化。"
}

if ([string]::IsNullOrWhiteSpace($env:DIFY_DEMO_API_KEY)) {
    $secureKey = Read-Host "输入 Dify 应用 API Key（输入内容不显示，仅当前进程使用）" -AsSecureString
    $credential = [System.Net.NetworkCredential]::new("", $secureKey)
    $env:DIFY_DEMO_API_KEY = $credential.Password
    Remove-Variable secureKey, credential
}

if ([string]::IsNullOrWhiteSpace($env:DIFY_DEMO_API_KEY)) {
    throw "未输入 Dify 应用 API Key。"
}

Write-Host "演示页启动中：http://127.0.0.1:8001"
Push-Location $projectRoot
try {
    & $pythonPath -m uvicorn demo.app:app --host 127.0.0.1 --port 8001
} finally {
    Pop-Location
    Remove-Item Env:DIFY_DEMO_API_KEY -ErrorAction SilentlyContinue
}
