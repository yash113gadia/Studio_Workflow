@echo off
title Preeti Studio - AI Film & Video Creator
color 0B

echo =======================================================
echo         PREETI STUDIO - AI FILM & VIDEO CREATOR       
echo =======================================================
echo.
echo Starting Preeti Studio...
cd /d "C:\Users\nikhi\Preeti_Studio"

:: Ensure the local image/video engine is available too
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_comfy.ps1

:: Check if server is already running on port 8000
netstat -ano | findstr :8000 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo Preeti Studio is already running!
) else (
    echo Launching local AI engine...
    start /B "" "environments\studio_core_env\Scripts\python.exe" scripts\run_server.py
    timeout /t 3 /nobreak >nul
)

echo Opening Web UI in your browser...
start http://127.0.0.1:8000/

echo.
echo =======================================================
echo  Studio is open at: http://127.0.0.1:8000/
echo  Ready to create videos! 
echo =======================================================
echo.
timeout /t 5
