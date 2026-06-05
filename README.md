# MarkItDown Batch Converter & Uploader

A utility that batch-converts documents (PDF, DOCX, XLSX, PPTX, etc.) in a local folder to Markdown using Microsoft's `markitdown`, uploads them to Google Drive, and syncs the links to a Notion Database.

## Features
- **Batch Conversion**: Converts all supported documents in the `input_files` directory to `.md`.
- **Duplicate Prevention**: Uses SHA-256 hashing to skip files that have already been converted.
- **Google Drive Upload**: Automatically uploads the generated Markdown files to a specific Google Drive folder.
- **Notion Sync**: Syncs the uploaded Google Drive links and embedded Markdown blocks to a specified Notion Database.
- **Auto Cleanup & Sync Check**: Moves successfully processed original files to a `processed_files` directory. Includes a checker to clean up history and Notion pages if the file is deleted from Google Drive.

## Prerequisites
- Python 3.8+
- Google Cloud Project with Google Drive API enabled (OAuth 2.0 Desktop Client).
- Notion Integration Token & Database ID.

## Setup
1. Clone this repository.
2. Put your Google Drive `credentials.json` into the `app/` directory.
3. Rename `app/config.example.json` to `app/config.json` and fill in your Notion API details.
4. Run `run_converter.bat`. The batch script will automatically create a virtual environment, install dependencies, and run the tool.

## Usage
- **Upload**: Drop files you want to convert into the `input_files` folder and run `run_converter.bat`.
- **Check/Cleanup**: Run `run_checker.bat` to scan Google Drive for deleted files and sync deletions to your local history and Notion database.

## Supported Formats
`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.csv`, `.json`, `.xml`, `.html`, `.epub`, `.zip`, `.txt`, `.jpg`, `.png`

---

## Acknowledgments & License
This project utilizes [**MarkItDown**](https://github.com/microsoft/markitdown) by Microsoft for document conversion. `markitdown` is an open-source tool released under the **MIT License**. We respect and acknowledge Microsoft's original work which makes the core functionality of this batch utility possible.

This batch utility is provided as-is, expanding upon the core conversion capabilities of MarkItDown to include automation, cloud storage, and Notion synchronization.
