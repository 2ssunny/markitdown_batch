@echo off
setlocal

cd /d "%~dp0"

echo [1/3] Checking input_files and processed_files directories...
if not exist "input_files" mkdir "input_files"
if not exist "processed_files" mkdir "processed_files"

echo [2/3] Checking Python virtual environment...
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    if errorlevel 1 (
        echo Failed to create virtual environment. Please ensure Python is installed and added to PATH.
        pause
        exit /b 1
    )
    echo Activating virtual environment and installing dependencies...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r app\requirements.txt
) else (
    echo Activating existing virtual environment...
    call venv\Scripts\activate.bat
)

echo [3/3] Running the converter script...
cd app
python converter.py

echo.
echo ========================================================
echo Done.
pause
