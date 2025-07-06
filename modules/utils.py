import streamlit as st
import json
import os
import re
from datetime import datetime
from google import genai
import pickle
import hashlib

HISTORY_DIR = "history"
SESSION_BACKUP_DIR = "session_backup"

# ディレクトリの作成
for dir_path in [HISTORY_DIR, SESSION_BACKUP_DIR]:
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def get_session_id():
    """
    現在のセッション用のユニークIDを生成します。
    
    Returns:
        str: セッションID
    """
    # セッション状態からIDを取得、なければ生成
    if 'session_id' not in st.session_state:
        # ユーザーのIPアドレスやタイムスタンプからセッションIDを生成
        import time
        session_data = f"{time.time()}_{id(st.session_state)}"
        st.session_state.session_id = hashlib.md5(session_data.encode()).hexdigest()[:12]
    
    return st.session_state.session_id

def save_session_backup(session_data):
    """
    セッション状態をバックアップファイルに保存します。
    
    Args:
        session_data (dict): 保存するセッションデータ
    """
    try:
        session_id = get_session_id()
        backup_file = os.path.join(SESSION_BACKUP_DIR, f"session_{session_id}.json")
        
        # JSONシリアライズ可能な形式に変換
        serializable_data = {}
        for key, value in session_data.items():
            try:
                json.dumps(value)  # JSON化テスト
                serializable_data[key] = value
            except (TypeError, ValueError):
                # シリアライズできない値は文字列化
                serializable_data[key] = str(value)
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        st.warning(f"セッションバックアップの保存に失敗しました: {e}")

