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
                print("[ERROR] 'credentials.json' 파일을 찾을 수 없습니다.")
                print("Google Cloud Console에서 프로젝트를 생성하고, Google Drive API를 활성화한 뒤")
                print("OAuth 2.0 클라이언트 ID(데스크톱 앱)의 자격 증명 파일을 다운로드하여")
                print("이 폴더에 'credentials.json' 이라는 이름으로 저장해주세요.")
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
            print(f"[*] 기존 Google Drive 폴더 '{folder_name}'를 찾았습니다. (ID: {files[0]['id']})")
            return files[0]['id']
        else:
            print(f"[*] 새 Google Drive 폴더 '{folder_name}'를 생성하는 중...")
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=file_metadata, fields='id').execute()
            print(f"[*] 폴더 생성 완료. (ID: {folder.get('id')})")
            return folder.get('id')
    except HttpError as error:
        print(f"[ERROR] 폴더 검색/생성 중 오류 발생: {error}")
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
        print(f"[ERROR] 파일 업로드 중 오류 발생 {file_path}: {error}")
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
        print(f"[ERROR] Notion 동기화 중 오류 발생: {str(e)}")
        print("참고: 노션 데이터베이스에 'Name'(제목 속성)과 'URL'(URL 속성)이 존재하는지 확인하세요.")
        return False, None

def main():
    base_dir = Path(__file__).parent
    input_dir = base_dir / 'input_files'
    processed_dir = base_dir / 'processed_files'
    history_file = base_dir / 'history.json'
    
    input_dir.mkdir(exist_ok=True)
    processed_dir.mkdir(exist_ok=True)
    
    print("----------------------------------------------------------------")
    print("MarkItDown 구글 드라이브 일괄 변환 및 노션 동기화 유틸리티 시작")
    print("----------------------------------------------------------------")
    
    # Load config for Notion
    config = load_config()
    notion = None
    notion_db_id = None
    if config and config.get('NOTION_API_KEY') and config.get('NOTION_DATABASE_ID'):
        try:
            notion = Client(auth=config['NOTION_API_KEY'])
            notion_db_id = config['NOTION_DATABASE_ID']
            print("\n[*] Notion API 설정이 확인되었습니다. (동기화 활성화됨)")
        except Exception as e:
            print(f"\n[WARNING] Notion 클라이언트 초기화 실패: {e}")
    else:
        print("\n[*] 'config.json'에 Notion API 설정이 없어 노션 동기화는 건너뜁니다.")
    
    # Authenticate and get Drive service
    print("\n[단계 1] Google Drive 인증 진행 중...")
    service = get_google_drive_service()
    if not service:
        print("Google Drive 인증에 실패하여 스크립트를 종료합니다.")
        return
        
    folder_id = get_or_create_folder(service, DRIVE_FOLDER_NAME)
    if not folder_id:
        print("대상 폴더를 찾거나 생성하지 못해 스크립트를 종료합니다.")
        return

    # Get files to process
    files_to_process = [f for f in input_dir.iterdir() if f.is_file()]
    if not files_to_process:
        print(f"\n[알림] '{input_dir.name}' 폴더에 처리할 파일이 없습니다.")
        return
        
    print(f"\n[단계 2] 총 {len(files_to_process)}개의 파일을 확인했습니다.")
    print("MarkItDown 초기화 중...")
    md = MarkItDown()
    
    history_data = load_history(history_file)
    
    for file_path in files_to_process:
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            print(f"  -> [스킵] 지원하지 않는 확장자입니다: {file_path.name}")
            continue
            
        print(f"\n▶ 처리 중: {file_path.name}")
        
        # Check duplicate via hash
        file_hash = get_file_hash(file_path)
        if file_hash in history_data:
            print(f"  -> [알림] 이미 변환/업로드가 완료된 중복 파일입니다. (스킵)")
            continue
            
        md_file_path = base_dir / f"{file_path.stem}.md"
        
        try:
            # Convert
            print(f"  - Markdown으로 변환 중...")
            result = md.convert(str(file_path))
            md_content = result.text_content
            with open(md_file_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
                
            # Upload
            print(f"  - Google Drive '{DRIVE_FOLDER_NAME}' 폴더로 업로드 중...")
            success, drive_link, drive_file_id = upload_file(service, str(md_file_path), folder_id)
            
            # Clean up & Sync
            if success:
                print("  - 구글 드라이브 업로드 완료.")
                
                # Notion Sync
                notion_page_id = None
                if notion and notion_db_id and drive_link:
                    print("  - 노션 데이터베이스에 동기화 및 본문 삽입 중...")
                    sync_success, page_id = sync_to_notion(notion, notion_db_id, md_file_path.name, drive_link, md_content)
                    if sync_success:
                        notion_page_id = page_id
                        print("  - [완료] 노션 동기화 성공!")
                
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
                
                print(f"  - [완료] 원본 파일을 '{processed_dir.name}' 폴더로 이동했습니다.")
            else:
                print("  - [실패] 업로드에 실패했습니다. 다음 시도를 위해 파일을 유지합니다.")
                
        except Exception as e:
            print(f"  - [ERROR] '{file_path.name}' 처리 중 오류 발생: {str(e)}")

if __name__ == '__main__':
    main()
