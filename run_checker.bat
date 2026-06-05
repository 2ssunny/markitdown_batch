@echo off
setlocal

cd /d "%~dp0"

echo Checking Python virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Please run run_converter.bat first to set up the environment.
    pause
    exit /b 1
)

echo Activating existing virtual environment...
call venv\Scripts\activate.bat

echo Running the sync checker script...
python checker.py

echo.
echo ========================================================
echo Done.
pause
