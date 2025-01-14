@echo off

:: Store the current working directory
set CURRENT_DIR=%CD%

:: Check for administrative privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrative privileges...
    PowerShell -Command "Start-Process cmd -ArgumentList '/c cd /d \"%CURRENT_DIR%\" && %~f0' -Verb RunAs"
    exit /b
)

:: Run the Python script
python poe_xp_tracker.py

:: Pause the window to show any output
pause
