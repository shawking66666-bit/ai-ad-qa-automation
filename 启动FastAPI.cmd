@echo off
chcp 65001 >nul
title AI Ad QA - FastAPI
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_video_processor.ps1"
if errorlevel 1 (
  echo.
  echo FastAPI failed to start. Review the error above.
  pause
)
