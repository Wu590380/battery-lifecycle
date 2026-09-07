@echo off
chcp 936 >nul
title AI Battery Lifecycle - Launcher
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

echo [1/2] Checking dependencies...
pip install -r requirements.txt -q
echo       Done.

echo [2/2] Starting services...
python -u launcher.py
