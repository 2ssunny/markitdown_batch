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
                print("[ERROR] 'credentials.json' 파일을 찾을 수 없습니다.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def main():
    base_dir = Path(__file__).parent
    history_file = base_dir / 'history.json'
    
    print("----------------------------------------------------------------")
    print("구글 드라이브 동기화 상태 점검 도구 (Checker) 시작")
    print("----------------------------------------------------------------")
    
    history_data = load_history(history_file)
    if not history_data:
        print("[알림] 점검할 변환 기록(history.json)이 없습니다.")
        return
        
    print("\n[단계 1] Google Drive 인증 진행 중...")
    drive_service = get_google_drive_service()
    if not drive_service:
        print("Google Drive 인증 실패.")
        return

    # Load config for Notion
    config = load_config()
    notion = None
    if config and config.get('NOTION_API_KEY'):
        try:
            notion = Client(auth=config['NOTION_API_KEY'])
            print("[*] Notion API 설정 확인됨. (노션 삭제 연동 활성화)")
        except Exception:
            pass

    print(f"\n[단계 2] 총 {len(history_data)}개의 파일 기록을 검사합니다...\n")
    
    hashes_to_remove = []
    
    for file_hash, record in history_data.items():
        original_name = record.get('original_name', 'Unknown')
        drive_file_id = record.get('drive_file_id')
        notion_page_id = record.get('notion_page_id')
        
        if not drive_file_id:
            print(f"▶ {original_name}: 구글 드라이브 ID가 기록되어 있지 않아 검사 스킵.")
            continue
            
        print(f"▶ 검사 중: {original_name}")
        is_deleted = False
        
        try:
            # Check file in Google Drive
            file = drive_service.files().get(fileId=drive_file_id, fields='trashed').execute()
            if file.get('trashed', False):
                print("  - [감지] 구글 드라이브 휴지통으로 이동된 것을 확인했습니다.")
                is_deleted = True
            else:
                print("  - [정상] 구글 드라이브에 파일이 존재합니다.")
        except HttpError as e:
            if e.resp.status == 404:
                print("  - [감지] 구글 드라이브에서 파일이 완전히 삭제된 것을 확인했습니다.")
                is_deleted = True
            else:
                print(f"  - [오류] 드라이브 상태 확인 중 에러: {e}")
                
        if is_deleted:
            # Archive Notion Page if exists
            if notion and notion_page_id:
                try:
                    notion.pages.update(page_id=notion_page_id, archived=True)
                    print("  - [처리 완료] 연결된 노션 페이지를 삭제(휴지통 이동)했습니다.")
                except Exception as ne:
                    print(f"  - [오류] 노션 페이지 삭제 실패: {ne}")
            elif not notion_page_id:
                 print("  - [알림] 연결된 노션 페이지 ID가 없어 노션 처리는 건너뜁니다.")
            
            # Remove from local history
            hashes_to_remove.append(file_hash)
            print("  - [처리 완료] 로컬 기록(history.json)에서 삭제 예약됨.")

    # Apply removals
    if hashes_to_remove:
        for h in hashes_to_remove:
            del history_data[h]
        save_history(history_file, history_data)
        print(f"\n[결과] 총 {len(hashes_to_remove)}개의 삭제된 파일 기록이 로컬에서 지워졌습니다.")
    else:
        print("\n[결과] 지워진 파일이 없습니다. 모두 정상 동기화 상태입니다.")

if __name__ == '__main__':
    main()
