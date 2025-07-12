"""
新しいリレーショナルデータベース管理システム
PostgreSQLの特性を活かした正規化されたスキーマに対応
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

class SessionStatus(Enum):
    """練習セッションの状態"""
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

@dataclass
class PracticeType:
    """練習タイプのデータクラス"""
    practice_type_id: int
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
class PracticeSession:
    """練習セッションのデータクラス"""
    session_id: str
    user_id: str
    practice_type_id: int
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
class PracticeInput:
    """練習入力のデータクラス"""
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
class PracticeScore:
    """練習スコアのデータクラス"""
    score_id: str
    session_id: str
    score_category: str
    score_value: float
    max_score: float = 10.0
    weight: float = 1.0
    feedback: Optional[str] = None

    @property
    def score_percentage(self) -> float:
        """スコアの百分率を計算"""
        return (self.score_value / self.max_score) * 100 if self.max_score > 0 else 0

class UserManager:
    """ユーザー管理クラス"""
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    def create_or_get_user(self, identifier: str, identifier_type: str = "browser_fingerprint") -> str:
        """ユーザーを作成または取得"""
        try:
            # 既存ユーザーを検索
            if identifier_type == "email":
                result = self.client.table('users').select('user_id').eq('email', identifier).execute()
            else:
                result = self.client.table('users').select('user_id').eq('browser_fingerprint', identifier).execute()
            
            if result.data:
                user_id = result.data[0]['user_id']
                # 最終アクティブ時刻を更新
                self.update_last_active(user_id)
                return user_id
            
            # 新規ユーザー作成
            user_data = {
                'display_name': f'User {identifier[:8]}',
                'preferences': {},
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'is_active': True
            }
            
            if identifier_type == "email":
                user_data['email'] = identifier
            else:
                user_data['browser_fingerprint'] = identifier
            
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

class SessionManager:
    """練習セッション管理クラス"""
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    def start_practice_session(self, user_id: str, practice_type_id: int, theme: str = None) -> str:
        """練習セッションを開始"""
        try:
            # 既存のアクティブセッションを強制的にクリーンアップ
            self._cleanup_user_sessions(user_id)
            
            # 現在時刻をUTCで取得
            from datetime import timezone
            current_time = datetime.now(timezone.utc)
            
            session_data = {
                'user_id': user_id,
                'practice_type_id': practice_type_id,
                'theme': theme,
                'start_time': current_time.isoformat(),
                'status': SessionStatus.IN_PROGRESS.value,
                'completion_percentage': 0.0,
                'metadata': {}
            }
            
            result = self.client.table('practice_sessions').insert(session_data).execute()
            
            if result.data:
                session_id = result.data[0]['session_id']
                logger.info(f"Started practice session: {session_id}")
                return session_id
            else:
                raise Exception("Failed to create practice session")
                
        except Exception as e:
            logger.error(f"Error starting practice session: {e}")
            raise
    
    def _cleanup_user_sessions(self, user_id: str) -> bool:
        """ユーザーの既存セッションをクリーンアップ"""
        try:
            # 進行中のセッションを直接削除（制約回避）
            result = self.client.table('practice_sessions').delete().eq('user_id', user_id).eq('status', SessionStatus.IN_PROGRESS.value).execute()
            
            if result.data:
                logger.info(f"Deleted {len(result.data)} active sessions for user {user_id}")
            else:
                logger.info(f"No active sessions found for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up user sessions: {e}")
            # フォールバック: 中断状態に更新を試行
            try:
                logger.info("Attempting fallback: mark sessions as abandoned")
                result = self.client.table('practice_sessions').update({
                    'status': SessionStatus.ABANDONED.value
                }).eq('user_id', user_id).eq('status', SessionStatus.IN_PROGRESS.value).execute()
                
                if result.data:
                    logger.info(f"Marked {len(result.data)} sessions as abandoned")
                
                return True
            except Exception as fallback_error:
                logger.error(f"Fallback cleanup also failed: {fallback_error}")
                return False
    
    def complete_practice_session(self, session_id: str, completion_percentage: float = 100.0) -> bool:
        """練習セッションを完了"""
        try:
            # セッション情報を取得
            session_result = self.client.table('practice_sessions').select('start_time').eq('session_id', session_id).execute()
            
            if not session_result.data:
                raise Exception("Session not found")
            
            # タイムゾーンを統一して計算
            start_time_str = session_result.data[0]['start_time']
            if start_time_str.endswith('Z'):
                # Zサフィックスを持つ場合は+00:00に変換
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            else:
                # タイムゾーン情報がない場合はUTCとして扱う
                start_time = datetime.fromisoformat(start_time_str)
                if start_time.tzinfo is None:
                    from datetime import timezone
                    start_time = start_time.replace(tzinfo=timezone.utc)
            
            # 現在時刻もUTCで取得
            from datetime import timezone
            end_time = datetime.now(timezone.utc)
            
            # 時間差を計算
            duration_seconds = int((end_time - start_time).total_seconds())
            
            update_data = {
                'end_time': end_time.isoformat(),
                'duration_seconds': duration_seconds,
                'status': SessionStatus.COMPLETED.value,
                'completion_percentage': completion_percentage
            }
            
            result = self.client.table('practice_sessions').update(update_data).eq('session_id', session_id).execute()
            
            success = bool(result.data)
            if success:
                logger.info(f"Completed practice session: {session_id}, duration: {duration_seconds}s")
            
            return success
            
        except Exception as e:
            logger.error(f"Error completing practice session: {e}")
            return False
    
    def abandon_session(self, session_id: str) -> bool:
        """セッションを中断"""
        try:
            # 現在時刻をUTCで取得
            from datetime import timezone
            current_time = datetime.now(timezone.utc)
            
            result = self.client.table('practice_sessions').update({
                'status': SessionStatus.ABANDONED.value,
                'end_time': current_time.isoformat()
            }).eq('session_id', session_id).execute()
            
            return bool(result.data)
        except Exception as e:
            logger.error(f"Error abandoning session: {e}")
            return False
    
    def save_practice_inputs(self, session_id: str, inputs: List[PracticeInput]) -> bool:
        """練習入力データを保存"""
        try:
            input_data = []
            for input_item in inputs:
                input_data.append({
                    'session_id': session_id,
                    'input_type': input_item.input_type,
                    'content': input_item.content,
                    'word_count': input_item.word_count,
                    'input_order': input_item.input_order,
                    'metadata': input_item.metadata
                })
            
            result = self.client.table('practice_inputs').insert(input_data).execute()
            
            success = bool(result.data)
            if success:
                logger.info(f"Saved {len(input_data)} practice inputs for session {session_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error saving practice inputs: {e}")
            return False
    
    def save_practice_scores(self, session_id: str, scores: List[PracticeScore]) -> bool:
        """練習スコアを保存"""
        try:
            score_data = []
            for score in scores:
                score_data.append({
                    'session_id': session_id,
                    'score_category': score.score_category,
                    'score_value': score.score_value,
                    'max_score': score.max_score,
                    'weight': score.weight,
                    'feedback': score.feedback
                })
            
            result = self.client.table('practice_scores').insert(score_data).execute()
            
            success = bool(result.data)
            if success:
                logger.info(f"Saved {len(score_data)} practice scores for session {session_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error saving practice scores: {e}")
            return False
    
    def save_practice_feedback(self, session_id: str, feedback_content: str, 
                             feedback_type: FeedbackType = FeedbackType.GENERAL,
                             ai_model: str = None, tokens_used: int = None) -> bool:
        """練習フィードバックを保存"""
        try:
            feedback_data = {
                'session_id': session_id,
                'feedback_content': feedback_content,
                'feedback_type': feedback_type.value,
                'ai_model': ai_model,
                'tokens_used': tokens_used
            }
            
            result = self.client.table('practice_feedback').insert(feedback_data).execute()
            
            success = bool(result.data)
            if success:
                logger.info(f"Saved practice feedback for session {session_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error saving practice feedback: {e}")
            return False

class HistoryManager:
    """履歴管理クラス"""
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    def get_user_practice_history(self, user_id: str, practice_type_id: int = None, 
                                limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """ユーザーの練習履歴を取得"""
        try:
            # 基本クエリ
            query = self.client.table('practice_sessions').select('''
                session_id,
                practice_type_id,
                theme,
                start_time,
                end_time,
                duration_seconds,
                status,
                completion_percentage,
                practice_types(display_name, category_id, practice_categories(display_name))
            ''').eq('user_id', user_id).eq('status', SessionStatus.COMPLETED.value)
            
            # 練習タイプフィルタ
            if practice_type_id:
                query = query.eq('practice_type_id', practice_type_id)
            
            # 順序付けと制限
            result = query.order('start_time', desc=True).range(offset, offset + limit - 1).execute()
            
            if not result.data:
                return []
            
            # 詳細データを並行取得
            session_ids = [session['session_id'] for session in result.data]
            
            # 入力、スコア、フィードバックを並行取得
            inputs_future = self._get_session_inputs_batch(session_ids)
            scores_future = self._get_session_scores_batch(session_ids)
            feedback_future = self._get_session_feedback_batch(session_ids)
            
            inputs_data = inputs_future
            scores_data = scores_future
            feedback_data = feedback_future
            
            # データを統合
            history = []
            for session in result.data:
                session_id = session['session_id']
                
                history_item = {
                    'session_id': session_id,
                    'practice_type_id': session['practice_type_id'],
                    'practice_type_name': session['practice_types']['display_name'],
                    'category_name': session['practice_types']['practice_categories']['display_name'],
                    'theme': session['theme'],
                    'start_time': session['start_time'],
                    'end_time': session['end_time'],
                    'duration_seconds': session['duration_seconds'],
                    'status': session['status'],
                    'completion_percentage': session['completion_percentage'],
                    'inputs': inputs_data.get(session_id, []),
                    'scores': scores_data.get(session_id, []),
                    'feedback': feedback_data.get(session_id, [])
                }
                
                history.append(history_item)
            
            return history
            
        except Exception as e:
            logger.error(f"Error getting user practice history: {e}")
            return []
    
    def _get_session_inputs_batch(self, session_ids: List[str]) -> Dict[str, List[Dict]]:
        """セッションの入力データを一括取得"""
        try:
            result = self.client.table('practice_inputs').select('*').in_('session_id', session_ids).order('input_order').execute()
            
            inputs_by_session = {}
            for input_item in result.data or []:
                session_id = input_item['session_id']
                if session_id not in inputs_by_session:
                    inputs_by_session[session_id] = []
                inputs_by_session[session_id].append(input_item)
            
            return inputs_by_session
            
        except Exception as e:
            logger.error(f"Error getting session inputs: {e}")
            return {}
    
    def _get_session_scores_batch(self, session_ids: List[str]) -> Dict[str, List[Dict]]:
        """セッションのスコアデータを一括取得"""
        try:
            result = self.client.table('practice_scores').select('*').in_('session_id', session_ids).execute()
            
            scores_by_session = {}
            for score_item in result.data or []:
                session_id = score_item['session_id']
                if session_id not in scores_by_session:
                    scores_by_session[session_id] = []
                
                # スコア百分率を計算
                score_percentage = (score_item['score_value'] / score_item['max_score']) * 100 if score_item['max_score'] > 0 else 0
                score_item['score_percentage'] = score_percentage
                
                scores_by_session[session_id].append(score_item)
            
            return scores_by_session
            
        except Exception as e:
            logger.error(f"Error getting session scores: {e}")
            return {}
    
    def _get_session_feedback_batch(self, session_ids: List[str]) -> Dict[str, List[Dict]]:
        """セッションのフィードバックデータを一括取得"""
        try:
            result = self.client.table('practice_feedback').select('*').in_('session_id', session_ids).order('created_at').execute()
            
            feedback_by_session = {}
            for feedback_item in result.data or []:
                session_id = feedback_item['session_id']
                if session_id not in feedback_by_session:
                    feedback_by_session[session_id] = []
                feedback_by_session[session_id].append(feedback_item)
            
            return feedback_by_session
            
        except Exception as e:
            logger.error(f"Error getting session feedback: {e}")
            return {}
    
    def get_practice_statistics(self, user_id: str, practice_type_id: int = None, 
                              days_back: int = 30) -> Dict[str, Any]:
        """練習統計を取得"""
        try:
            # 日付範囲を設定
            start_date = (datetime.now() - timedelta(days=days_back)).isoformat()
            
            # 基本統計クエリ
            query = self.client.table('practice_sessions').select('''
                session_id,
                practice_type_id,
                duration_seconds,
                completion_percentage,
                start_time
            ''').eq('user_id', user_id).eq('status', SessionStatus.COMPLETED.value).gte('start_time', start_date)
            
            if practice_type_id:
                query = query.eq('practice_type_id', practice_type_id)
            
            sessions_result = query.execute()
            
            if not sessions_result.data:
                return {
                    'total_sessions': 0,
                    'total_duration_minutes': 0,
                    'average_completion': 0,
                    'average_score': 0,
                    'sessions_by_day': {},
                    'score_trends': []
                }
            
            # セッションIDを取得してスコアを集計
            session_ids = [s['session_id'] for s in sessions_result.data]
            scores_result = self.client.table('practice_scores').select('session_id, score_value, max_score').in_('session_id', session_ids).execute()
            
            # 統計計算
            total_sessions = len(sessions_result.data)
            total_duration = sum(s.get('duration_seconds', 0) or 0 for s in sessions_result.data)
            total_duration_minutes = total_duration / 60
            
            completion_percentages = [s.get('completion_percentage', 0) or 0 for s in sessions_result.data]
            average_completion = sum(completion_percentages) / len(completion_percentages) if completion_percentages else 0
            
            # スコア統計
            session_scores = {}
            for score in scores_result.data or []:
                session_id = score['session_id']
                if session_id not in session_scores:
                    session_scores[session_id] = []
                
                score_percentage = (score['score_value'] / score['max_score']) * 100 if score['max_score'] > 0 else 0
                session_scores[session_id].append(score_percentage)
            
            session_avg_scores = [sum(scores) / len(scores) for scores in session_scores.values() if scores]
            average_score = sum(session_avg_scores) / len(session_avg_scores) if session_avg_scores else 0
            
            # 日別セッション数
            sessions_by_day = {}
            for session in sessions_result.data:
                date_str = session['start_time'][:10]  # YYYY-MM-DD
                sessions_by_day[date_str] = sessions_by_day.get(date_str, 0) + 1
            
            return {
                'total_sessions': total_sessions,
                'total_duration_minutes': round(total_duration_minutes, 1),
                'average_completion': round(average_completion, 1),
                'average_score': round(average_score, 1),
                'sessions_by_day': sessions_by_day,
                'score_trends': session_avg_scores
            }
            
        except Exception as e:
            logger.error(f"Error getting practice statistics: {e}")
            return {}
    
    def delete_user_history_by_type(self, user_id: str, practice_type_id: int) -> int:
        """
        指定ユーザーの指定練習タイプの履歴を削除
        
        Args:
            user_id: ユーザーID
            practice_type_id: 練習タイプID
            
        Returns:
            削除件数
        """
        try:
            # まず該当するセッションIDを取得
            sessions_result = self.client.table('practice_sessions').select('session_id').eq(
                'user_id', user_id
            ).eq('practice_type_id', practice_type_id).execute()
            
            if not sessions_result.data:
                logger.info(f"No sessions found for user_id={user_id}, practice_type_id={practice_type_id}")
                return 0
            
            session_ids = [session['session_id'] for session in sessions_result.data]
            deleted_count = len(session_ids)
            
            # 関連データを順番に削除（外部キー制約に配慮）
            
            # 1. practice_feedback を削除
            feedback_result = self.client.table('practice_feedback').delete().in_('session_id', session_ids).execute()
            logger.info(f"Deleted feedback records: {len(feedback_result.data) if feedback_result.data else 0}")
            
            # 2. practice_scores を削除
            scores_result = self.client.table('practice_scores').delete().in_('session_id', session_ids).execute()
            logger.info(f"Deleted score records: {len(scores_result.data) if scores_result.data else 0}")
            
            # 3. practice_inputs を削除
            inputs_result = self.client.table('practice_inputs').delete().in_('session_id', session_ids).execute()
            logger.info(f"Deleted input records: {len(inputs_result.data) if inputs_result.data else 0}")
            
            # 4. 最後に practice_sessions を削除
            sessions_delete_result = self.client.table('practice_sessions').delete().in_('session_id', session_ids).execute()
            logger.info(f"Deleted session records: {len(sessions_delete_result.data) if sessions_delete_result.data else 0}")
            
            logger.info(f"練習履歴削除完了: user_id={user_id}, practice_type_id={practice_type_id}, sessions={deleted_count}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"練習履歴削除エラー: {e}")
            return 0

class AnalyticsManager:
    """分析・統計管理クラス"""
    
    def __init__(self, supabase_client: Client):
        self.client = supabase_client
    
    def get_score_trends(self, user_id: str, practice_type_id: int = None, 
                        score_category: str = None, days_back: int = 30) -> List[Dict[str, Any]]:
        """スコアトレンドを取得"""
        try:
            start_date = (datetime.now() - timedelta(days=days_back)).isoformat()
            
            # セッションとスコアを結合して取得
            query = self.client.table('practice_scores').select('''
                score_category,
                score_value,
                max_score,
                created_at,
                practice_sessions!inner(user_id, practice_type_id, start_time)
            ''').eq('practice_sessions.user_id', user_id).gte('practice_sessions.start_time', start_date)
            
            if practice_type_id:
                query = query.eq('practice_sessions.practice_type_id', practice_type_id)
            
            if score_category:
                query = query.eq('score_category', score_category)
            
            result = query.order('created_at').execute()
            
            trends = []
            for score in result.data or []:
                score_percentage = (score['score_value'] / score['max_score']) * 100 if score['max_score'] > 0 else 0
                trends.append({
                    'date': score['created_at'][:10],
                    'score_category': score['score_category'],
                    'score_percentage': round(score_percentage, 1),
                    'score_value': score['score_value'],
                    'max_score': score['max_score']
                })
            
            return trends
            
        except Exception as e:
            logger.error(f"Error getting score trends: {e}")
            return []
    
    def get_category_performance(self, user_id: str, days_back: int = 30) -> Dict[str, Dict[str, Any]]:
        """カテゴリ別パフォーマンスを取得"""
        try:
            start_date = (datetime.now() - timedelta(days=days_back)).isoformat()
            
            # カテゴリ別の統計を取得
            result = self.client.table('practice_sessions').select('''
                practice_type_id,
                duration_seconds,
                completion_percentage,
                practice_types(display_name, practice_categories(display_name))
            ''').eq('user_id', user_id).eq('status', SessionStatus.COMPLETED.value).gte('start_time', start_date).execute()
            
            category_stats = {}
            for session in result.data or []:
                category_name = session['practice_types']['practice_categories']['display_name']
                
                if category_name not in category_stats:
                    category_stats[category_name] = {
                        'total_sessions': 0,
                        'total_duration': 0,
                        'completion_percentages': [],
                        'practice_types': set()
                    }
                
                stats = category_stats[category_name]
                stats['total_sessions'] += 1
                stats['total_duration'] += session.get('duration_seconds', 0) or 0
                stats['completion_percentages'].append(session.get('completion_percentage', 0) or 0)
                stats['practice_types'].add(session['practice_types']['display_name'])
            
            # 統計を計算
            for category, stats in category_stats.items():
                stats['average_duration_minutes'] = round(stats['total_duration'] / 60, 1)
                stats['average_completion'] = round(sum(stats['completion_percentages']) / len(stats['completion_percentages']), 1) if stats['completion_percentages'] else 0
                stats['practice_types'] = list(stats['practice_types'])
                del stats['completion_percentages']  # 生データは削除
                del stats['total_duration']  # 生データは削除
            
            return category_stats
            
        except Exception as e:
            logger.error(f"Error getting category performance: {e}")
            return {}

class DatabaseManagerV2:
    """新しいデータベース管理メインクラス"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.user_manager: Optional[UserManager] = None
        self.session_manager: Optional[SessionManager] = None
        self.history_manager: Optional[HistoryManager] = None
        self.analytics_manager: Optional[AnalyticsManager] = None
        self._practice_types_cache: Optional[List[PracticeType]] = None
        self._cache_timestamp: Optional[datetime] = None
        
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
            
            # サブマネージャーを初期化
            self.user_manager = UserManager(self.client)
            self.session_manager = SessionManager(self.client)
            self.history_manager = HistoryManager(self.client)
            self.analytics_manager = AnalyticsManager(self.client)
            
            logger.info("DatabaseManagerV2 initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize DatabaseManagerV2: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """データベースが利用可能かチェック"""
        return self.client is not None
    
    def get_browser_fingerprint(self) -> str:
        """ブラウザフィンガープリントを生成"""
        try:
            # Streamlit固有の情報を組み合わせてフィンガープリントを作成
            components = [
                str(st.get_option('server.port') or '8501'),
                str(st.get_option('server.baseUrlPath') or ''),
                # その他利用可能な情報
            ]
            
            # セッション状態の一部も使用（継続性のため）
            if hasattr(st.session_state, 'browser_fingerprint'):
                return st.session_state.browser_fingerprint
            
            fingerprint_string = '|'.join(components)
            fingerprint = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]
            
            # セッション状態に保存
            st.session_state.browser_fingerprint = fingerprint
            
            return fingerprint
            
        except Exception as e:
            logger.error(f"Error generating browser fingerprint: {e}")
            # フォールバック: ランダムなフィンガープリント
            fallback = str(uuid.uuid4())[:16]
            st.session_state.browser_fingerprint = fallback
            return fallback
    
    def get_current_user_id(self) -> str:
        """現在のユーザーIDを取得"""
        if not self.is_available():
            # オフライン時のフォールバック
            if 'offline_user_id' not in st.session_state:
                st.session_state.offline_user_id = str(uuid.uuid4())
            return st.session_state.offline_user_id
        
        try:
            fingerprint = self.get_browser_fingerprint()
            return self.user_manager.create_or_get_user(fingerprint, "browser_fingerprint")
        except Exception as e:
            logger.error(f"Error getting current user ID: {e}")
            # エラー時のフォールバック
            if 'fallback_user_id' not in st.session_state:
                st.session_state.fallback_user_id = str(uuid.uuid4())
            return st.session_state.fallback_user_id
    
    def get_practice_types(self, force_refresh: bool = False) -> List[PracticeType]:
        """練習タイプ一覧を取得（キャッシュ付き）"""
        # キャッシュチェック（5分間有効）
        if not force_refresh and self._practice_types_cache and self._cache_timestamp:
            if datetime.now() - self._cache_timestamp < timedelta(minutes=5):
                return self._practice_types_cache
        
        try:
            result = self.client.table('practice_types').select('''
                practice_type_id,
                category_id,
                type_name,
                display_name,
                description,
                input_schema,
                score_schema,
                difficulty_level,
                estimated_duration_minutes,
                is_active
            ''').eq('is_active', True).order('category_id, sort_order').execute()
            
            practice_types = []
            for item in result.data or []:
                practice_type = PracticeType(
                    practice_type_id=item['practice_type_id'],
                    category_id=item['category_id'],
                    type_name=item['type_name'],
                    display_name=item['display_name'],
                    description=item['description'],
                    input_schema=item['input_schema'] or {},
                    score_schema=item['score_schema'] or {},
                    difficulty_level=item['difficulty_level'],
                    estimated_duration_minutes=item['estimated_duration_minutes'],
                    is_active=item['is_active']
                )
                practice_types.append(practice_type)
            
            # キャッシュ更新
            self._practice_types_cache = practice_types
            self._cache_timestamp = datetime.now()
            
            return practice_types
            
        except Exception as e:
            logger.error(f"Error getting practice types: {e}")
            return []
    
    def save_complete_practice_session(self, practice_type_id: int, theme: str, 
                                     inputs: List[Tuple[str, str]], scores: List[Tuple[str, float, float]], 
                                     feedback: str, ai_model: str = None) -> bool:
        """完全な練習セッションを保存"""
        if not self.is_available():
            logger.warning("Database not available")
            return False
        
        try:
            user_id = self.get_current_user_id()
            
            # セッション開始
            session_id = self.session_manager.start_practice_session(user_id, practice_type_id, theme)
            
            # 入力データを保存
            practice_inputs = []
            for i, (input_type, content) in enumerate(inputs, 1):
                practice_input = PracticeInput(
                    input_id=str(uuid.uuid4()),
                    session_id=session_id,
                    input_type=input_type,
                    content=content,
                    input_order=i
                )
                practice_inputs.append(practice_input)
            
            self.session_manager.save_practice_inputs(session_id, practice_inputs)
            
            # スコアデータを保存
            practice_scores = []
            for score_category, score_value, max_score in scores:
                practice_score = PracticeScore(
                    score_id=str(uuid.uuid4()),
                    session_id=session_id,
                    score_category=score_category,
                    score_value=score_value,
                    max_score=max_score
                )
                practice_scores.append(practice_score)
            
            self.session_manager.save_practice_scores(session_id, practice_scores)
            
            # フィードバックを保存
            self.session_manager.save_practice_feedback(session_id, feedback, ai_model=ai_model)
            
            # セッション完了
            self.session_manager.complete_practice_session(session_id)
            
            logger.info(f"Successfully saved complete practice session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving complete practice session: {e}")
            return False
    
    def get_user_history(self, practice_type_id: int = None, limit: int = 50) -> List[Dict[str, Any]]:
        """ユーザーの練習履歴を取得"""
        if not self.is_available():
            return []
        
        try:
            user_id = self.get_current_user_id()
            return self.history_manager.get_user_practice_history(user_id, practice_type_id, limit)
        except Exception as e:
            logger.error(f"Error getting user history: {e}")
            return []
    
    def get_user_statistics(self, practice_type_id: int = None, days_back: int = 30) -> Dict[str, Any]:
        """ユーザー統計を取得"""
        if not self.is_available():
            return {}
        
        try:
            user_id = self.get_current_user_id()
            return self.history_manager.get_practice_statistics(user_id, practice_type_id, days_back)
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {}
    
    def delete_user_history_by_type(self, practice_type_id: int) -> int:
        """
        現在のユーザーの指定練習タイプの履歴を削除
        
        Args:
            practice_type_id: 練習タイプID
            
        Returns:
            削除件数
        """
        if not self.is_available():
            logger.warning("Database not available for history deletion")
            return 0
        
        try:
            user_id = self.get_current_user_id()
            if not user_id:
                logger.warning("ユーザーIDが取得できないため履歴削除をスキップ")
                return 0
                
            return self.history_manager.delete_user_history_by_type(user_id, practice_type_id)
            
        except Exception as e:
            logger.error(f"ユーザー履歴削除エラー: {e}")
            return 0

# シングルトンインスタンス
db_manager_v2 = DatabaseManagerV2() 