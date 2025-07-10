import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
import streamlit as st
from supabase import create_client, Client
import logging

# ロガー設定
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Supabaseを使った履歴データベース管理クラス"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Supabaseクライアントを初期化"""
        try:
            # 環境変数またはStreamlit secretsから設定を取得
            supabase_url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
            supabase_key = os.environ.get("SUPABASE_ANON_KEY") or st.secrets.get("SUPABASE_ANON_KEY")
            
            if not supabase_url or not supabase_key:
                logger.warning("Supabase credentials not found. Database features will be disabled.")
                return
            
            self.client = create_client(supabase_url, supabase_key)
            logger.info("Supabase client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """データベースが利用可能かチェック"""
        return self.client is not None
    
    def get_session_id(self) -> str:
        """セッションIDを取得（存在しない場合は新規作成）"""
        if 'db_session_id' not in st.session_state:
            st.session_state.db_session_id = str(uuid.uuid4())
            
            # セッション情報をデータベースに保存
            if self.is_available():
                try:
                    self.client.table('user_sessions').insert({
                        'session_id': st.session_state.db_session_id,
                        'created_at': datetime.now().isoformat(),
                        'last_active': datetime.now().isoformat()
                    }).execute()
                except Exception as e:
                    logger.error(f"Failed to create session record: {e}")
        
        return st.session_state.db_session_id
    
    def update_last_active(self) -> None:
        """最終アクティブ時刻を更新"""
        if not self.is_available():
            return
        
        try:
            session_id = self.get_session_id()
            self.client.table('user_sessions').update({
                'last_active': datetime.now().isoformat()
            }).eq('session_id', session_id).execute()
        except Exception as e:
            logger.error(f"Failed to update last active time: {e}")
    
    def save_practice_history(self, data: Dict[str, Any]) -> bool:
        """練習履歴をデータベースに保存"""
        logger.info(f"save_practice_history called with data keys: {list(data.keys())}")
        logger.info(f"Data type: {data.get('type')}")
        logger.info(f"Data date: {data.get('date')}")
        logger.info(f"Inputs type: {type(data.get('inputs'))}, keys: {list(data.get('inputs', {}).keys()) if isinstance(data.get('inputs'), dict) else 'Not a dict'}")
        logger.info(f"Scores type: {type(data.get('scores'))}, content: {data.get('scores')}")
        
        if not self.is_available():
            logger.warning("Database not available. Saving to session state only.")
            return self._save_to_session_state(data)
        
        try:
            session_id = self.get_session_id()
            logger.info(f"Using session_id: {session_id}")
            
            # データベース用にデータを変換
            inputs_data = data.get('inputs', {})
            scores_data = data.get('scores', {})
            
            # JSON変換を安全に実行
            try:
                inputs_json = json.dumps(inputs_data, ensure_ascii=False, default=str)
                logger.info(f"Inputs JSON: {inputs_json[:200]}...")  # 最初の200文字をログ
            except Exception as e:
                logger.error(f"Failed to serialize inputs: {e}")
                inputs_json = json.dumps({}, ensure_ascii=False)
            
            try:
                scores_json = json.dumps(scores_data, ensure_ascii=False, default=str) if scores_data else None
                if scores_json:
                    logger.info(f"Scores JSON: {scores_json}")
            except Exception as e:
                logger.error(f"Failed to serialize scores: {e}")
                scores_json = None
            
            db_data = {
                'session_id': session_id,
                'practice_type': data.get('type', ''),
                'practice_date': data.get('date'),
                'inputs': inputs_json,
                'feedback': data.get('feedback', ''),
                'scores': scores_json,
                'duration_seconds': int(data.get('duration_seconds', 0)) if data.get('duration_seconds') is not None else None,
                'duration_display': data.get('duration_display', '')
            }
            
            logger.info(f"Prepared db_data: {db_data}")
            logger.info(f"Attempting to insert into practice_history table...")
            
            result = self.client.table('practice_history').insert(db_data).execute()
            
            logger.info(f"Insert result status: {hasattr(result, 'data')}")
            logger.info(f"Insert result data length: {len(result.data) if result.data else 0}")
            
            if result.data:
                inserted_record = result.data[0]
                logger.info(f"Successfully saved practice history to database: record ID {inserted_record.get('id')}")
                logger.info(f"Inserted inputs length: {len(inserted_record.get('inputs', ''))}")
                logger.info(f"Inserted inputs preview: {inserted_record.get('inputs', '')[:100]}...")
                self.update_last_active()
                return True
            else:
                logger.error("Failed to save practice history to database - no data returned")
                logger.error(f"Supabase error: {getattr(result, 'error', 'No error info')}")
                return self._save_to_session_state(data)
                
        except Exception as e:
            logger.error(f"Error saving practice history to database: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.warning("Falling back to session state storage due to database error")
            return self._save_to_session_state(data)
    
    def _save_to_session_state(self, data: Dict[str, Any]) -> bool:
        """フォールバック: セッション状態に保存"""
        logger.info("Saving to session state as fallback")
        
        if 'offline_history' not in st.session_state:
            st.session_state.offline_history = []
        
        st.session_state.offline_history.insert(0, data)
        
        # 最大100件まで保持
        if len(st.session_state.offline_history) > 100:
            st.session_state.offline_history = st.session_state.offline_history[:100]
        
        # フォールバック保存が行われたことを記録
        if 'database_fallback_occurred' not in st.session_state:
            st.session_state.database_fallback_occurred = True
        
        logger.info(f"Saved to session state. Total offline records: {len(st.session_state.offline_history)}")
        return True
    
    def load_practice_history(self, practice_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """練習履歴を読み込み"""
        if not self.is_available():
            logger.warning("Database not available. Loading from session state only.")
            return self._load_from_session_state(practice_type, limit)
        
        try:
            session_id = self.get_session_id()
            
            # クエリを構築
            query = self.client.table('practice_history').select('*').eq('session_id', session_id)
            
            if practice_type:
                query = query.eq('practice_type', practice_type)
            
            result = query.order('practice_date', desc=True).limit(limit).execute()
            
            if result.data:
                # データベース形式から元の形式に変換
                history = []
                for item in result.data:
                    try:
                        # JSON解析を安全に実行
                        inputs = {}
                        if item['inputs']:
                            try:
                                inputs = json.loads(item['inputs'])
                                logger.debug(f"Loaded inputs keys: {list(inputs.keys()) if isinstance(inputs, dict) else 'Not a dict'}")
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse inputs JSON: {e}, content: {item['inputs'][:100]}...")
                        
                        scores = {}
                        if item['scores']:
                            try:
                                scores = json.loads(item['scores'])
                                logger.debug(f"Loaded scores: {scores}")
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse scores JSON: {e}, content: {item['scores']}")
                        
                        converted_item = {
                            'type': item['practice_type'],
                            'date': item['practice_date'],
                            'inputs': inputs,
                            'feedback': item['feedback'],
                            'scores': scores,
                            'duration_seconds': item['duration_seconds'],
                            'duration_display': item['duration_display']
                        }
                        history.append(converted_item)
                        
                    except Exception as e:
                        logger.error(f"Failed to convert database record: {e}")
                        continue
                
                logger.info(f"Successfully loaded {len(history)} practice history records from database")
                return history
            else:
                return self._load_from_session_state(practice_type, limit)
                
        except Exception as e:
            logger.error(f"Error loading practice history from database: {e}")
            return self._load_from_session_state(practice_type, limit)
    
    def _load_from_session_state(self, practice_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """フォールバック: セッション状態から読み込み"""
        if 'offline_history' not in st.session_state:
            return []
        
        history = st.session_state.offline_history
        
        if practice_type:
            history = [item for item in history if item.get('type') == practice_type]
        
        return history[:limit]
    
    def get_recent_themes(self, practice_type: str, limit: int = 5) -> List[str]:
        """最近のテーマを取得"""
        history = self.load_practice_history(practice_type, limit * 2)  # 余裕をもって取得
        
        recent_themes = []
        for item in history:
            theme = item.get('inputs', {}).get('theme')
            if theme and theme not in recent_themes:
                recent_themes.append(theme)
                if len(recent_themes) >= limit:
                    break
        
        return recent_themes
    
    def get_theme_history(self, practice_type: str, theme: str) -> List[Dict[str, Any]]:
        """指定されたテーマの履歴を取得"""
        history = self.load_practice_history(practice_type, 200)  # テーマ検索のため多めに取得
        
        theme_history = []
        for item in history:
            if item.get('inputs', {}).get('theme') == theme and item.get('scores'):
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
    
    def is_theme_recently_used(self, practice_type: str, theme: str, recent_limit: int = 3) -> bool:
        """テーマが最近使用されたかチェック"""
        recent_themes = self.get_recent_themes(practice_type, recent_limit)
        return theme in recent_themes
    
    def export_history(self, practice_type: Optional[str] = None) -> str:
        """履歴データをJSON形式でエクスポート"""
        history = self.load_practice_history(practice_type)
        return json.dumps(history, ensure_ascii=False, indent=2)
    
    def get_database_status(self) -> Dict[str, Any]:
        """データベース接続状況を取得"""
        status = {
            'available': self.is_available(),
            'session_id': self.get_session_id() if self.is_available() else None,
            'offline_records': len(st.session_state.get('offline_history', []))
        }
        
        if self.is_available():
            try:
                session_id = self.get_session_id()
                result = self.client.table('practice_history').select('id').eq('session_id', session_id).execute()
                status['database_records'] = len(result.data) if result.data else 0
            except Exception as e:
                logger.error(f"Error getting database record count: {e}")
                status['database_records'] = 'Unknown'
        
        return status

# グローバルインスタンス
db_manager = DatabaseManager() 