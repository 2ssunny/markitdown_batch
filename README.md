# MarkItDown Batch Converter & Uploader

A utility that batch-converts documents (PDF, DOCX, XLSX, PPTX, etc.) in a local folder to Markdown using Microsoft's `markitdown`, uploads them to Google Drive, and syncs the links to a Notion Database.

## Features
- **Batch Conversion**: Converts all supported documents in the `input_files` directory to `.md`.
- **Duplicate Prevention**: Uses SHA-256 hashing to skip files that have already been converted.
- **Google Drive Upload**: Automatically uploads the generated Markdown files to a specific Google Drive folder.
- **Notion Sync**: Syncs the uploaded Google Drive links to a specified Notion Database.
- **Auto Cleanup**: Moves successfully processed original files to a `processed_files` directory and deletes local `.md` copies.

## Prerequisites
- Python 3.8+
- Google Cloud Project with Google Drive API enabled (OAuth 2.0 Desktop Client).
- Notion Integration Token & Database ID.

## Setup
1. Clone this repository.
2. Put your Google Drive `credentials.json` into the root directory.
3. Rename `config.example.json` to `config.json` and fill in your Notion API details.
4. Run `run_converter.bat`. The batch script will automatically create a virtual environment, install dependencies, and run the tool.

## Usage
- Drop files you want to convert into the `input_files` folder.
- Double click `run_converter.bat`.
- Converted original files will be moved to `processed_files`.

## Supported Formats
`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.csv`, `.json`, `.xml`, `.html`, `.epub`, `.zip`, `.txt`, `.jpg`, `.png`
