@echo off
chcp 65001 >nul
title AI Ad QA - Initialize GitHub
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
git config --local user.email shaw.king.66666@gmail.com
git add .

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

git push -u origin main
if errorlevel 1 goto :failed

echo.
echo GitHub push completed successfully.
pause
exit /b 0

:failed
echo.
echo Operation failed. Confirm that the private GitHub repository exists and sign in when prompted.
pause
exit /b 1
