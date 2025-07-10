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
            return False, "APIキーの形式が正しくありません。有効なGoogle Gemini APIキーを設定してください。"
        
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
    """Saves a record to the database or local directory as fallback."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"save_history called with data type: {data.get('type', 'Unknown')}")
    logger.info(f"save_history data keys: {list(data.keys())}")
    
    try:
        # 新しいデータベースマネージャーを使用
        from modules.database import db_manager
        logger.info("Calling db_manager.save_practice_history...")
        success = db_manager.save_practice_history(data)
        
        logger.info(f"db_manager.save_practice_history returned: {success}")
        
        if success:
            logger.info("History saved successfully via database")
            return True
        else:
            # フォールバック: ローカルファイル保存
            logger.warning("Database save failed, falling back to local file")
            return _save_history_local(data)
            
    except ImportError as e:
        # データベースモジュールが利用できない場合はローカル保存
        logger.error(f"ImportError: {e}, falling back to local save")
        return _save_history_local(data)
    except Exception as e:
        logger.error(f"Unexpected error in save_history: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return _save_history_local(data)

def _save_history_local(data):
    """Saves a record to the local history directory (fallback)."""
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
    """Loads all history records from database or local directory as fallback."""
    try:
        # 新しいデータベースマネージャーを使用
        from modules.database import db_manager
        return db_manager.load_practice_history()
        
    except ImportError:
        # データベースモジュールが利用できない場合はローカルファイル読み込み
        return _load_history_local()

def _load_history_local():
    """Loads all history records from local directory (fallback)."""
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

def answer_followup_question_stream(original_content, original_results, question, question_type="一般"):
    """
    元の結果に基づいて追加質問に回答するストリーミング関数
    
    Args:
        original_content (dict): 元の提出内容（課題、回答など）
        original_results (str): 元のAI評価結果
        question (str): ユーザーからの追加質問
        question_type (str): 質問の種類（"小論文"、"面接"、"一般"）
    
    Yields:
        応答のストリーミングチャンク
    """
    try:
        client = genai.Client()
        
        # 質問種類に応じたプロンプト生成
        if question_type == "小論文":
            context_prompt = f"""
# 前提情報
あなたは先ほど以下の小論文を採点しました：

【テーマ】
{original_content.get('theme', '')}

【構成メモ】
{original_content.get('memo', '')}

【清書】
{original_content.get('essay', '')}

【あなたの採点結果】
{original_results}

# 指示
上記の採点結果について、学習者から以下の質問がありました。
採点結果の内容を踏まえ、具体的で建設的なアドバイスを提供してください。
回答は丁寧で分かりやすく、学習者の理解を深めるものにしてください。

【学習者からの質問】
{question}
"""
        elif question_type == "面接":
            context_prompt = f"""
# 前提情報
あなたは先ほど以下の面接練習を評価しました：

【面接質問】
{original_content.get('question', '')}

【回答】
{original_content.get('answer', '')}

【あなたの評価結果】
{original_results}

# 指示
上記の評価結果について、学習者から以下の質問がありました。
評価結果の内容を踏まえ、面接スキル向上に繋がる具体的で実践的なアドバイスを提供してください。
回答は丁寧で分かりやすく、学習者の成長を支援するものにしてください。

【学習者からの質問】
{question}
"""
        else:
            context_prompt = f"""
# 前提情報
あなたは学習者の課題について以下の評価を行いました：

【元の内容】
{json.dumps(original_content, ensure_ascii=False, indent=2)}

【あなたの評価結果】
{original_results}

# 指示
上記の評価結果について、学習者から以下の質問がありました。
評価結果の内容を踏まえ、具体的で建設的なアドバイスを提供してください。

