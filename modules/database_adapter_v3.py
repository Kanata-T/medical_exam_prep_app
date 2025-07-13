"""
新しいデータベース設計に対応したアダプター v3
既存コードとの互換性を保ちながら、新しい設計を活用
"""

import logging
import streamlit as st
from typing import List, Dict, Any, Optional
from datetime import datetime
from modules.database_v3 import (
    db_manager_v3, 
    ExerciseInput, 
    ExerciseScore, 
    FeedbackType,
    SessionStatus
)
from modules.session_manager import session_manager

logger = logging.getLogger(__name__)

class DatabaseAdapterV3:
    """
    新しいデータベース設計に対応したアダプタークラス
    既存のページコードを最小限の変更で新システムに対応
    """
    
    def __init__(self):
        self.v3_manager = db_manager_v3
        self.session_mgr = session_manager
        self._current_session = None
    
    def is_available(self) -> bool:
        """データベースが利用可能かチェック"""
        return self.v3_manager.is_available()
    
    def get_session_id(self) -> str:
        """現在のセッションIDを取得（旧API互換）"""
        try:
            if not self._current_session:
                self._current_session = self.session_mgr.get_user_session()
            
            # 匿名ユーザーの場合はfallback_sessionを返す
            if self._current_session.user_id.startswith("temp_"):
                logger.debug(f"Anonymous user detected, using fallback session ID")
                return "fallback_session"
            
            return self._current_session.user_id
            
        except Exception as e:
            logger.error(f"Error getting session ID: {e}")
            return "fallback_session"
    
    def save_practice_history(self, data: Dict[str, Any]) -> bool:
        """
        練習履歴を保存（旧API互換）
        
        Args:
            data: 旧形式のデータ
                - type: 練習タイプ名
                - date: 日付文字列
                - inputs: 入力データの辞書
                - feedback: フィードバック文字列
                - scores: スコア辞書
                - duration_seconds: 所要時間
        """
        try:
            # 重複保存防止のためのチェック
            import hashlib
            data_hash = hashlib.md5(str(data).encode()).hexdigest()
            
            # セッション状態で重複チェック
            if 'last_saved_hash' not in st.session_state:
                st.session_state.last_saved_hash = None
            
            if st.session_state.last_saved_hash == data_hash:
                logger.info("Duplicate save attempt detected, skipping...")
                return True  # 重複の場合は成功として扱う
            
            st.session_state.last_saved_hash = data_hash
            
            # 匿名ユーザーはDB保存不可（UUID型制約のため）
            user_id = self.get_session_id()
            if user_id.startswith("temp_"):
                logger.info("Anonymous (temporary) user detected, skipping DB save.")
                return False  # ローカル保存に自動フォールバック
            
            # 認証済みユーザーの場合は実際のUUIDを使用
            try:
                from modules.session_manager import session_manager
                current_session = session_manager.get_user_session()
                logger.info(f"Session debug - is_authenticated: {current_session.is_authenticated}, user_id: {current_session.user_id}, method: {current_session.identification_method.value}")
                
                if current_session.is_authenticated and current_session.user_id and not current_session.user_id.startswith('temp_'):
                    logger.info(f"Using authenticated user ID: {current_session.user_id}")
                    # 認証済みユーザーの場合はDB保存を許可
                    pass
                else:
                    logger.info(f"User not authenticated - is_authenticated: {current_session.is_authenticated}, user_id: {current_session.user_id}, skipping DB save.")
                    return False  # ローカル保存に自動フォールバック
            except Exception as session_error:
                logger.debug(f"Session manager not available: {session_error}")
                # セッション管理が利用できない場合は一時IDをチェック
                if user_id.startswith("temp_"):
                    logger.info("Temporary user ID detected, skipping DB save.")
                    return False
            logger.info(f"=== DatabaseAdapterV3.save_practice_history START ===")
            logger.info(f"Data type: '{data.get('type', 'MISSING')}'")
            logger.info(f"Data date: {data.get('date', 'MISSING')}")
            logger.info(f"Data inputs keys: {list(data.get('inputs', {}).keys())}")
            logger.info(f"Data scores: {data.get('scores', {})}")
            
            # 演習タイプIDを取得
            exercise_type_id = self._get_exercise_type_id(data.get('type', ''))
            logger.info(f"Retrieved exercise_type_id: {exercise_type_id}")

            if not exercise_type_id:
                logger.error(f"❌ Unknown exercise type: {data.get('type')}")
                # フォールバック処理を追加
                fallback_type_id = self._get_fallback_exercise_type_id(data.get('type', ''))
                if fallback_type_id:
                    logger.info(f"Using fallback exercise type ID: {fallback_type_id}")
                    exercise_type_id = fallback_type_id
                else:
                    logger.error(f"❌ No fallback exercise type found for: {data.get('type')}")
                    return False
            
            logger.info(f"✅ Exercise type ID found: {exercise_type_id}")
            
            # 入力データを変換
            logger.info("Converting inputs...")
            inputs = self._convert_inputs(data.get('inputs', {}))
            logger.info(f"Converted inputs: {inputs[:2] if len(inputs) > 2 else inputs}")  # 最初の2項目のみ表示
            
            # スコアデータを変換
            logger.info("Converting scores...")
            scores = self._convert_scores(data.get('scores', {}))
            logger.info(f"Converted scores: {scores}")
            
            # フィードバックを取得
            feedback = data.get('feedback', '')
            logger.info(f"Feedback length: {len(feedback)} characters")
            
            # テーマを抽出
            theme = self._extract_theme(data.get('inputs', {}))
            logger.info(f"Extracted theme: '{theme[:50]}...' ({len(theme)} chars)")
            
            # v3_manager のステータスを確認
            logger.info("Checking v3_manager availability...")
            if not self.v3_manager:
                logger.error("❌ v3_manager is None")
                return False
            
            if not self.v3_manager.is_available():
                logger.error("❌ v3_manager reports not available")
                return False
            
            logger.info("✅ v3_manager is available")
            
            # 新システムで保存
            logger.info("Calling v3_manager.save_complete_exercise_session...")
            logger.info(f"Parameters: exercise_type_id={exercise_type_id}, theme='{theme[:30]}...', "
                       f"inputs_count={len(inputs)}, scores_count={len(scores)}, "
                       f"feedback_length={len(feedback)}")
            
            success = self.v3_manager.save_complete_exercise_session(
                exercise_type_id=exercise_type_id,
                theme=theme,
                inputs=inputs,
                scores=scores,
                feedback=feedback,
                ai_model='gemini-pro'  # デフォルト
            )
            
            logger.info(f"v3_manager.save_complete_exercise_session returned: {success}")
            
            if success:
                logger.info(f"✅ Successfully converted and saved practice history: {data.get('type')}")
                logger.info(f"=== DatabaseAdapterV3.save_practice_history SUCCESS ===")
            else:
                logger.error(f"❌ v3_manager.save_complete_exercise_session failed")
                logger.info(f"=== DatabaseAdapterV3.save_practice_history FAILED ===")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error saving practice history: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.info(f"=== DatabaseAdapterV3.save_practice_history ERROR ===")
            return False
    
    def load_practice_history(self, practice_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        練習履歴を読み込み（旧API互換）
        
        Returns:
            旧形式のデータリスト
        """
        try:
            # 演習タイプIDを取得
            exercise_type_id = None
            if practice_type:
                exercise_type_id = self._get_exercise_type_id(practice_type)
                if not exercise_type_id:
                    logger.warning(f"Unknown exercise type for loading: {practice_type}")
                    return []
            
            # 新システムから履歴を取得
            new_history = self.v3_manager.get_user_history(exercise_type_id, limit)
            
            # 旧形式に変換
            converted_history = []
            for item in new_history:
                converted_item = self._convert_to_old_format(item)
                if converted_item:
                    converted_history.append(converted_item)
            
            logger.info(f"Loaded and converted {len(converted_history)} history items")
            return converted_history
            
        except Exception as e:
            logger.error(f"Error loading practice history: {e}")
            return []
    
    def get_practice_history_by_type(self, practice_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        指定された練習タイプの履歴を取得
        
        Args:
            practice_type: 新DBキー（例: "english_reading", "free_writing"）
            limit: 取得件数上限
            
        Returns:
            履歴データのリスト（created_at降順）
        """
        try:
            # 新DBから指定タイプの履歴を取得
            if self.v3_manager and self.is_available():
                # practice_typeを新DBのexercise_type_idに変換
                exercise_type_id = self._get_exercise_type_id_by_new_key(practice_type)
                if exercise_type_id:
                    new_history = self.v3_manager.get_user_history(exercise_type_id, limit)
                    
                    # 旧形式に変換
                    converted_history = []
                    for item in new_history:
                        converted_item = self._convert_to_old_format(item)
                        if converted_item:
                            converted_history.append(converted_item)
                    
                    logger.info(f"Retrieved {len(converted_history)} history items for type: {practice_type}")
                    return converted_history
                else:
                    logger.warning(f"Unknown exercise type: {practice_type}")
                    return []
            else:
                logger.error("Database not available")
                return []
                
        except Exception as e:
            logger.error(f"Error getting practice history by type: {e}")
            return []
    
    def delete_practice_history_by_type(self, practice_type: str) -> int:
        """
        指定された練習タイプの履歴を削除
        
        Args:
            practice_type: 新DBキー
            
        Returns:
            削除された件数
        """
        try:
            if not self.v3_manager or not self.is_available():
                logger.error("Database not available")
                return 0
            
            exercise_type_id = self._get_exercise_type_id_by_new_key(practice_type)
            if not exercise_type_id:
                logger.warning(f"Unknown exercise type for deletion: {practice_type}")
                return 0
            
            # 新システムで削除
            deleted_count = self.v3_manager.delete_user_history_by_type(exercise_type_id)
            logger.info(f"Deleted {deleted_count} history items for type: {practice_type}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting practice history by type: {e}")
            return 0
    
    def _get_exercise_type_id_by_new_key(self, practice_type: str) -> Optional[int]:
        """
        新しいDBキーから演習タイプIDを取得
        
        Args:
            practice_type: 新DBキー（例: "english_reading", "free_writing"）
            
        Returns:
            演習タイプID
        """
        try:
            # 新しいスキーマに合わせたキーマッピング
            type_mapping = {
                # 英語読解系 (category_id = 5)
                'english_reading': 'english_reading_practice',
                'keyword_generation_english': 'keyword_generation_english',
                'paper_search_english': 'paper_search_english',
                
                # 自由記述系 (category_id = 4)
                'free_writing': 'free_writing_practice',
                'keyword_generation_free': 'keyword_generation_free',
                'paper_search_free': 'paper_search_free',
                
                # 採用試験系 (category_id = 1)
                'prefecture_adoption': 'prefecture_adoption',
                'keyword_generation_adoption': 'keyword_generation_adoption',
                'paper_search_adoption': 'paper_search_adoption',
                
                # 小論文系 (category_id = 2)
                'essay_writing': 'essay_practice',
                'keyword_generation_essay': 'keyword_generation_essay',
                'paper_search_essay': 'paper_search_essay',
                
                # 面接系 (category_id = 3)
                'interview_prep': 'interview_prep',
                'keyword_generation_interview': 'keyword_generation_interview',
                'paper_search_interview': 'paper_search_interview',
                
                # 旧形式との互換性
                'keyword_generation_paper': 'keyword_generation_english',  # デフォルトで英語読解
                'keyword_generation_freeform': 'keyword_generation_free',  # 自由記述
                'keyword_generation_general': 'keyword_generation_english',  # デフォルトで英語読解
                'paper_search': 'paper_search_english'  # デフォルトで英語読解
            }
            
            # 英語読解系の追加マッピング
            type_mapping['english_reading_standard'] = 'english_reading_practice'
            type_mapping['english_reading_letter_style'] = 'english_reading_practice'
            type_mapping['english_reading_comment_style'] = 'english_reading_practice'

            # 採点系のマッピング
            type_mapping['letter_translation_opinion'] = 'english_reading_practice'
            type_mapping['paper_comment_translation_opinion'] = 'english_reading_practice'
            type_mapping['過去問スタイル採点'] = 'english_reading_practice'

            # キーワード生成・論文検索のマッピング
            type_mapping['keyword_generation_paper'] = 'keyword_generation_english'
            type_mapping['keyword_generation_freeform'] = 'keyword_generation_free'
            type_mapping['keyword_generation_general'] = 'keyword_generation_english'
            type_mapping['paper_search'] = 'paper_search_english'
            type_mapping['キーワード生成'] = 'keyword_generation_english'
            type_mapping['論文検索'] = 'paper_search_english'

            mapped_type = type_mapping.get(practice_type, practice_type)
            
            # 演習タイプ一覧から検索
            exercise_types = self.v3_manager.get_exercise_types()
            for exercise_type in exercise_types:
                if exercise_type.type_name == mapped_type:
                    return exercise_type.exercise_type_id
            
            logger.warning(f"Exercise type not found: {practice_type}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting exercise type ID: {e}")
            return None
    
    def _get_exercise_type_id(self, type_name: str) -> Optional[int]:
        """
        旧形式のタイプ名から演習タイプIDを取得
        
        Args:
            type_name: 旧形式のタイプ名
            
        Returns:
            演習タイプID
        """
        try:
            # 旧形式から新形式へのマッピング
            old_to_new_mapping = {
                # 基本練習タイプ
                '英語読解': 'english_reading_practice',
                '自由記述': 'free_writing_practice',
                'free_writing': 'free_writing_practice',  # 追加：ページで使用される形式
                '医学知識チェック': 'free_writing_practice',  # 追加：医学知識チェックは自由記述として扱う
                '県総採用試験': 'prefecture_adoption',
                '面接準備': 'interview_prep',
                '小論文練習': 'essay_practice',
                
                # キーワード生成・論文検索（用途に応じて振り分け）
                'キーワード生成・論文検索': 'keyword_generation_english',  # デフォルトで英語読解
                'キーワード生成': 'keyword_generation_english',  # デフォルトで英語読解
                '論文検索': 'paper_search_english',  # デフォルトで英語読解
                
                # 英語読解系の追加マッピング
                'english_reading_standard': 'english_reading_practice',
                'english_reading_letter_style': 'english_reading_practice',
                'english_reading_comment_style': 'english_reading_practice',
                '過去問スタイル採点(letter_translation_opinion)': 'english_reading_practice',
                '過去問スタイル採点(paper_comment_translation_opinion)': 'english_reading_practice',
                
                # 採点系のマッピング
                'letter_translation_opinion': 'english_reading_practice',
                'paper_comment_translation_opinion': 'english_reading_practice',
                '過去問スタイル採点': 'english_reading_practice',
                
                # キーワード生成・論文検索のマッピング
                'keyword_generation_paper': 'keyword_generation_english',
                'keyword_generation_freeform': 'keyword_generation_free',
                'keyword_generation_general': 'keyword_generation_english',
                'paper_search': 'paper_search_english',
                'キーワード生成': 'keyword_generation_english',
                '論文検索': 'paper_search_english',
            }
            
            # マッピングを適用
            new_type_name = old_to_new_mapping.get(type_name, type_name)
            
            # 演習タイプ一覧から検索
            exercise_types = self.v3_manager.get_exercise_types()
            for exercise_type in exercise_types:
                if exercise_type.type_name == new_type_name or exercise_type.display_name == type_name:
                    return exercise_type.exercise_type_id
            
            logger.warning(f"Exercise type not found for: {type_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting exercise type ID: {e}")
            return None
    
    def _get_fallback_exercise_type_id(self, type_name: str) -> Optional[int]:
        """フォールバック用の演習タイプID取得"""
        fallback_mapping = {
            'english_reading_standard': 13,  # english_reading_practice
            'english_reading_letter_style': 13,
            'english_reading_comment_style': 13,
            '過去問スタイル採点(letter_translation_opinion)': 13,
            '過去問スタイル採点(paper_comment_translation_opinion)': 13,
            '過去問スタイル採点': 13,
            'letter_translation_opinion': 13,
            'paper_comment_translation_opinion': 13,
            'keyword_generation_paper': 14,  # keyword_generation_english
            'keyword_generation_freeform': 15,  # paper_search_english
            'keyword_generation_general': 14,  # keyword_generation_english
            'paper_search': 15,  # paper_search_english
            'キーワード生成': 14,
            '論文検索': 15,
        }
        return fallback_mapping.get(type_name)
    
    def _convert_inputs(self, old_inputs: Dict[str, Any]) -> List[tuple]:
        """
        旧形式の入力を新形式に変換
        
        Args:
            old_inputs: 旧形式の入力データ
            
        Returns:
            新形式の入力データのリスト
        """
        try:
            inputs = []
            
            # 質問
            if 'question' in old_inputs:
                inputs.append(('question', str(old_inputs['question'])))
            
            # 回答
            if 'answer' in old_inputs:
                inputs.append(('answer', str(old_inputs['answer'])))
            
            # 翻訳
            if 'translation' in old_inputs:
                inputs.append(('translation', str(old_inputs['translation'])))
            
            # キーワード
            if 'keywords' in old_inputs:
                inputs.append(('keywords', str(old_inputs['keywords'])))
            
            # 論文検索
            if 'paper_search' in old_inputs:
                inputs.append(('paper_search', str(old_inputs['paper_search'])))
            
            # その他の入力
            for key, value in old_inputs.items():
                if key not in ['question', 'answer', 'translation', 'keywords', 'paper_search']:
                    inputs.append((key, str(value)))
            
            return inputs
            
        except Exception as e:
            logger.error(f"Error converting inputs: {e}")
            return []
    
    def _convert_scores(self, old_scores: Dict[str, Any]) -> List[tuple]:
        """
        旧形式のスコアを新形式に変換
        
        Args:
            old_scores: 旧形式のスコアデータ
            
        Returns:
            新形式のスコアデータのリスト
        """
        try:
            scores = []
            
            # スコアカテゴリのマッピング
            score_mapping = {
                'clinical_accuracy': 'clinical_accuracy',
                'practical_thinking': 'practical_thinking',
                'communication': 'communication',
                'overall': 'overall',
                'total': 'overall'
            }
            
            for key, value in old_scores.items():
                if isinstance(value, (int, float)):
                    score_category = score_mapping.get(key, key)
                    scores.append((score_category, float(value), 10.0))
                elif isinstance(value, dict):
                    # 辞書形式のスコア（例: {'score': 8, 'max': 10}）
                    score_value = value.get('score', 0)
                    max_score = value.get('max', 10)
                    score_category = score_mapping.get(key, key)
                    scores.append((score_category, float(score_value), float(max_score)))
            
            return scores
            
        except Exception as e:
            logger.error(f"Error converting scores: {e}")
            return []
    
    def _extract_theme(self, old_inputs: Dict[str, Any]) -> str:
        """
        入力データからテーマを抽出
        
        Args:
            old_inputs: 入力データ
            
        Returns:
            テーマ文字列
        """
        try:
            # テーマが直接指定されている場合
            if 'theme' in old_inputs:
                return str(old_inputs['theme'])
            
            # 質問からテーマを抽出
            if 'question' in old_inputs:
                question = str(old_inputs['question'])
                # 最初の100文字をテーマとして使用
                return question[:100] + "..." if len(question) > 100 else question
            
            # その他の入力からテーマを抽出
            for key, value in old_inputs.items():
                if key not in ['answer', 'translation', 'keywords', 'paper_search']:
                    content = str(value)
                    if len(content) > 10:  # 十分な長さがある場合
                        return content[:100] + "..." if len(content) > 100 else content
            
            return "No theme specified"
            
        except Exception as e:
            logger.error(f"Error extracting theme: {e}")
            return "Unknown theme"
    
    def _convert_to_old_format(self, new_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        新形式のデータを旧形式に変換
        
        Args:
            new_item: 新形式のデータ
            
        Returns:
            旧形式のデータ
        """
        try:
            if not new_item:
                return None
            
            # 基本情報
            old_item = {
                'type': self._get_exercise_type_name(new_item.get('exercise_type_id')),
                'date': new_item.get('start_time', ''),
                'duration_seconds': new_item.get('duration_seconds', 0),
                'status': new_item.get('status', 'completed')
            }
            
            # 入力データを変換
            inputs = {}
            for input_item in new_item.get('inputs', []):
                input_type = input_item.get('input_type', 'unknown')
                content = input_item.get('content', '')
                inputs[input_type] = content
            
            old_item['inputs'] = inputs
            
            # スコアデータを変換
            scores = {}
            for score_item in new_item.get('scores', []):
                score_category = score_item.get('score_category', 'unknown')
                score_value = score_item.get('score_value', 0)
                scores[score_category] = score_value
            
            old_item['scores'] = scores
            
            # フィードバックを結合
            feedback_parts = []
            for feedback_item in new_item.get('feedback', []):
                feedback_content = feedback_item.get('feedback_content', '')
                if feedback_content:
                    feedback_parts.append(feedback_content)
            
            old_item['feedback'] = '\n\n'.join(feedback_parts)
            
            return old_item
            
        except Exception as e:
            logger.error(f"Error converting to old format: {e}")
            return None
    
    def _get_exercise_type_name(self, exercise_type_id: int) -> str:
        """
        演習タイプIDから名前を取得
        
        Args:
            exercise_type_id: 演習タイプID
            
        Returns:
            演習タイプ名
        """
        try:
            exercise_types = self.v3_manager.get_exercise_types()
            for exercise_type in exercise_types:
                if exercise_type.exercise_type_id == exercise_type_id:
                    return exercise_type.display_name
            
            return f"Unknown Type {exercise_type_id}"
            
        except Exception as e:
            logger.error(f"Error getting exercise type name: {e}")
            return f"Unknown Type {exercise_type_id}"
    
    def get_database_status(self) -> Dict[str, Any]:
        """データベースの状態を取得"""
        try:
            status = {
                'available': self.is_available(),
                'v3_manager_available': self.v3_manager.is_available() if self.v3_manager else False,
                'session_manager_available': self.session_mgr is not None
            }
            
            if self.is_available():
                # 接続テスト
                try:
                    exercise_types = self.v3_manager.get_exercise_types()
                    status['exercise_types_count'] = len(exercise_types)
                    status['connection_test'] = 'success'
                except Exception as e:
                    status['connection_test'] = f'error: {str(e)}'
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting database status: {e}")
            return {'available': False, 'error': str(e)}
    
    def export_history(self, practice_type: Optional[str] = None) -> str:
        """履歴をエクスポート"""
        try:
            history = self.load_practice_history(practice_type, limit=1000)
            return json.dumps(history, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error exporting history: {e}")
            return "[]"
    
    def get_recent_themes(self, practice_type: str, limit: int = 5) -> List[str]:
        """最近使用されたテーマを取得"""
        try:
            history = self.get_practice_history_by_type(practice_type, limit=limit)
            themes = []
            for item in history:
                theme = item.get('inputs', {}).get('question', '')
                if theme and theme not in themes:
                    themes.append(theme)
            return themes[:limit]
        except Exception as e:
            logger.error(f"Error getting recent themes: {e}")
            return []
    
    def is_theme_recently_used(self, practice_type: str, theme: str, recent_limit: int = 3) -> bool:
        """テーマが最近使用されたかチェック"""
        try:
            recent_themes = self.get_recent_themes(practice_type, recent_limit)
            return theme in recent_themes
        except Exception as e:
            logger.error(f"Error checking recent theme usage: {e}")
            return False
    
    def get_user_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """全ユーザー履歴を取得"""
        try:
            return self.load_practice_history(limit=limit)
        except Exception as e:
            logger.error(f"Error getting user history: {e}")
            return []
    
    def analyze_user_history(self) -> Dict[str, Any]:
        """ユーザー履歴を分析"""
        try:
            history = self.get_user_history(limit=1000)
            
            analysis = {
                'total_sessions': len(history),
                'by_type': {},
                'recent_activity': [],
                'average_scores': {}
            }
            
            # タイプ別集計
            for item in history:
                practice_type = item.get('type', 'Unknown')
                if practice_type not in analysis['by_type']:
                    analysis['by_type'][practice_type] = {
                        'count': 0,
                        'total_duration': 0,
                        'scores': []
                    }
                
                analysis['by_type'][practice_type]['count'] += 1
                analysis['by_type'][practice_type]['total_duration'] += item.get('duration_seconds', 0)
                
                # スコアを収集
                scores = item.get('scores', {})
                for score_category, score_value in scores.items():
                    if isinstance(score_value, (int, float)):
                        analysis['by_type'][practice_type]['scores'].append({
                            'category': score_category,
                            'value': score_value
                        })
            
            # 平均スコアを計算
            for practice_type, data in analysis['by_type'].items():
                if data['scores']:
                    total_score = sum(score['value'] for score in data['scores'])
                    analysis['average_scores'][practice_type] = total_score / len(data['scores'])
            
            # 最近のアクティビティ
            recent_items = sorted(history, key=lambda x: x.get('date', ''), reverse=True)[:10]
            analysis['recent_activity'] = recent_items
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing user history: {e}")
            return {
                'total_sessions': 0,
                'by_type': {},
                'recent_activity': [],
                'average_scores': {}
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """データベース接続をテスト"""
        try:
            status = self.get_database_status()
            
            if status['available']:
                # 演習タイプを取得してテスト
                exercise_types = self.v3_manager.get_exercise_types()
                status['exercise_types'] = [
                    {
                        'id': et.exercise_type_id,
                        'name': et.type_name,
                        'display_name': et.display_name
                    }
                    for et in exercise_types
                ]
                
                # ユーザーID取得テスト
                user_id = self.v3_manager.get_current_user_id()
                status['current_user_id'] = user_id
                
                status['test_result'] = 'success'
            else:
                status['test_result'] = 'failed'
            
            return status
            
        except Exception as e:
            logger.error(f"Error testing connection: {e}")
            return {
                'available': False,
                'test_result': 'error',
                'error': str(e)
            }

# グローバルインスタンス
db_adapter_v3 = DatabaseAdapterV3() 