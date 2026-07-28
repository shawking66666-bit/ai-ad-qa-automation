@echo off
chcp 65001 >nul
title AI Ad QA - Stop FastAPI
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_video_processor.ps1"
echo.
pause
