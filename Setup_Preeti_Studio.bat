@echo off
title Preeti Studio - One-time setup
color 0B
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows.ps1" %*

echo.
pause