def load_session_backup():
    """
    セッション状態をバックアップファイルから復元します。
    
    Returns:
        dict or None: 復元されたセッションデータ
    """
    try:
        session_id = get_session_id()
        backup_file = os.path.join(SESSION_BACKUP_DIR, f"session_{session_id}.json")
        
        if os.path.exists(backup_file):
            with open(backup_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
        
    except Exception as e:
        st.warning(f"セッションバックアップの読み込みに失敗しました: {e}")
        return None

def cleanup_old_session_backups(max_age_hours=24):
    """
    古いセッションバックアップファイルを削除します。
    
    Args:
        max_age_hours (int): 削除対象の経過時間（時間）
    """
    try:
        import time
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for filename in os.listdir(SESSION_BACKUP_DIR):
            if filename.startswith('session_') and filename.endswith('.json'):
                file_path = os.path.join(SESSION_BACKUP_DIR, filename)
                file_age = current_time - os.path.getmtime(file_path)
                
                if file_age > max_age_seconds:
                    os.remove(file_path)
                    
    except Exception as e:
        # エラーは無視（クリーンアップ失敗は致命的ではない）
        pass

def restore_exam_session():
    """
    試験セッションを復元します（リロード耐性）。
    
    Returns:
        bool: 復元に成功したかどうか
    """
    try:
        backup_data = load_session_backup()
        if not backup_data:
            return False
        
        # 重要なセッション変数のみ復元
        restore_keys = [
            'start_time', 'paper_data', 'essay_theme', 'exam_step',
            'search_keywords', 'time_extended', 'exam_completed',
            'exam_results', 'submitted_data'
        ]
        
        restored_count = 0
        for key in restore_keys:
            if key in backup_data and key not in st.session_state:
                st.session_state[key] = backup_data[key]
                restored_count += 1
        
        return restored_count > 0
        
    except Exception as e:
        st.warning(f"セッション復元中にエラーが発生しました: {e}")
        return False

def auto_save_session():
    """
    セッション状態を自動保存します。
    """
    try:
        # 保存対象のキーを指定
        save_keys = [
            'start_time', 'paper_data', 'essay_theme', 'exam_step',
            'search_keywords', 'time_extended', 'exam_completed',
            'exam_results', 'submitted_data', 'session_id',
            'knowledge_checker', 'interview_mode', 'single_practice_vars',
            'session_practice_vars'
        ]
        
        save_data = {}
        for key in save_keys:
            if key in st.session_state:
                # st.session_stateは直接はJSONシリアライズできないので、辞書に変換
                if hasattr(st.session_state[key], 'to_dict'):
                     save_data[key] = st.session_state[key].to_dict()
                else:
                     save_data[key] = st.session_state[key]

        # タイムスタンプを追加
        save_data['last_saved'] = datetime.now().isoformat()
        
        save_session_backup(save_data);
        
        # 古いバックアップをクリーンアップ
        cleanup_old_session_backups()
        
    except Exception as e:
        # 自動保存のエラーは表示しない（UXを損なうため）
        pass

def check_api_configuration():
    """
    Google Gemini APIの設定を確認し、適切にセットアップされているかチェックします。
    APIの疎通確認は行わず、キーの存在と形式のみをチェックします。
    
    Returns:
        tuple: (bool, str) - (設定OK?, メッセージ)
    """
    try:
        # 環境変数またはStreamlit secretsからAPIキーを確認
        api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
            
        if not api_key:
            return False, "Google Gemini APIキーが設定されていません。環境変数GOOGLE_API_KEYまたはStreamlit secretsに設定してください。"
        
        # APIキーの基本的な形式チェック
        if not api_key.strip() or len(api_key.strip()) < 30:
            return False, "APIキ���の形式が正しくありません。有効なGoogle Gemini APIキーを設定してください。"
        
        return True, "APIキーが設定されています。"
            
    except Exception as e:
        return False, f"API設定確認中にエラーが発生しました: {str(e)}"


def show_api_setup_guide():
    """
    API設定のガイドを表示します。
    """
    with st.expander("🔧 API設定ガイド", expanded=True):
        st.markdown("""
        ### Google Gemini API設定手順
        
        1. **APIキーの取得**
           - [Google AI Studio](https://aistudio.google.com/) にアクセス
           - 「Get API Key」をクリック
           - APIキーをコピー
        
        2. **環境変数での設定（推奨）**
           ```bash
           # Windows (PowerShell)
           $env:GOOGLE_API_KEY="your-api-key-here"
           
           # Windows (Command Prompt)
           set GOOGLE_API_KEY=your-api-key-here
           
           # macOS/Linux
           export GOOGLE_API_KEY="your-api-key-here"
           ```
        
        3. **Streamlit Secretsでの設定**
           - プロジェクトフォルダに `.streamlit/secrets.toml` ファイルを作成
           - 以下の内容を記述：
           ```toml
           GOOGLE_API_KEY = "your-api-key-here"
           ```
        
        4. **アプリケーションの再起動**
           - 設定後、Streamlitアプリを再起動してください
        """)

def safe_api_call(func, *args, **kwargs):
    """
    API呼び出しを安全に実行し、エラーハンドリングを行います。
    
    Args:
        func: 実行する関数
        *args: 関数の引数
        **kwargs: 関数のキーワード引数
    
    Returns:
        tuple: (bool, result) - (成功?, 結果またはエラーメッセージ)
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_msg = f"API呼び出し中にエラーが発生しました: {str(e)}"
        return False, error_msg

def save_history(data):
    """Saves a record to the history directory."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(HISTORY_DIR, f"{timestamp}.json")
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filename
    except IOError as e:
        st.error(f"履歴の保存中にエラーが発生しました: {e}")
        return None

def load_history():
    """Loads all history records."""
    if not os.path.exists(HISTORY_DIR):
        return []
    history_files = sorted([f for f in os.listdir(HISTORY_DIR) if f.endswith('.json')], reverse=True)
    history = []
    for filename in history_files:
        try:
            with open(os.path.join(HISTORY_DIR, filename), "r", encoding="utf-8") as f:
                history.append(json.load(f))
        except (json.JSONDecodeError, IOError) as e:
            st.error(f"履歴ファイル '{filename}' の読み込み中にエラーが発生しました: {e}")
    return history

def extract_scores(feedback):
    """Extracts scores from the feedback text by parsing a JSON block, with a regex fallback."""
    scores = {}
    # Attempt to find and parse the JSON block
    json_match = re.search(r'\*\*スコア:\*\*```json\s*({.*?})\s*```', feedback, re.DOTALL)
    if json_match:
        try:
            scores = json.loads(json_match.group(1))
            # Ensure all values are integers
            for key, value in scores.items():
                scores[key] = int(value)
            return scores
        except (json.JSONDecodeError, ValueError) as e:
            st.warning(f"スコアのJSONパースまたは値変換中にエラーが発生しました。旧形式で抽出を試みます: {e}")

    # Fallback to regex if JSON parsing fails or JSON block is not found
    score_pattern = re.compile(r"\*\*([a-zA-Z0-9\u4e00-\u9fa5]+)[:：]:\*\*\s*(\d+)")
    matches = score_pattern.findall(feedback)
    for key, score in matches:
        scores[key] = int(score)
    return scores

def format_history_for_download(data):
    """Formats a history record into a string for downloading."""
    s = f"# {data['type']} 練習結果\n\n"
    s += f"実施日時: {datetime.fromisoformat(data['date']).strftime('%Y/%m/%d %H:%M')}\n\n"
    
    if data['type'] == "採用試験":
        s += f"## 課題\n\n"
        s += f"### Abstract\n{data['inputs']['abstract']}\n\n"
        if data['inputs'].get('citations'):
            s += f"### 引用元\n"
            for citation in data['inputs']['citations']:
                s += f"- [{citation['title']}]({citation['uri']})\n"
            s += "\n"
        s += f"### 小論文テーマ\n{data['inputs']['essay_theme']}\n\n"
        s += f"## あなたの回答\n\n"
        s += f"### 日本語訳\n{data['inputs']['translation']}\n\n"
        s += f"### 意見\n{data['inputs']['opinion']}\n\n"
        s += f"### 小論文\n{data['inputs']['essay']}\n\n"
    elif data['type'] == "小論文対策":
        s += f"## 課題\n\n"
        s += f"### テーマ\n{data['inputs']['theme']}\n\n"
        s += f"## あなたの回答\n\n"
        s += f"### 構成メモ\n{data['inputs']['memo']}\n\n"
        s += f"### 清書\n{data['inputs']['essay']}\n\n"
    elif data['type'] == "面接対策":
        s += f"## 質問\n\n{data['inputs']['question']}\n\n"
        s += f"## あなたの回答\n\n{data['inputs']['answer']}\n\n"

    s += f"## AIによる採点結果\n\n{data['feedback']}"
    return s

def handle_submission(feedback_stream, history_data_base):
    """Handles the streaming feedback, saving, and download button logic."""
    st.subheader("採点結果")
    feedback_placeholder = st.empty()
    full_feedback = ""
    try:
        for chunk in feedback_stream:
            # hasattrでchunkにtext属性があるか確認
            if hasattr(chunk, 'text'):
                full_feedback += chunk.text
                feedback_placeholder.markdown(full_feedback + "▌")
            else:
                # text属性がない場合(エラーなど)の処理
                st.warning("レスポンスのチャンクに予期せぬ形式が含まれています。")

        feedback_placeholder.markdown(full_feedback)

        scores = extract_scores(full_feedback)
        history_data = {**history_data_base, "feedback": full_feedback, "scores": scores}
        
        filename = save_history(history_data)
        if filename:
            st.success("結果を学習履歴に保存しました。")
            download_content = format_history_for_download(history_data)
            st.download_button(
                label="結果をテキストファイルでダウンロード",
                data=download_content,
                file_name=f"result_{os.path.splitext(os.path.basename(filename))[0]}.txt",
                mime="text/plain"
            )
    except Exception as e:
        st.error(f"結果の処理中にエラーが発生しました: {e}")
        if full_feedback:
            st.info("部分的なフィードバック:")
            st.markdown(full_feedback)

def reset_session_state(keys_to_reset):
    """
    指定されたキーのリストに基づいてセッション変数をリセットする。
    """
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]