# MarkItDown Batch Converter & Uploader

A utility that batch-converts documents (PDF, DOCX, XLSX, PPTX, etc.) in a local folder to Markdown using Microsoft's `markitdown`, uploads them to Google Drive, and syncs the links to a Notion Database. It also features a built-in Local OCR fallback to extract text from scanned PDFs.

## Features
- **Batch Conversion**: Converts all supported documents in the `input_files` directory to `.md`.
- **Local OCR Fallback (NEW)**: Automatically detects scanned PDFs (images without a text layer) and extracts text using Tesseract OCR.
- **Dual Engine OCR Architecture**: Choose between `tesseract` (default, fast) and `easyocr` (high accuracy for complex/handwritten text). The script dynamically installs EasyOCR dependencies only if requested.
- **Dynamic OCR Model Download**: Specify any language in `config.json` (e.g., `jpn`, `fra`), and the script will automatically download the required high-accuracy `tessdata_best` models from the official GitHub repository on the fly.
- **Duplicate Prevention**: Uses SHA-256 hashing to skip files that have already been converted.
- **Google Drive Upload**: Automatically uploads the generated Markdown files to a specific Google Drive folder.
- **Notion Sync**: Syncs the uploaded Google Drive links and embedded Markdown blocks to a specified Notion Database.
- **Auto Cleanup & Sync Check**: Moves successfully processed original files to a `processed_files` directory. Includes a checker (`run_checker.bat`) to clean up history and Notion pages if the file is deleted from Google Drive.

## Prerequisites
- Python 3.8+
- Google Cloud Project with Google Drive API enabled (OAuth 2.0 Desktop Client).
- Notion Integration Token & Database ID.

## Setup Guide

To use this utility, you must authenticate with both Google Drive and Notion. Follow the detailed steps below.

### 1. Google Drive API Authentication (`credentials.json`)
You need a `credentials.json` file so the script can upload files to your Google Drive.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a **New Project**.
3. Navigate to **APIs & Services > Library**, search for **Google Drive API**, and click **Enable**.
4. Go to **APIs & Services > OAuth consent screen**. Choose **External** (or Internal if you have a Google Workspace) and fill out the required basic information.
5. Go to **APIs & Services > Credentials**.
6. Click **+ CREATE CREDENTIALS** and select **OAuth client ID**.
7. Choose **Desktop app** as the Application type, give it a name, and click **Create**.
8. Download the JSON file, rename it to **`credentials.json`**, and place it inside the **`app/`** folder of this repository.

### 2. Notion API Integration (`config.json`)
You need an Internal Integration Token and a Database ID to sync files to Notion.

1. **Create an Integration (Bot):**
   - Go to [Notion My Integrations](https://www.notion.so/my-integrations).
   - Click **+ New integration**. Select the workspace you want to use, give the integration a name, and ensure the type is **Internal** (or Secret Token).
   - Once created, copy the **Internal Integration Secret** (it starts with `secret_...`).

2. **Prepare your Notion Database:**
   - In your Notion workspace, create a new Database (Full page or Inline).
   - You must have exactly these two properties (case-sensitive):
     - **`Name`** (Property type: `Title` / `제목`)
     - **`URL`** (Property type: `URL`)
   - Click the `...` menu in the top right of your database page, select **Add connections (연결 추가)**, and search for the name of the integration you just created to invite it to the database.

3. **Get the Database ID:**
   - Copy the link to your Notion database page.
   - The URL will look like this: `https://www.notion.so/myworkspace/a1b2c3d4e5f6g7h8i9j0?v=...`
   - The long alphanumeric string between your workspace name and the `?v=` is your **Database ID** (in this example, `a1b2c3d4e5f6g7h8i9j0`).

4. **Configure the script:**
   - Rename `app/config.example.json` to **`app/config.json`**.
   - Open `app/config.json` and paste your copied Integration Secret into `NOTION_API_KEY` and your Database ID into `NOTION_DATABASE_ID`.
   - **`OCR_ENGINE`**: Set to `"tesseract"` (default) or `"easyocr"`.
     > **⚠️ WARNING for EasyOCR users:** `easyocr` installs PyTorch (~2GB). If you do not have a CUDA-enabled NVIDIA GPU configured, it will run on your CPU and can be **extremely slow**. Only use `easyocr` if you have CUDA setup or absolutely need high-accuracy handwriting extraction.
   - **`OCR_LANG`**: Define the target language for OCR (e.g., `"eng"`, `"kor"`, `"eng+kor"`, `"jpn"`). If the required high-accuracy models are missing locally, the script will automatically download them for you. The script also automatically maps Tesseract codes to EasyOCR codes.

### 3. Run the Tool
Once both API credentials are in the `app/` folder:
1. Drop files you want to convert into the `input_files/` folder.
2. Run `run_converter.bat`. 
   *(The batch script will automatically download Tesseract OCR if it's missing, create a virtual environment, install dependencies, and execute the conversion and sync.)*
   - **Note on OCR:** When installing Tesseract, make sure to expand "Additional language data" and check "Korean" to support Korean text extraction from scanned PDFs.

## Usage Details
- **Upload (`run_converter.bat`)**: Converts files, falls back to OCR for scanned PDFs, uploads to Google Drive, writes the markdown content to the Notion Database, and moves the original files to `processed_files/`.
- **Check/Cleanup (`run_checker.bat`)**: Scans Google Drive for files that you might have deleted. If it detects a deleted file, it will sync this deletion to your local history and move the corresponding Notion page to the trash.

## Supported Formats
`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.csv`, `.json`, `.xml`, `.html`, `.epub`, `.zip`, `.txt`, `.jpg`, `.png`

---

## Acknowledgments & License

This project utilizes several powerful open-source tools:

1. [**MarkItDown**](https://github.com/microsoft/markitdown) by Microsoft. 
   - Used for document conversion. Released under the **MIT License**. We respect and acknowledge Microsoft's original work which makes the core functionality of this batch utility possible.

2. [**Tesseract OCR**](https://github.com/tesseract-ocr/tesseract) by Tesseract.
   - Used for the Local OCR fallback functionality to extract text from scanned PDFs. Released under the **Apache License 2.0**.

This batch utility is provided as-is, expanding upon the core capabilities of these tools to include automation, OCR fallbacks, cloud storage, and Notion synchronization.
