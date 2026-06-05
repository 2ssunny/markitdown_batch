import os
import shutil
import json
import hashlib
from pathlib import Path
from markitdown import MarkItDown
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from notion_client import Client
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import urllib.request

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive.readonly']
DRIVE_FOLDER_NAME = 'mdconversion'

# markitdown supported file extensions
SUPPORTED_EXTENSIONS = {
    '.pdf', '.docx', '.pptx', '.xlsx', '.csv', '.json', '.xml', 
    '.html', '.htm', '.epub', '.zip', '.txt', '.jpg', '.jpeg', '.png'
}

def load_config():
    if not os.path.exists('config.json'):
        return None
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_file_hash(filepath):
    """Calculate SHA-256 hash of a file's contents."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()

def load_history(history_file):
    if not os.path.exists(history_file):
        return {}
    with open(history_file, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_history(history_file, history_data):
    with open(history_file, 'w', encoding='utf-8') as f:
        json.dump(history_data, f, indent=4, ensure_ascii=False)

def get_google_drive_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("================================================================")
                print("[ERROR] 'credentials.json' not found.")
                print("Create a project in Google Cloud Console, enable Google Drive API,")
                print("download the OAuth 2.0 Client ID (Desktop App) credentials file,")
                print("and save it in the 'app' folder as 'credentials.json'.")
                print("================================================================")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('drive', 'v3', credentials=creds)

def get_or_create_folder(service, folder_name):
    try:
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])
        
        if files:
            print(f"[*] Found existing Google Drive folder '{folder_name}' (ID: {files[0]['id']})")
            return files[0]['id']
        else:
            print(f"[*] Creating new Google Drive folder '{folder_name}'...")
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=file_metadata, fields='id').execute()
            print(f"[*] Folder created successfully. (ID: {folder.get('id')})")
            return folder.get('id')
    except HttpError as error:
        print(f"[ERROR] Failed to search/create folder: {error}")
        return None

def upload_file(service, file_path, folder_id):
    try:
        file_name = os.path.basename(file_path)
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, mimetype='text/markdown', resumable=True)
        # Request webViewLink and id
        file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        return True, file.get('webViewLink'), file.get('id')
    except HttpError as error:
        print(f"[ERROR] Failed to upload {file_path}: {error}")
        return False, None, None

def sync_to_notion(notion_client, db_id, file_name, drive_link, md_content=""):
    if not notion_client or not db_id:
        return False, None
        
    try:
        children = []
        if md_content:
            # Chunk text to avoid Notion's 2000 character limit per block
            # Max 100 blocks per request
            chunks = [md_content[i:i+2000] for i in range(0, len(md_content), 2000)][:100] 
            for chunk in chunks:
                children.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": chunk}}],
                        "language": "markdown"
                    }
                })

        new_page = {
            "parent": {"database_id": db_id},
            "properties": {
                "Name": {"title": [{"text": {"content": file_name}}]},
                "URL": {"url": drive_link}
            },
            "children": children
        }
        response = notion_client.pages.create(**new_page)
        return True, response.get("id")
    except Exception as e:
        print(f"[ERROR] Failed to sync to Notion: {str(e)}")
        print("Note: Ensure your Notion Database has a Title property named 'Name' and a URL property named 'URL'.")
        return False, None

def download_missing_models(tessdata_dir, ocr_lang):
    tessdata_dir.mkdir(exist_ok=True)
    langs = ocr_lang.split('+')
    if 'osd' not in langs:
        langs.append('osd')
        
    for lang in langs:
        model_file = tessdata_dir / f"{lang}.traineddata"
        if not model_file.exists():
            print(f"      -> [OCR] Downloading missing model '{lang}' (High Accuracy)...")
            url = f"https://github.com/tesseract-ocr/tessdata_best/raw/main/{lang}.traineddata"
            try:
                urllib.request.urlretrieve(url, model_file)
            except Exception as e:
                print(f"      -> [OCR Error] Failed to download {lang} model: {e}")

def extract_text_with_ocr(pdf_path, ocr_lang='eng+kor'):
    app_dir = Path(__file__).parent
    tessdata_dir = app_dir / 'tessdata_best'
    
    download_missing_models(tessdata_dir, ocr_lang)
    
    # Use environment variable to avoid Windows path quoting issues
    if tessdata_dir.exists():
        os.environ['TESSDATA_PREFIX'] = str(tessdata_dir)
        print(f"      -> [OCR] Extracting text using Tesseract (Language: {ocr_lang}, Model: tessdata_best)...")
    else:
        print(f"      -> [OCR] Extracting text using Tesseract (Language: {ocr_lang}, Model: default)...")

    text_content = ""
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=300)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            page_text = pytesseract.image_to_string(img, lang=ocr_lang)
            text_content += f"\n\n--- Page {i+1} ---\n\n" + page_text
        doc.close()
    except Exception as e:
        print(f"      -> [OCR Error] Failed to OCR pdf: {e}")
    return text_content.strip()

def main():
    app_dir = Path(__file__).parent
    base_dir = app_dir.parent
    input_dir = base_dir / 'input_files'
    processed_dir = base_dir / 'processed_files'
    history_file = app_dir / 'history.json'
    
    input_dir.mkdir(exist_ok=True)
    processed_dir.mkdir(exist_ok=True)
    
    print("----------------------------------------------------------------")
    print("MarkItDown Google Drive Batch Converter & Notion Sync Utility")
    print("----------------------------------------------------------------")
    
    # Load config for Notion
    config = load_config()
    notion = None
    notion_db_id = None
    if config and config.get('NOTION_API_KEY') and config.get('NOTION_DATABASE_ID'):
        try:
            notion = Client(auth=config['NOTION_API_KEY'])
            notion_db_id = config['NOTION_DATABASE_ID']
            print("\n[*] Notion API settings verified. (Sync Enabled)")
        except Exception as e:
            print(f"\n[WARNING] Failed to initialize Notion client: {e}")
    else:
        print("\n[*] No Notion API settings found in 'config.json'. Skipping Notion sync.")
    
    # Authenticate and get Drive service
    print("\n[Step 1] Authenticating with Google Drive...")
    service = get_google_drive_service()
    if not service:
        print("Google Drive authentication failed. Exiting script.")
        return
        
    folder_id = get_or_create_folder(service, DRIVE_FOLDER_NAME)
    if not folder_id:
        print("Failed to find or create target folder. Exiting script.")
        return

    # Get files to process
    files_to_process = [f for f in input_dir.iterdir() if f.is_file()]
    if not files_to_process:
        print(f"\n[Info] No files found in '{input_dir.name}' directory to process.")
        return
        
    print(f"\n[Step 2] Found {len(files_to_process)} files to process.")
    print("Initializing MarkItDown...")
    md = MarkItDown()
    
    history_data = load_history(history_file)
    
    for file_path in files_to_process:
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(f"  -> [Skip] Unsupported file extension: {file_path.name}")
            continue
            
        print(f"\n▶ Processing: {file_path.name}")
        
        # Check duplicate via hash
        file_hash = get_file_hash(file_path)
        if file_hash in history_data:
            print(f"  -> [Info] Duplicate file detected. Moving to '{processed_dir.name}' folder and skipping...")
            dest_path = processed_dir / file_path.name
            if dest_path.exists():
                import time
                dest_path = processed_dir / f"{file_path.stem}_{int(time.time())}{file_path.suffix}"
            shutil.move(str(file_path), str(dest_path))
            continue
            
        md_file_path = app_dir / f"{file_path.stem}.md"
        
        try:
            # Convert
            print(f"  - Converting to Markdown...")
            result = md.convert(str(file_path))
            md_content = result.text_content
            
            # Local OCR Fallback for empty/short scanned PDFs
            if (not md_content or len(md_content.strip()) < 50) and file_path.suffix.lower() == '.pdf':
                print("  - [Info] No readable text found. Falling back to Local OCR...")
                ocr_lang_setting = config.get('OCR_LANG', 'eng+kor') if config else 'eng+kor'
                ocr_text = extract_text_with_ocr(str(file_path), ocr_lang=ocr_lang_setting)
                if ocr_text:
                    md_content = ocr_text
                    print("  - [Success] Local OCR extracted text successfully.")
                else:
                    print("  - [Warning] Local OCR also failed to extract text.")

            with open(md_file_path, 'w', encoding='utf-8') as f:
                f.write(md_content if md_content else "")
                
            # Upload
            print(f"  - Uploading to Google Drive '{DRIVE_FOLDER_NAME}' folder...")
            success, drive_link, drive_file_id = upload_file(service, str(md_file_path), folder_id)
            
            # Clean up & Sync
            if success:
                print("  - Google Drive upload successful.")
                
                # Notion Sync
                notion_page_id = None
                if notion and notion_db_id and drive_link:
                    print("  - Syncing to Notion Database and embedding content...")
                    sync_success, page_id = sync_to_notion(notion, notion_db_id, md_file_path.name, drive_link, md_content)
                    if sync_success:
                        notion_page_id = page_id
                        print("  - [Success] Notion sync completed!")
                
                os.remove(md_file_path)
                
                dest_path = processed_dir / file_path.name
                if dest_path.exists():
                    import time
                    dest_path = processed_dir / f"{file_path.stem}_{int(time.time())}{file_path.suffix}"
                shutil.move(str(file_path), str(dest_path))
                
                # Record in history
                history_data[file_hash] = {
                    "original_name": file_path.name,
                    "drive_link": drive_link,
                    "drive_file_id": drive_file_id,
                    "notion_page_id": notion_page_id
                }
                save_history(history_file, history_data)
                
                print(f"  - [Success] Moved original file to '{processed_dir.name}' folder.")
            else:
                print("  - [Failed] Upload failed. Keeping files locally for retry.")
                
        except Exception as e:
            print(f"  - [ERROR] Failed to process '{file_path.name}': {str(e)}")

if __name__ == '__main__':
    main()
