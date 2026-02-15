import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import traceback

# YouTube Data API v3 scopes
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

def _is_token_valid(path: str) -> bool:
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            return False
        with open(path, 'rb') as token:
            creds = pickle.load(token)
            return bool(creds and getattr(creds, "valid", False))
    except Exception:
        return False

def get_authenticated_service(client_secrets_file: str = "client_secrets.json", token_pickle_file: str = "token.pickle"):
    """
    YouTube Data APIの認証を行い、サービスオブジェクトを返す。
    """
    credentials = None
    
    # token.pickleが存在する場合はロード
    if os.path.exists(token_pickle_file):
        print("  - 既存のトークンを読み込み中...")
        try:
            with open(token_pickle_file, 'rb') as token:
                credentials = pickle.load(token)
        except Exception:
            print("  ! 既存トークンの読み込みに失敗しました。再認証します。")
            credentials = None
            
    # 認証情報がない、または無効な場合
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("  - トークンをリフレッシュ中...")
            credentials.refresh(Request())
        else:
            print("  - 新規認証プロセスを開始...")
            if not os.path.exists(client_secrets_file):
                raise FileNotFoundError(f"Client secrets file '{client_secrets_file}' not found.")
                
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            try:
                # ブラウザ完了画面で自動クローズを試みる（HTML/JS）
                credentials = flow.run_local_server(
                    port=0,
                    authorization_prompt_message="",
                    success_message="<html><head><script>setTimeout(function(){window.close();}, 500);</script></head><body><p>認証成功。ウィンドウを自動で閉じます。</p></body></html>",
                    open_browser=True,
                )
            except KeyboardInterrupt:
                # ユーザーが待機を中断した場合でも後続を安全に扱う
                print("  ! 認証待機が中断されました。再試行します。")
                credentials = None
            except Exception as e:
                print(f"  ! ローカルサーバー認証でエラー: {e}")
                traceback.print_exc()
                # フォールバック: コンソール認証（ブラウザ問題の回避）
                try:
                    credentials = flow.run_console()
                except Exception as ee:
                    print(f"  ! コンソール認証でも失敗: {ee}")
                    raise
            
        # 次回のためにトークンを保存
        try:
            with open(token_pickle_file, 'wb') as token:
                pickle.dump(credentials, token)
            print("  - トークンを保存しました。")
        except Exception as e:
            print(f"  ! トークン保存エラー: {e}")
            traceback.print_exc()
        
        # 保存されたトークンの健全性チェック。空や不正なら再生成
        if not _is_token_valid(token_pickle_file):
            print("  ! 保存されたトークンが不正/空です。再認証を実施します。")
            try:
                if os.path.exists(token_pickle_file):
                    os.remove(token_pickle_file)
                flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
                credentials = flow.run_local_server(
                    port=0,
                    authorization_prompt_message="",
                    success_message="<html><head><script>setTimeout(function(){window.close();}, 500);</script></head><body><p>認証成功。ウィンドウを自動で閉じます。</p></body></html>",
                    open_browser=True,
                )
                with open(token_pickle_file, 'wb') as token:
                    pickle.dump(credentials, token)
                print("  - トークンを再作成しました。")
            except Exception as e:
                print(f"  ! トークン再作成エラー: {e}")
                traceback.print_exc()
                raise
        
        print("認証成功")
            
    return build('youtube', 'v3', credentials=credentials)

def upload_thumbnail(youtube, video_id: str, thumbnail_path: str):
    """
    アップロードされた動画にカスタムサムネイルを設定する。
    """
    print(f"  - サムネイルをアップロード中: {thumbnail_path}")
    
    if not os.path.exists(thumbnail_path):
        print(f"    ! Error: Thumbnail file not found: {thumbnail_path}")
        return

    request = youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path)
    )
    response = request.execute()
    print("  - サムネイル設定完了。")
    return response

def upload_to_youtube(video_file: str, title: str, description: str, category_id: str = "27", privacy_status: str = "private", tags: list = None, thumbnail_path: str = None, publish_at: str = None):
    """
    動画をYouTubeにアップロードする。
    
    Args:
        video_file (str): 動画ファイルのパス
        title (str): 動画のタイトル
        description (str): 動画の説明
        category_id (str): カテゴリID (27=Education)
        privacy_status (str): 公開設定 ("private", "unlisted", "public")
        tags (list): タグのリスト
        thumbnail_path (str): サムネイル画像のパス (オプション)
        publish_at (str): 予約投稿日時 (ISO 8601形式: YYYY-MM-DDThh:mm:ss.sZ)。指定がある場合、privacy_statusは自動的にprivateになります。
    """
    print(f"YouTubeへアップロード開始: '{title}'")
    
    if not os.path.exists(video_file):
        print(f"  ! Error: Video file not found: {video_file}")
        return

    try:
        # 認証
        youtube = get_authenticated_service()
        
        # 予約投稿の場合はprivacyStatusをprivateに強制
        if publish_at:
            privacy_status = "private"

        # メタデータ設定
        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags or ["English Learning", "Podcast", "AI"],
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status,
                'selfDeclaredMadeForKids': False, 
            }
        }

        if publish_at:
            body['status']['publishAt'] = publish_at
        
        # メディアファイルの準備 (再開可能なアップロード)
        media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
        
        # アップロードリクエスト
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        # アップロード実行
        print("  - 動画ファイルをアップロード中 (これには時間がかかる場合があります)...")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"    - Uploaded {int(status.progress() * 100)}%")
                
        video_id = response.get('id')
        print(f"  - 動画アップロード完了! Video ID: {video_id}")
        print(f"  - Link: https://youtu.be/{video_id}")
        
        # サムネイルのアップロード (オプション)
        if thumbnail_path:
            try:
                upload_thumbnail(youtube, video_id, thumbnail_path)
            except Exception as e:
                print(f"  ! サムネイルアップロードエラー: {e}")
                
        return video_id

    except FileNotFoundError as e:
        print(f"  ! 認証ファイルエラー: {e}")
        print("    ヒント: Google Cloud Consoleから 'client_secrets.json' をダウンロードしてプロジェクトルートに配置してください。")
    except Exception as e:
        print(f"  ! アップロードエラー: {e}")
        return None

if __name__ == "__main__":
    # テスト実行には client_secrets.json と動画ファイルが必要
    if os.path.exists("client_secrets.json") and os.path.exists("podcast_video.mp4"):
        upload_to_youtube(
            "podcast_video.mp4", 
            "Test Upload", 
            "This is a test upload.",
            thumbnail_path=os.path.join("temp", "temp_bg_generated.png") # テスト用サムネイル
        )
    else:
        print("Skipping test run: 'client_secrets.json' or 'podcast_video.mp4' not found.")
