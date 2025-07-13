"""
新しいデータベース設計に対応したデータベース管理システム v3
ユーザー中心の管理、演習タイプ別の履歴管理、LLM添削結果の確実な保存
"""

import os
import json
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple, Union
import streamlit as st
from supabase import create_client, Client
import logging
from dataclasses import dataclass
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ロガー設定
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class SessionStatus(Enum):
    """演習セッションの状態"""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ERROR = "error"

class FeedbackType(Enum):
    """フィードバックのタイプ"""
    GENERAL = "general"
    IMPROVEMENT = "improvement"
    STRONG_POINT = "strong_point"
    ERROR = "error"
    CORRECTION = "correction"

@dataclass
class ExerciseType:
    """演習タイプのデータクラス"""
    exercise_type_id: int
    category_id: int
    type_name: str
    display_name: str
    description: str
    input_schema: Dict[str, Any]
    score_schema: Dict[str, Any]
    difficulty_level: int = 1
    estimated_duration_minutes: int = 30
    is_active: bool = True

@dataclass
class ExerciseSession:
    """演習セッションのデータクラス"""
    session_id: str
    user_id: str
    exercise_type_id: int
    theme: Optional[str] = None
    start_time: datetime = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    status: SessionStatus = SessionStatus.IN_PROGRESS
    completion_percentage: float = 0.0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.start_time is None:
            self.start_time = datetime.now()
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ExerciseInput:
    """演習入力のデータクラス"""
    input_id: str
    session_id: str
    input_type: str
    content: str
    word_count: int = 0
    input_order: int = 1
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.word_count == 0 and self.content:
            self.word_count = len(self.content)
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ExerciseScore:
    """演習スコアのデータクラス"""
    score_id: str
    session_id: str
    score_category: str
    score_value: float
    max_score: float = 10.0
    weight: float = 1.0
    feedback: Optional[str] = None
    ai_model: Optional[str] = None
    tokens_used: Optional[int] = None

    @property
    def score_percentage(self) -> float:
        """スコアの百分率を計算"""
        return (self.score_value / self.max_score) * 100 if self.max_score > 0 else 0

@dataclass
class ExerciseFeedback:
    """演習フィードバックのデータクラス"""
    feedback_id: str
    session_id: str
    feedback_content: str
    feedback_type: FeedbackType = FeedbackType.GENERAL
    ai_model: Optional[str] = None
    tokens_used: Optional[int] = None

