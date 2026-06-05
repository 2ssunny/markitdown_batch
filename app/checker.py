import os
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from notion_client import Client

SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive.readonly']

def load_config():
    if not os.path.exists('config.json'):
        return None
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

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
                print("[ERROR] 'credentials.json' not found.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def main():
    app_dir = Path(__file__).parent
    history_file = app_dir / 'history.json'
    
    print("----------------------------------------------------------------")
    print("Google Drive Sync Checker Utility")
    print("----------------------------------------------------------------")
    
    history_data = load_history(history_file)
    if not history_data:
        print("[Info] No conversion history (history.json) found to check.")
        return
        
    print("\n[Step 1] Authenticating with Google Drive...")
    drive_service = get_google_drive_service()
    if not drive_service:
        print("Google Drive authentication failed.")
        return

    # Load config for Notion
    config = load_config()
    notion = None
    if config and config.get('NOTION_API_KEY'):
        try:
            notion = Client(auth=config['NOTION_API_KEY'])
            print("[*] Notion API settings verified. (Notion deletion sync enabled)")
        except Exception:
            pass

    print(f"\n[Step 2] Scanning {len(history_data)} file records from history...\n")
    
    hashes_to_remove = []
    
    for file_hash, record in history_data.items():
        original_name = record.get('original_name', 'Unknown')
        drive_file_id = record.get('drive_file_id')
        notion_page_id = record.get('notion_page_id')
        
        if not drive_file_id:
            print(f"▶ {original_name}: No Google Drive ID recorded. Skipping.")
            continue
            
        print(f"▶ Checking: {original_name}")
        is_deleted = False
        
        try:
            # Check file in Google Drive
            file = drive_service.files().get(fileId=drive_file_id, fields='trashed').execute()
            if file.get('trashed', False):
                print("  - [Detected] File is in Google Drive Trash.")
                is_deleted = True
            else:
                print("  - [Normal] File still exists in Google Drive.")
        except HttpError as e:
            if e.resp.status == 404:
                print("  - [Detected] File is permanently deleted from Google Drive.")
                is_deleted = True
            else:
                print(f"  - [Error] Failed to check Drive file status: {e}")
                
        if is_deleted:
            # Archive Notion Page if exists
            if notion and notion_page_id:
                try:
                    notion.pages.update(page_id=notion_page_id, archived=True)
                    print("  - [Success] Archived (deleted) the associated Notion page.")
                except Exception as ne:
                    print(f"  - [Error] Failed to archive Notion page: {ne}")
            elif not notion_page_id:
                 print("  - [Info] No associated Notion page ID. Skipping Notion cleanup.")
            
            # Remove from local history
            hashes_to_remove.append(file_hash)
            print("  - [Success] Marked for removal from local history (history.json).")

    # Apply removals
    if hashes_to_remove:
        for h in hashes_to_remove:
            del history_data[h]
        save_history(history_file, history_data)
        print(f"\n[Result] Removed {len(hashes_to_remove)} deleted file records from local history.")
    else:
        print("\n[Result] No deleted files found. Everything is synchronized.")

if __name__ == '__main__':
    main()
