@echo off
setlocal

cd /d "%~dp0"

echo [1/5] Checking Tesseract OCR installation...
if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo Downloading Tesseract OCR Installer. Please wait a minute...
    curl.exe -L -o tesseract_installer.exe "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
    
    echo.
    echo --------------------------------------------------------
    echo [ACTION REQUIRED]
    echo The Tesseract installer will now launch.
    echo IMPORTANT: During installation, expand "Additional language data" and check "Korean"!
    echo Please proceed with the default installation path.
    echo --------------------------------------------------------
    start /wait tesseract_installer.exe
    del tesseract_installer.exe
    
    if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        echo You must install Tesseract OCR to the default path to continue. Exiting.
        pause
        exit /b 1
    )
)

echo [2/5] Downloading tessdata_best models (High Accuracy OCR)...
if not exist "app\tessdata_best" mkdir "app\tessdata_best"
if not exist "app\tessdata_best\eng.traineddata" (
    echo Downloading eng.traineddata - 14.5 MB...
    curl.exe -L -o "app\tessdata_best\eng.traineddata" "https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata"
)
if not exist "app\tessdata_best\kor.traineddata" (
    echo Downloading kor.traineddata - 34.6 MB...
    curl.exe -L -o "app\tessdata_best\kor.traineddata" "https://github.com/tesseract-ocr/tessdata_best/raw/main/kor.traineddata"
)
if not exist "app\tessdata_best\osd.traineddata" (
    echo Downloading osd.traineddata - 10.3 MB...
    curl.exe -L -o "app\tessdata_best\osd.traineddata" "https://github.com/tesseract-ocr/tessdata_best/raw/main/osd.traineddata"
)

echo [3/5] Checking input_files and processed_files directories...
if not exist "input_files" mkdir "input_files"
if not exist "processed_files" mkdir "processed_files"

echo [4/5] Checking Python virtual environment...
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

echo [5/5] Running the converter script...
cd app
python converter.py

echo.
echo ========================================================
echo Done.
pause