class UserManagerV3:
    """ユーザー管理クラス v3"""
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    def create_or_get_user(self, identifier: str, identifier_type: str = "browser_fingerprint") -> str:
        """ユーザーを作成または取得"""
        try:
            # ブラウザフィンガープリントの場合は匿名ユーザーを作成しない
            if identifier_type == "browser_fingerprint":
                # 一時的なセッションIDを返す
                temp_user_id = f"temp_{identifier}"
                logger.info(f"Using temporary session: {temp_user_id}")
                return temp_user_id
            
            # 既存ユーザーを検索（emailの場合のみ）
            result = self.client.table('users').select('user_id').eq('email', identifier).execute()
            
            if result.data:
                user_id = result.data[0]['user_id']
                # 最終アクティブ時刻を更新
                self.update_last_active(user_id)
                return user_id
            
            # 新規ユーザー作成（emailの場合のみ）
            user_data = {
                'email': identifier,
                'display_name': f'User {identifier[:8]}',
                'preferences': {},
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'is_active': True
            }
            
            result = self.client.table('users').insert(user_data).execute()
            
            if result.data:
                user_id = result.data[0]['user_id']
                logger.info(f"Created new user: {user_id}")
                return user_id
            else:
                raise Exception("Failed to create user")
                
        except Exception as e:
            logger.error(f"Error in create_or_get_user: {e}")
            raise
    
    def update_last_active(self, user_id: str) -> None:
        """最終アクティブ時刻を更新"""
        try:
            # 一時的なユーザーIDの場合は更新しない
            if user_id.startswith('temp_'):
                logger.debug(f"Skipping last_active update for temporary user: {user_id}")
                return
                
            self.client.table('users').update({
                'last_active': datetime.now().isoformat()
            }).eq('user_id', user_id).execute()
        except Exception as e:
            logger.warning(f"Failed to update last active for user {user_id}: {e}")
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """ユーザー設定を取得"""
        try:
            result = self.client.table('users').select('preferences').eq('user_id', user_id).execute()
            if result.data:
                return result.data[0].get('preferences', {})
            return {}
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}")
            return {}
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """ユーザー設定を更新"""
        try:
            result = self.client.table('users').update({
                'preferences': preferences
            }).eq('user_id', user_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error updating user preferences: {e}")
            return False

class SessionManagerV3:
    """演習セッション管理クラス v3"""
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    def start_exercise_session(self, user_id: str, exercise_type_id: int, theme: str = None) -> str:
        """演習セッションを開始"""
        try:
            # 既存のアクティブセッションを強制的にクリーンアップ
            self._cleanup_user_sessions(user_id)
            
            # 現在時刻をUTCで取得
            from datetime import timezone
            current_time = datetime.now(timezone.utc)
            
            session_data = {
                'user_id': user_id,
                'exercise_type_id': exercise_type_id,
                'theme': theme,
                'start_time': current_time.isoformat(),
                'status': SessionStatus.IN_PROGRESS.value,
                'completion_percentage': 0.0,
                'metadata': {}
            }
            
            result = self.client.table('exercise_sessions').insert(session_data).execute()
            
            if result.data:
                session_id = result.data[0]['session_id']
                logger.info(f"Started exercise session: {session_id}")
                return session_id
            else:
                raise Exception("Failed to create exercise session")
                
        except Exception as e:
            logger.error(f"Error starting exercise session: {e}")
            raise
    
    def _cleanup_user_sessions(self, user_id: str) -> bool:
        """ユーザーのアクティブセッションをクリーンアップ"""
        try:
            # アクティブセッションをabandonedに変更
            result = self.client.table('exercise_sessions').update({
                'status': SessionStatus.ABANDONED.value,
                'end_time': datetime.now().isoformat()
            }).eq('user_id', user_id).eq('status', SessionStatus.IN_PROGRESS.value).execute()
            
            if result.data:
                logger.info(f"Cleaned up {len(result.data)} active sessions for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up user sessions: {e}")
            return False
    
    def complete_exercise_session(self, session_id: str, completion_percentage: float = 100.0) -> bool:
        """演習セッションを完了"""
        try:
            # セッション時間を計算
            session_result = self.client.table('exercise_sessions').select(
                'start_time'
            ).eq('session_id', session_id).execute()
            
            if not session_result.data:
                logger.error(f"Session not found: {session_id}")
                return False
            
            start_time = datetime.fromisoformat(session_result.data[0]['start_time'].replace('Z', '+00:00'))
            end_time = datetime.now().replace(tzinfo=start_time.tzinfo)
            duration_seconds = int((end_time - start_time).total_seconds())
            
            # セッションを完了
            result = self.client.table('exercise_sessions').update({
                'status': SessionStatus.COMPLETED.value,
                'end_time': end_time.isoformat(),
                'duration_seconds': duration_seconds,
                'completion_percentage': completion_percentage
            }).eq('session_id', session_id).execute()
            
            if result.data:
                logger.info(f"Completed exercise session: {session_id}")
                return True
            else:
                logger.error(f"Failed to complete session: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error completing exercise session: {e}")
            return False
    
    def abandon_session(self, session_id: str) -> bool:
        """セッションを中断"""
        try:
            result = self.client.table('exercise_sessions').update({
                'status': SessionStatus.ABANDONED.value,
                'end_time': datetime.now().isoformat()
            }).eq('session_id', session_id).execute()
            
            if result.data:
                logger.info(f"Abandoned exercise session: {session_id}")
                return True
            else:
                logger.error(f"Failed to abandon session: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error abandoning session: {e}")
            return False
    
    def save_exercise_inputs(self, session_id: str, inputs: List[ExerciseInput]) -> bool:
        """演習入力を保存"""
        try:
            input_data = []
            for i, input_item in enumerate(inputs, 1):
                input_data.append({
                    'session_id': session_id,
                    'input_type': input_item.input_type,
                    'content': input_item.content,
                    'word_count': input_item.word_count,
                    'input_order': i,
                    'metadata': input_item.metadata
                })
            
            result = self.client.table('exercise_inputs').insert(input_data).execute()
            
            if result.data:
                logger.info(f"Saved {len(result.data)} exercise inputs for session: {session_id}")
                return True
            else:
                logger.error(f"Failed to save exercise inputs for session: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving exercise inputs: {e}")
            return False
    
    def save_exercise_scores(self, session_id: str, scores: List[ExerciseScore]) -> bool:
        """演習スコアを保存"""
        try:
            score_data = []
            for score in scores:
                score_data.append({
                    'session_id': session_id,
                    'score_category': score.score_category,
                    'score_value': score.score_value,
                    'max_score': score.max_score,
                    'weight': score.weight,
                    'feedback': score.feedback,
                    'ai_model': score.ai_model,
                    'tokens_used': score.tokens_used
                })
            
            result = self.client.table('exercise_scores').insert(score_data).execute()
            
            if result.data:
                logger.info(f"Saved {len(result.data)} exercise scores for session: {session_id}")
                return True
            else:
                logger.error(f"Failed to save exercise scores for session: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving exercise scores: {e}")
            return False
    
    def save_exercise_feedback(self, session_id: str, feedback_content: str, 
                             feedback_type: FeedbackType = FeedbackType.GENERAL,
                             ai_model: str = None, tokens_used: int = None) -> bool:
        """演習フィードバックを保存"""
        try:
            feedback_data = {
                'session_id': session_id,
                'feedback_content': feedback_content,
                'feedback_type': feedback_type.value,
                'ai_model': ai_model,
                'tokens_used': tokens_used
            }
            
            result = self.client.table('exercise_feedback').insert(feedback_data).execute()
            
            if result.data:
                logger.info(f"Saved exercise feedback for session: {session_id}")
                return True
            else:
                logger.error(f"Failed to save exercise feedback for session: {session_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error saving exercise feedback: {e}")
            return False

class HistoryManagerV3:
    """履歴管理クラス v3"""
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    def get_user_exercise_history(self, user_id: str, exercise_type_id: int = None, 
                                limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """ユーザーの演習履歴を取得"""
        try:
            # 一時的なユーザーID（temp_プレフィックス）の場合は履歴を返さない
            if user_id.startswith('temp_'):
                logger.debug(f"Skipping history retrieval for temporary user: {user_id}")
                return []
            
            # 基本クエリ
            query = self.client.table('exercise_sessions').select(
                'session_id, exercise_type_id, theme, start_time, end_time, duration_seconds, status, completion_percentage'
            ).eq('user_id', user_id).order('created_at', desc=True).limit(limit).offset(offset)
            
            # 演習タイプでフィルタ
            if exercise_type_id:
                query = query.eq('exercise_type_id', exercise_type_id)
            
            result = query.execute()
            
            if not result.data:
                return []
            
            # セッションIDを取得
            session_ids = [session['session_id'] for session in result.data]
            
            # 関連データを一括取得
            inputs_map = self._get_session_inputs_batch(session_ids)
            scores_map = self._get_session_scores_batch(session_ids)
            feedback_map = self._get_session_feedback_batch(session_ids)
            
            # 結果を組み合わせ
            history = []
            for session in result.data:
                session_id = session['session_id']
                history_item = {
                    **session,
                    'inputs': inputs_map.get(session_id, []),
                    'scores': scores_map.get(session_id, []),
                    'feedback': feedback_map.get(session_id, [])
                }
                history.append(history_item)
            
            logger.info(f"Retrieved {len(history)} exercise history items for user {user_id}")
            return history
            
        except Exception as e:
            logger.error(f"Error getting user exercise history: {e}")
            return []
    
    def _get_session_inputs_batch(self, session_ids: List[str]) -> Dict[str, List[Dict]]:
        """セッション入力データを一括取得"""
        try:
            if not session_ids:
                return {}
            
            result = self.client.table('exercise_inputs').select(
                'session_id, input_type, content, word_count, input_order, metadata'
            ).in_('session_id', session_ids).order('input_order').execute()
            
            inputs_map = {}
            for input_item in result.data:
                session_id = input_item['session_id']
                if session_id not in inputs_map:
                    inputs_map[session_id] = []
                inputs_map[session_id].append(input_item)
            
            return inputs_map
            
        except Exception as e:
            logger.error(f"Error getting session inputs batch: {e}")
            return {}
    
    def _get_session_scores_batch(self, session_ids: List[str]) -> Dict[str, List[Dict]]:
        """セッションスコアデータを一括取得"""
        try:
            if not session_ids:
                return {}
            
            result = self.client.table('exercise_scores').select(
                'session_id, score_category, score_value, max_score, weight, feedback, ai_model, tokens_used'
            ).in_('session_id', session_ids).execute()
            
            scores_map = {}
            for score_item in result.data:
                session_id = score_item['session_id']
                if session_id not in scores_map:
                    scores_map[session_id] = []
                scores_map[session_id].append(score_item)
            
            return scores_map
            
        except Exception as e:
            logger.error(f"Error getting session scores batch: {e}")
            return {}
    
    def _get_session_feedback_batch(self, session_ids: List[str]) -> Dict[str, List[Dict]]:
        """セッションフィードバックデータを一括取得"""
        try:
            if not session_ids:
                return {}
            
            result = self.client.table('exercise_feedback').select(
                'session_id, feedback_content, feedback_type, ai_model, tokens_used, created_at'
            ).in_('session_id', session_ids).order('created_at').execute()
            
            feedback_map = {}
            for feedback_item in result.data:
                session_id = feedback_item['session_id']
                if session_id not in feedback_map:
                    feedback_map[session_id] = []
                feedback_map[session_id].append(feedback_item)
            
            return feedback_map
            
        except Exception as e:
            logger.error(f"Error getting session feedback batch: {e}")
            return {}
    
    def get_keyword_generation_history(self, user_id: str, exercise_type_id: int = None, 
                                     limit: int = 50) -> List[Dict[str, Any]]:
        """キーワード生成履歴を取得"""
        try:
            # fallback_userの場合は履歴を返さない
            if user_id == "fallback_user":
                logger.debug(f"Skipping keyword history retrieval for fallback user: {user_id}")
                return []
            
            # 一時的なユーザーID（temp_プレフィックス）の場合は履歴を返さない
            if user_id.startswith('temp_'):
                logger.debug(f"Skipping keyword history retrieval for temporary user: {user_id}")
                return []
            
            query = self.client.table('category_keyword_history').select(
                'keyword_id, category_id, session_id, input_text, generated_keywords, category, rationale, ai_model, tokens_used, created_at'
            ).eq('user_id', user_id).order('created_at', desc=True).limit(limit)
            
            if exercise_type_id:
                # exercise_type_idからcategory_idを取得
                exercise_type_result = self.client.table('exercise_types').select('category_id').eq('exercise_type_id', exercise_type_id).execute()
                if exercise_type_result.data:
                    category_id = exercise_type_result.data[0]['category_id']
                    query = query.eq('category_id', category_id)
            
            result = query.execute()
            
            logger.info(f"Retrieved {len(result.data)} keyword generation history items for user {user_id}")
            return result.data
            
        except Exception as e:
            logger.error(f"Error getting keyword generation history: {e}")
            return []
    
    def get_paper_search_history(self, user_id: str, exercise_type_id: int = None, 
                               limit: int = 50) -> List[Dict[str, Any]]:
        """論文検索履歴を取得"""
        try:
            # fallback_userの場合は履歴を返さない
            if user_id == "fallback_user":
                logger.debug(f"Skipping paper search history retrieval for fallback user: {user_id}")
                return []
            
            # 一時的なユーザーID（temp_プレフィックス）の場合は履歴を返さない
            if user_id.startswith('temp_'):
                logger.debug(f"Skipping paper search history retrieval for temporary user: {user_id}")
                return []
            
            query = self.client.table('category_paper_search_history').select(
                'search_id, category_id, session_id, search_query, search_keywords, search_results, selected_papers, purpose, ai_model, tokens_used, created_at'
            ).eq('user_id', user_id).order('created_at', desc=True).limit(limit)
            
            if exercise_type_id:
                # exercise_type_idからcategory_idを取得
                exercise_type_result = self.client.table('exercise_types').select('category_id').eq('exercise_type_id', exercise_type_id).execute()
                if exercise_type_result.data:
                    category_id = exercise_type_result.data[0]['category_id']
                    query = query.eq('category_id', category_id)
            
            result = query.execute()
            
            logger.info(f"Retrieved {len(result.data)} paper search history items for user {user_id}")
            return result.data
            
        except Exception as e:
            logger.error(f"Error getting paper search history: {e}")
            return []

class DatabaseManagerV3:
    """データベース管理クラス v3"""
    
    def __init__(self):
        self.client = None
        self.user_manager = None
        self.session_manager = None
        self.history_manager = None
        self._exercise_types_cache = None
        self._cache_timestamp = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Supabaseクライアントを初期化"""
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_ANON_KEY')
            
            if not supabase_url or not supabase_key:
                logger.error("Supabase credentials not found in environment variables")
                return
            
            self.client = create_client(supabase_url, supabase_key)
            
            # マネージャーを初期化
            self.user_manager = UserManagerV3(self.client)
            self.session_manager = SessionManagerV3(self.client)
            self.history_manager = HistoryManagerV3(self.client)
            
            logger.info("DatabaseManagerV3 initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing DatabaseManagerV3: {e}")
    
    def is_available(self) -> bool:
        """データベースが利用可能かチェック"""
        try:
            if self.client is None:
                logger.error("Supabase client is None")
                return False
            
            # 簡単なクエリで接続テスト
            result = self.client.table('exercise_categories').select('category_id').limit(1).execute()
            available = bool(result.data)
            logger.info(f"データベース接続確認: {'成功' if available else '失敗'}")
            return available
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_browser_fingerprint(self) -> str:
        """ブラウザフィンガープリントを生成"""
        try:
            # Streamlitのセッション情報からフィンガープリントを生成
            session_info = {
                'session_id': st.session_state.get('session_id', 'unknown'),
                'timestamp': str(datetime.now().timestamp())
            }
            
            # ユーザーエージェントの取得を試行
            try:
                # Streamlitのセッション情報からユーザーエージェントを取得
                if hasattr(st, 'get_user_agent'):
                    session_info['user_agent'] = st.get_user_agent()
                else:
                    # 代替手段：セッション情報から推測
                    session_info['user_agent'] = 'streamlit-app'
            except Exception:
                session_info['user_agent'] = 'streamlit-app'
            
            # ハッシュを生成
            fingerprint = hashlib.sha256(
                json.dumps(session_info, sort_keys=True).encode()
            ).hexdigest()
            
            return fingerprint
            
        except Exception as e:
            logger.error(f"Error generating browser fingerprint: {e}")
            return "fallback_fingerprint"
    
    def get_current_user_id(self) -> str:
        """現在のユーザーIDを取得"""
        try:
            if not self.is_available():
                logger.error("Database not available")
                return "fallback_user"
            
            # セッション管理から認証済みユーザーIDを取得
            try:
                from modules.session_manager import session_manager
                current_session = session_manager.get_user_session()
                
                # デバッグ情報を詳細に出力
                logger.info(f"Session debug - Method: {current_session.identification_method.value}, User ID: {current_session.user_id[:20]}..., Authenticated: {current_session.is_authenticated}, Persistent: {current_session.is_persistent}")
                
                # 認証済みユーザーの場合は実際のUUIDを使用
                if current_session.is_authenticated and current_session.user_id:
                    if not current_session.user_id.startswith('temp_') and len(current_session.user_id) == 36:
                        logger.info(f"Using authenticated user ID: {current_session.user_id}")
                        return current_session.user_id
                    else:
                        logger.warning(f"Invalid authenticated user ID format: {current_session.user_id}")
                        return "fallback_user"
                else:
                    # 認証されていない場合でも、一時的なセッションIDを返す
                    if current_session.user_id and current_session.user_id.startswith('temp_'):
                        logger.debug(f"Using temporary session ID: {current_session.user_id}")
                        return current_session.user_id
                    else:
                        logger.debug(f"User not authenticated or no user_id: authenticated={current_session.is_authenticated}, user_id={current_session.user_id}")
                        # 匿名ユーザーの場合はfallback_userを返す
                        return "fallback_user"
            except Exception as session_error:
                logger.debug(f"Session manager not available: {session_error}")
                return "fallback_user"
            
        except Exception as e:
            logger.error(f"Error getting current user ID: {e}")
            return "fallback_user"
    
    def get_exercise_types(self, force_refresh: bool = False) -> List[ExerciseType]:
        """演習タイプ一覧を取得"""
        try:
            # キャッシュをチェック
            if not force_refresh and self._exercise_types_cache and self._cache_timestamp:
                cache_age = datetime.now() - self._cache_timestamp
                if cache_age.total_seconds() < 300:  # 5分間キャッシュ
                    return self._exercise_types_cache
            
            if not self.is_available():
                logger.error("Database not available")
                return []
            
            result = self.client.table('exercise_types').select(
                'exercise_type_id, category_id, type_name, display_name, description, input_schema, score_schema, difficulty_level, estimated_duration_minutes, is_active'
            ).eq('is_active', True).order('sort_order').execute()
            
            exercise_types = []
            for row in result.data:
                exercise_type = ExerciseType(
                    exercise_type_id=row['exercise_type_id'],
                    category_id=row['category_id'],
                    type_name=row['type_name'],
                    display_name=row['display_name'],
                    description=row['description'],
                    input_schema=row.get('input_schema', {}),
                    score_schema=row.get('score_schema', {}),
                    difficulty_level=row.get('difficulty_level', 1),
                    estimated_duration_minutes=row.get('estimated_duration_minutes', 30),
                    is_active=row.get('is_active', True)
                )
                exercise_types.append(exercise_type)
            
            # キャッシュを更新
            self._exercise_types_cache = exercise_types
            self._cache_timestamp = datetime.now()
            
            logger.info(f"Retrieved {len(exercise_types)} exercise types")
            return exercise_types
            
        except Exception as e:
            logger.error(f"Error getting exercise types: {e}")
            return []
    
    def save_complete_exercise_session(self, exercise_type_id: int, theme: str, 
                                     inputs: List[Tuple[str, str]], scores: List[Tuple[str, float, float]], 
                                     feedback: str, ai_model: str = None) -> bool:
        """完全な演習セッションを保存"""
        try:
            if not self.is_available():
                logger.error("Database not available")
                return False
            
            # 現在のユーザーIDを取得
            user_id = self.get_current_user_id()
            
            # セッションを開始
            session_id = self.session_manager.start_exercise_session(user_id, exercise_type_id, theme)
            
            # 入力を保存
            exercise_inputs = []
            for input_type, content in inputs:
                exercise_input = ExerciseInput(
                    input_id=str(uuid.uuid4()),
                    session_id=session_id,
                    input_type=input_type,
                    content=content
                )
                exercise_inputs.append(exercise_input)
            
            if not self.session_manager.save_exercise_inputs(session_id, exercise_inputs):
                logger.error("Failed to save exercise inputs")
                return False
            
            # スコアを保存
            if scores:
                exercise_scores = []
                for score_category, score_value, max_score in scores:
                    exercise_score = ExerciseScore(
                        score_id=str(uuid.uuid4()),
                        session_id=session_id,
                        score_category=score_category,
                        score_value=score_value,
                        max_score=max_score,
                        ai_model=ai_model
                    )
                    exercise_scores.append(exercise_score)
                
                if not self.session_manager.save_exercise_scores(session_id, exercise_scores):
                    logger.error("Failed to save exercise scores")
                    return False
            
            # フィードバックを保存
            if feedback:
                if not self.session_manager.save_exercise_feedback(
                    session_id, feedback, FeedbackType.GENERAL, ai_model
                ):
                    logger.error("Failed to save exercise feedback")
                    return False
            
            # セッションを完了
            if not self.session_manager.complete_exercise_session(session_id):
                logger.error("Failed to complete exercise session")
                return False
            
            logger.info(f"Successfully saved complete exercise session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving complete exercise session: {e}")
            return False
    
    def get_user_history(self, exercise_type_id: int = None, limit: int = 50) -> List[Dict[str, Any]]:
        """ユーザーの履歴を取得"""
        try:
            if not self.is_available():
                logger.error("Database not available")
                return []
            
            user_id = self.get_current_user_id()
            return self.history_manager.get_user_exercise_history(user_id, exercise_type_id, limit)
            
        except Exception as e:
            logger.error(f"Error getting user history: {e}")
            return []
    
    def get_keyword_history(self, exercise_type_id: int = None, limit: int = 50) -> List[Dict[str, Any]]:
        """キーワード生成履歴を取得"""
        try:
            if not self.is_available():
                logger.error("Database not available")
                return []
            
            user_id = self.get_current_user_id()
            return self.history_manager.get_keyword_generation_history(user_id, exercise_type_id, limit)
            
        except Exception as e:
            logger.error(f"Error getting keyword history: {e}")
            return []
    
    def get_paper_search_history(self, exercise_type_id: int = None, limit: int = 50) -> List[Dict[str, Any]]:
        """論文検索履歴を取得"""
        try:
            if not self.is_available():
                logger.error("Database not available")
                return []
            
            user_id = self.get_current_user_id()
            return self.history_manager.get_paper_search_history(user_id, exercise_type_id, limit)
            
        except Exception as e:
            logger.error(f"Error getting paper search history: {e}")
            return []
    
    def get_all_categories(self) -> List[Dict[str, Any]]:
        """全ての演習カテゴリーを取得"""
        try:
            if not self.is_available():
                logger.error("Database not available")
                return []
            
            result = self.client.table('exercise_categories').select('*').eq('is_active', True).order('sort_order').execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error getting all categories: {e}")
            return []
    
    def get_all_exercise_types(self) -> List[Dict[str, Any]]:
        """全ての演習タイプを取得"""
        try:
            if not self.is_available():
                logger.error("Database not available")
                return []
            
            result = self.client.table('exercise_types').select('*').eq('is_active', True).order('sort_order').execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"Error getting all exercise types: {e}")
            return []
    
    def create_session(self, user_id: str, exercise_type_id: int) -> Optional[str]:
        """セッションを作成"""
        try:
            return self.session_manager.start_exercise_session(user_id, exercise_type_id)
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """セッションを削除"""
        try:
            result = self.client.table('exercise_sessions').delete().eq('session_id', session_id).execute()
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    def save_keyword_generation(self, input_text: str, generated_keywords: List[str], 
                              exercise_type_id: int = None, session_id: str = None, 
                              ai_model: str = None) -> bool:
        """キーワード生成履歴を保存"""
        try:
            if not self.is_available():
                logger.error("Database not available")
                return False
            
            user_id = self.get_current_user_id()
            
            # fallback_userの場合は保存をスキップ
            if user_id == "fallback_user":
                logger.info(f"Fallback user detected, skipping keyword generation save for user: {user_id}")
                return False
            
            # 一時的なユーザーIDの場合は保存をスキップ
            if user_id.startswith("temp_"):
                logger.info(f"Temporary user detected, skipping keyword generation save for user: {user_id}")
                return False
            
            # exercise_type_idからcategory_idを取得
            category_id = None
            if exercise_type_id:
                exercise_type_result = self.client.table('exercise_types').select('category_id').eq('exercise_type_id', exercise_type_id).execute()
                if exercise_type_result.data:
                    category_id = exercise_type_result.data[0]['category_id']
            
            keyword_data = {
                'user_id': user_id,
                'category_id': category_id or 1,  # デフォルトは採用試験カテゴリー
                'input_text': input_text,
                'generated_keywords': generated_keywords,
                'ai_model': ai_model
            }
            
            if session_id:
                keyword_data['session_id'] = session_id
            
            result = self.client.table('category_keyword_history').insert(keyword_data).execute()
            
            if result.data:
                logger.info(f"Saved keyword generation history for user {user_id}")
                return True
            else:
                logger.error("Failed to save keyword generation history")
                return False
                
        except Exception as e:
            logger.error(f"Error saving keyword generation history: {e}")
            return False
    
    def save_paper_search(self, search_query: str, search_results: List[Dict], 
                         selected_papers: List[Dict] = None, exercise_type_id: int = None, 
                         session_id: str = None, ai_model: str = None, search_keywords: List[str] = None,
                         purpose: str = "general") -> bool:
        """論文検索履歴を保存"""
        try:
            print(f"save_paper_search開始: query={search_query}, purpose={purpose}")
            logger.info(f"save_paper_search開始: query={search_query}, purpose={purpose}")
            
            if not self.is_available():
                print("Database not available")
                logger.error("Database not available")
                return False
            
            user_id = self.get_current_user_id()
            print(f"現在のユーザーID: {user_id}")
            logger.info(f"現在のユーザーID: {user_id}")
            
            # fallback_userの場合は保存をスキップ
            if user_id == "fallback_user":
                logger.info(f"Fallback user detected, skipping paper search save for user: {user_id}")
                return False
            
            # 一時的なユーザーIDの場合は保存をスキップ
            if user_id.startswith("temp_"):
                logger.info(f"Temporary user detected, skipping paper search save for user: {user_id}")
                return False
            
            # exercise_type_idからcategory_idを取得
            category_id = None
            if exercise_type_id:
                exercise_type_result = self.client.table('exercise_types').select('category_id').eq('exercise_type_id', exercise_type_id).execute()
                if exercise_type_result.data:
                    category_id = exercise_type_result.data[0]['category_id']
            
            search_data = {
                'user_id': user_id,
                'category_id': category_id or 1,  # デフォルトは採用試験カテゴリー
                'search_query': search_query,
                'search_results': search_results,
                'selected_papers': selected_papers,
                'ai_model': ai_model,
                'purpose': purpose
            }
            
            # search_keywordsが指定されている場合は追加
            if search_keywords:
                search_data['search_keywords'] = search_keywords
            
            if session_id:
                search_data['session_id'] = session_id
            
            print(f"保存データ: {search_data}")
            logger.info(f"保存データ: {search_data}")
            result = self.client.table('category_paper_search_history').insert(search_data).execute()
            
            if result.data:
                print(f"Saved paper search history for user {user_id}")
                logger.info(f"Saved paper search history for user {user_id}")
                return True
            else:
                print(f"Failed to save paper search history. Result: {result}")
                logger.error(f"Failed to save paper search history. Result: {result}")
                return False
                
        except Exception as e:
            print(f"Error saving paper search history: {e}")
            print(f"Search data: {search_data}")
            logger.error(f"Error saving paper search history: {e}")
            logger.error(f"Search data: {search_data}")
            return False

# グローバルインスタンス
db_manager_v3 = DatabaseManagerV3() 