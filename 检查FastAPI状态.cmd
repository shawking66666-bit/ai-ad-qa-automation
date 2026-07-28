@echo off
chcp 65001 >nul
title AI Ad QA - FastAPI Health Check
cd /d "%~dp0"
rem Health endpoint: http://localhost:8000/health
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0health_check_video_processor.ps1"
echo.
pause