【学習者からの質問】
{question}
"""
        
        # ストリーミング応答を生成
        response_stream = client.models.generate_content_stream(
            model='gemini-2.5-flash',
            contents=context_prompt
        )
        
        for chunk in response_stream:
            if hasattr(chunk, 'text') and chunk.text:
                yield chunk
            
    except Exception as e:
        # エラーが発生した場合のダミーチャンク
        error_msg = f"申し訳ございません。回答生成中にエラーが発生しました: {str(e)}"
        yield type('ErrorChunk', (), {'text': error_msg})()

def render_followup_chat(original_content, original_results, question_type="一般", session_key="followup_chat"):
    """
    追加質問用のチャットUIを描画する
    
    Args:
        original_content (dict): 元の提出内容
        original_results (str): 元のAI評価結果
        question_type (str): 質問の種類
        session_key (str): セッション状態のキー
    """
    # セッション状態の初期化
    chat_key = f"{session_key}_history"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []
    
    st.markdown("---")
    st.markdown("### 💬 結果について質問する")
    st.markdown("上記の評価結果について、詳しく知りたいことがあれば気軽に質問してください。")
    
    # チャット履歴の表示
    chat_container = st.container()
    with chat_container:
        for i, msg in enumerate(st.session_state[chat_key]):
            if msg["role"] == "user":
                st.chat_message("user").markdown(msg["content"])
            else:
                st.chat_message("assistant").markdown(msg["content"])
    
    # 質問入力
    if prompt := st.chat_input("質問を入力してください（例：この部分はどう改善すれば良いですか？）"):
        # ユーザーの質問を履歴に追加
        st.session_state[chat_key].append({"role": "user", "content": prompt})
        
        # ユーザーの質問を表示
        with chat_container:
            st.chat_message("user").markdown(prompt)
        
        # AIの回答を生成・表示
        with chat_container:
            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                full_response = ""
                
                # ストリーミング応答
                try:
                    stream = answer_followup_question_stream(
                        original_content, 
                        original_results, 
                        prompt, 
                        question_type
                    )
                    
                    for chunk in stream:
                        if hasattr(chunk, 'text') and chunk.text:
                            full_response += chunk.text
                            response_placeholder.markdown(full_response + "▌")
                    
                    response_placeholder.markdown(full_response)
                    
                    # AIの回答を履歴に追加
                    st.session_state[chat_key].append({"role": "assistant", "content": full_response})
                    
                except Exception as e:
                    error_msg = f"申し訳ございません。回答生成中にエラーが発生しました: {str(e)}"
                    response_placeholder.error(error_msg)
                    st.session_state[chat_key].append({"role": "assistant", "content": error_msg})
        
        # 表示を更新
        st.rerun()

def clear_followup_chat(session_key="followup_chat"):
    """
    追加質問のチャット履歴をクリアする
    
    Args:
        session_key (str): セッション状態のキー
    """
    chat_key = f"{session_key}_history"
    if chat_key in st.session_state:
        st.session_state[chat_key] = []

def get_recent_themes(practice_type: str, limit: int = 5) -> list:
    """
    指定された練習タイプの最近のテーマを取得します。
    
    Args:
        practice_type (str): 練習タイプ（"自由記述"など）
        limit (int): 取得する最大件数
    
    Returns:
        list: 最近使用されたテーマのリスト
    """
    try:
        # 新しいデータベースマネージャーを使用
        from modules.database import db_manager
        return db_manager.get_recent_themes(practice_type, limit)
        
    except ImportError:
        # フォールバック: 従来の方法
        return _get_recent_themes_local(practice_type, limit)

def _get_recent_themes_local(practice_type: str, limit: int = 5) -> list:
    """フォールバック: ローカルファイルから最近のテーマを取得"""
    try:
        history = _load_history_local()
        recent_themes = []
        
        for item in history:
            if item.get('type') == practice_type:
                theme = item.get('inputs', {}).get('theme')
                if theme and theme not in recent_themes:
                    recent_themes.append(theme)
                    if len(recent_themes) >= limit:
                        break
        
        return recent_themes
    except Exception as e:
        st.warning(f"最近のテーマ取得中にエラーが発生しました: {e}")
        return []

def get_theme_history(practice_type: str, theme: str) -> list:
    """
    指定されたテーマの過去の成績履歴を取得します。
    
    Args:
        practice_type (str): 練習タイプ（"自由記述"など）
        theme (str): 検索するテーマ
    
    Returns:
        list: 過去の成績データのリスト（日付の新しい順）
    """
    try:
        # 新しいデータベースマネージャーを使用
        from modules.database import db_manager
        return db_manager.get_theme_history(practice_type, theme)
        
    except ImportError:
        # フォールバック: 従来の方法
        return _get_theme_history_local(practice_type, theme)

def _get_theme_history_local(practice_type: str, theme: str) -> list:
    """フォールバック: ローカルファイルからテーマ履歴を取得"""
    try:
        history = _load_history_local()
        theme_history = []
        
        for item in history:
            if (item.get('type') == practice_type and 
                item.get('inputs', {}).get('theme') == theme):
                
                # スコアが存在する場合のみ追加
                if item.get('scores'):
                    theme_data = {
                        'date': item.get('date'),
                        'scores': item.get('scores'),
                        'feedback': item.get('feedback', ''),
                        'answer': item.get('inputs', {}).get('answer', '')
                    }
                    theme_history.append(theme_data)
        
        # 日付順でソート（新しい順）
        theme_history.sort(key=lambda x: x['date'], reverse=True)
        return theme_history
        
    except Exception as e:
        st.warning(f"テーマ履歴取得中にエラーが発生しました: {e}")
        return []

def is_theme_recently_used(practice_type: str, theme: str, recent_limit: int = 3) -> bool:
    """
    指定されたテーマが最近使用されたかチェックします。
    
    Args:
        practice_type (str): 練習タイプ
        theme (str): チェックするテーマ
        recent_limit (int): 最近の件数
    
    Returns:
        bool: 最近使用されている場合True
    """
    try:
        # 新しいデータベースマネージャーを使用
        from modules.database import db_manager
        return db_manager.is_theme_recently_used(practice_type, theme, recent_limit)
        
    except ImportError:
        # フォールバック: 従来の方法
        recent_themes = _get_recent_themes_local(practice_type, recent_limit)
        return theme in recent_themes

def calculate_progress_stats(theme_history: list) -> dict:
    """
    テーマの履歴から進歩統計を計算します。
    
    Args:
        theme_history (list): テーマの履歴データ
    
    Returns:
        dict: 進歩統計の辞書
    """
    if len(theme_history) < 2:
        return {"has_progress": False}
    
    try:
        # 最新と最古の結果を比較
        latest = theme_history[0]
        oldest = theme_history[-1]
        
        # 平均スコアの計算
        latest_avg = sum(latest['scores'].values()) / len(latest['scores']) if latest['scores'] else 0
        oldest_avg = sum(oldest['scores'].values()) / len(oldest['scores']) if oldest['scores'] else 0
        
        # 改善度の計算
        improvement = latest_avg - oldest_avg
        improvement_percentage = (improvement / oldest_avg * 100) if oldest_avg > 0 else 0
        
        # カテゴリ別の改善
        category_improvements = {}
        if latest['scores'] and oldest['scores']:
            for category in set(latest['scores'].keys()) & set(oldest['scores'].keys()):
                category_improvements[category] = latest['scores'][category] - oldest['scores'][category]
        
        return {
            "has_progress": True,
            "attempts": len(theme_history),
            "latest_avg": latest_avg,
            "oldest_avg": oldest_avg,
            "improvement": improvement,
            "improvement_percentage": improvement_percentage,
            "category_improvements": category_improvements,
            "latest_date": latest['date'],
            "oldest_date": oldest['date']
        }
        
    except Exception as e:
        st.warning(f"進歩統計計算中にエラーが発生しました: {e}")
        return {"has_progress": False}

def render_progress_comparison(theme: str, theme_history: list):
    """
    テーマの進歩比較を表示します。
    
    Args:
        theme (str): テーマ名
        theme_history (list): テーマの履歴データ
    """
    if not theme_history:
        return
    
    progress_stats = calculate_progress_stats(theme_history)
    
    if not progress_stats.get("has_progress"):
        if len(theme_history) == 1:
            st.info(f"📊 「{theme}」は初回の挑戦です。次回以降、進歩を確認できます。")
        return
    
    st.markdown("---")
    st.markdown("### 📈 進歩の分析")
    
    attempts = progress_stats["attempts"]
    improvement = progress_stats["improvement"]
    improvement_percentage = progress_stats["improvement_percentage"]
    
    # 進歩の概要
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="挑戦回数",
            value=f"{attempts}回"
        )
    
    with col2:
        st.metric(
            label="平均スコア改善",
            value=f"{improvement:+.1f}",
            delta=f"{improvement_percentage:+.1f}%"
        )
    
    with col3:
        if improvement > 0:
            st.success("📈 成長しています！")
        elif improvement < 0:
            st.warning("📉 前回より下がりました")
        else:
            st.info("📊 同じレベルです")
    
    # カテゴリ別の改善
    if progress_stats.get("category_improvements"):
        st.markdown("#### カテゴリ別の改善度")
        improvements = progress_stats["category_improvements"]
        
        for category, change in improvements.items():
            color = "normal"
            if change > 0:
                color = "normal"
                icon = "📈"
                delta_color = "normal"
            elif change < 0:
                color = "normal"
                icon = "📉"
                delta_color = "inverse"
            else:
                color = "normal"
                icon = "📊"
                delta_color = "off"
            
            st.metric(
                label=f"{icon} {category}",
                value=theme_history[0]['scores'].get(category, 0),
                delta=change,
                delta_color=delta_color
            )
    
    # 過去の成績一覧
    with st.expander("📋 過去の成績を確認"):
        for i, record in enumerate(theme_history):
            date_str = datetime.fromisoformat(record['date']).strftime('%Y/%m/%d %H:%M')
            st.markdown(f"**{i+1}回目** ({date_str})")
            
            if record['scores']:
                score_cols = st.columns(len(record['scores']))
                for j, (category, score) in enumerate(record['scores'].items()):
                    with score_cols[j]:
                        st.metric(category, f"{score}点")
            else:
                st.text("スコアなし")
            
            if i < len(theme_history) - 1:  # 最後の要素でなければ区切り線
                st.markdown("---")

def save_recent_theme(theme: str):
    """
    最近使用したテーマをセッション状態に保存します。
    
    Args:
        theme (str): 保存するテーマ
    """
    if 'recent_knowledge_themes' not in st.session_state:
        st.session_state.recent_knowledge_themes = []
    
    # 重複を避けて先頭に追加
    if theme in st.session_state.recent_knowledge_themes:
        st.session_state.recent_knowledge_themes.remove(theme)
    
    st.session_state.recent_knowledge_themes.insert(0, theme)
    
    # 最大5件まで保持
    if len(st.session_state.recent_knowledge_themes) > 5:
        st.session_state.recent_knowledge_themes = st.session_state.recent_knowledge_themes[:5]