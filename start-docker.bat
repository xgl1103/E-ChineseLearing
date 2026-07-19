@echo off
cd /d "%~dp0"
echo Building and starting AI Lesson Recorder containers...
docker compose up --build
pause
