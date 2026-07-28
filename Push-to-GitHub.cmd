@echo off
chcp 65001 >nul
title AI Ad QA - Push to GitHub
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
  echo Git was not found. Install Git for Windows first.
  pause
  exit /b 1
)

git config --global --add safe.directory "%CD%"
if errorlevel 1 goto :failed

git config --local user.name shawking66666-bit
if errorlevel 1 goto :failed
git config --local user.email shaw.king.66666@gmail.com
if errorlevel 1 goto :failed

git add .
if errorlevel 1 goto :failed

git diff --cached --quiet
if errorlevel 1 (
  git commit -m "Initial AI Ad QA automation workflow"
  if errorlevel 1 goto :failed
) else (
  echo No new files need to be committed.
)

git remote get-url origin >nul 2>&1
if errorlevel 1 (
  git remote add origin https://github.com/shawking66666-bit/ai-ad-qa-automation.git
) else (
  git remote set-url origin https://github.com/shawking66666-bit/ai-ad-qa-automation.git
)
if errorlevel 1 goto :failed

git push -u origin main
if errorlevel 1 goto :failed

echo.
echo GitHub push completed successfully.
pause
exit /b 0

:failed
echo.
echo Operation failed. Review the error above.
echo Repository: https://github.com/shawking66666-bit/ai-ad-qa-automation
pause
exit /b 1
