"""
既存コードとの互換性を保つためのデータベースアダプター
旧DatabaseManagerの機能を新システムで実現
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from modules.database_v2 import (
    db_manager_v2, 
    PracticeInput, 
    PracticeScore, 
    FeedbackType
)
from modules.session_manager import session_manager

logger = logging.getLogger(__name__)

class DatabaseAdapter:
    """
    旧DatabaseManagerとの互換性を保つアダプタークラス
    既存のページコードを最小限の変更で新システムに対応
    """
    
    def __init__(self):
        self.v2_manager = db_manager_v2
        self.session_mgr = session_manager
        self._current_session = None
    
    def is_available(self) -> bool:
        """データベースが利用可能かチェック"""
        return self.v2_manager.is_available()
    
    def get_session_id(self) -> str:
        """現在のセッションIDを取得（旧API互換）"""
        try:
            if not self._current_session:
                self._current_session = self.session_mgr.get_user_session()
            
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
            logger.info(f"=== DatabaseAdapter.save_practice_history START ===")
            logger.info(f"Data type: '{data.get('type', 'MISSING')}'")
            logger.info(f"Data date: {data.get('date', 'MISSING')}")
            logger.info(f"Data inputs keys: {list(data.get('inputs', {}).keys())}")
            logger.info(f"Data scores: {data.get('scores', {})}")
            
            # 練習タイプIDを取得
            practice_type_id = self._get_practice_type_id(data.get('type', ''))
            logger.info(f"Retrieved practice_type_id: {practice_type_id}")
            
            if not practice_type_id:
                logger.error(f"❌ Unknown practice type: {data.get('type')}")
                return False
            
            logger.info(f"✅ Practice type ID found: {practice_type_id}")
            
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
            
            # v2_manager のステータスを確認
            logger.info("Checking v2_manager availability...")
            if not self.v2_manager:
                logger.error("❌ v2_manager is None")
                return False
            
            if not self.v2_manager.is_available():
                logger.error("❌ v2_manager reports not available")
                return False
            
            logger.info("✅ v2_manager is available")
            
            # 新システムで保存
            logger.info("Calling v2_manager.save_complete_practice_session...")
            logger.info(f"Parameters: practice_type_id={practice_type_id}, theme='{theme[:30]}...', "
                       f"inputs_count={len(inputs)}, scores_count={len(scores)}, "
                       f"feedback_length={len(feedback)}")
            
            success = self.v2_manager.save_complete_practice_session(
                practice_type_id=practice_type_id,
                theme=theme,
                inputs=inputs,
                scores=scores,
                feedback=feedback,
                ai_model='gemini-pro'  # デフォルト
            )
            
            logger.info(f"v2_manager.save_complete_practice_session returned: {success}")
            
            if success:
                logger.info(f"✅ Successfully converted and saved practice history: {data.get('type')}")
                logger.info(f"=== DatabaseAdapter.save_practice_history SUCCESS ===")
            else:
                logger.error(f"❌ v2_manager.save_complete_practice_session failed")
                logger.info(f"=== DatabaseAdapter.save_practice_history FAILED ===")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Error saving practice history: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.info(f"=== DatabaseAdapter.save_practice_history ERROR ===")
            return False
    
    def load_practice_history(self, practice_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        練習履歴を読み込み（旧API互換）
        
        Returns:
            旧形式のデータリスト
        """
        try:
            # 練習タイプIDを取得
            practice_type_id = None
            if practice_type:
                practice_type_id = self._get_practice_type_id(practice_type)
                if not practice_type_id:
                    logger.warning(f"Unknown practice type for loading: {practice_type}")
                    return []
            
            # 新システムから履歴を取得
            new_history = self.v2_manager.get_user_history(practice_type_id, limit)
            
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
            practice_type: 新DBキー（例: "keyword_generation_paper"）
            limit: 取得件数上限
            
        Returns:
            履歴データのリスト（created_at降順）
        """
        try:
            # 新DBから指定タイプの履歴を取得
            if self.v2_manager and self.is_available():
                # practice_typeを新DBのpractice_type_idに変換
                practice_type_id = self._get_practice_type_id_by_new_key(practice_type)
                if practice_type_id:
                    new_history = self.v2_manager.get_user_history(practice_type_id, limit)
                    
                    # 旧形式に変換
                    converted_history = []
                    for item in new_history:
                        converted_item = self._convert_to_old_format(item)
                        if converted_item:
                            converted_history.append(converted_item)
                    
                    logger.info(f"Retrieved {len(converted_history)} history items for type: {practice_type}")
                    return converted_history
            
            # フォールバック: 旧システムから取得
            logger.warning(f"Using fallback for practice type: {practice_type}")
            return self._get_legacy_history_by_type(practice_type, limit)
            
        except Exception as e:
            logger.error(f"練習タイプ別履歴取得エラー: {e}")
            return []
    
    def delete_practice_history_by_type(self, practice_type: str) -> int:
        """
        指定された練習タイプの履歴を削除
        
        Args:
            practice_type: 新DBキー
            
        Returns:
            削除件数
        """
        try:
            deleted_count = 0
            
            # 新DBから削除
            if self.v2_manager and self.is_available():
                practice_type_id = self._get_practice_type_id_by_new_key(practice_type)
                if practice_type_id:
                    deleted_count = self._delete_user_history_by_type_id(practice_type_id)
                    logger.info(f"Deleted {deleted_count} records from new DB for type: {practice_type}")
            
            # フォールバック: 旧システムからも削除
            legacy_count = self._delete_legacy_history_by_type(practice_type)
            logger.info(f"Deleted {legacy_count} records from legacy system for type: {practice_type}")
            
            total_deleted = deleted_count + legacy_count
            logger.info(f"Total deleted records for type {practice_type}: {total_deleted}")
            
            return total_deleted
            
        except Exception as e:
            logger.error(f"練習タイプ別履歴削除エラー: {e}")
            return 0
    
    def _get_practice_type_id_by_new_key(self, practice_type: str) -> Optional[int]:
        """新DBキーからpractice_type_idを取得"""
        # 新DBキーとIDのマッピング（計画書の完全マッピング表に基づく）
        type_mapping = {
            # paper_finder.py関連（最優先）
            "keyword_generation_paper": 1,
            "keyword_generation_freeform": 2, 
            "keyword_generation_general": 3,
            "paper_search": 4,
            # 県総採用試験関連
            "medical_exam_comprehensive": 5,
            "medical_exam_letter_style": 6,
            "medical_exam_comment_style": 7,
            # 小論文関連
            "essay_practice": 8,
            # 面接関連
            "interview_practice_general": 9,
            "interview_practice_single": 10,
            "interview_practice_session": 11,
            # 英語読解関連
            "english_reading_standard": 12,
            "english_reading_letter_style": 13,
            "english_reading_comment_style": 14,
            # 自由記述関連
            "free_writing": 15
        }
        
        practice_type_id = type_mapping.get(practice_type)
        if practice_type_id:
            return practice_type_id
            
        # 動的にpractice_typesから検索（フォールバック）
        try:
            practice_types = self.v2_manager.get_practice_types()
            for pt in practice_types:
                if pt.type_name == practice_type:
                    return pt.practice_type_id
        except Exception as e:
            logger.error(f"Error searching practice types: {e}")
            
        return None
    
    def _delete_user_history_by_type_id(self, practice_type_id: int) -> int:
        """新DBから指定practice_type_idの履歴を削除"""
        try:
            # DatabaseManagerV2に削除メソッドが実装されている場合
            if hasattr(self.v2_manager, 'delete_user_history_by_type'):
                return self.v2_manager.delete_user_history_by_type(practice_type_id)
            
            # 実装されていない場合のフォールバック
            logger.warning("DatabaseManagerV2.delete_user_history_by_type not implemented, skipping new DB deletion")
            return 0
            
        except Exception as e:
            logger.error(f"新DB履歴削除エラー: {e}")
            return 0
    
    def _get_legacy_history_by_type(self, practice_type: str, limit: int) -> List[Dict[str, Any]]:
        """旧システムから指定タイプの履歴を取得（フォールバック）"""
        try:
            from modules.utils import load_history
            all_history = load_history()
            
            # 旧DBキーから新DBキーへのマッピング
            legacy_mapping = {
                "keyword_generation_paper": ["キーワード生成（論文検索用）"],
                "keyword_generation_freeform": ["キーワード生成（自由記述用）"],
                "keyword_generation_general": ["キーワード生成"],
                "paper_search": ["論文検索"],
                "medical_exam_comprehensive": ["採用試験"],
                "medical_exam_letter_style": ["過去問スタイル採用試験 - Letter"],
                "medical_exam_comment_style": ["過去問スタイル採用試験 - 論文コメント"],
                "essay_practice": ["小論文対策"],
                "interview_practice_general": ["面接対策"],
                "interview_practice_single": ["面接対策(単発)"],
                "interview_practice_session": ["面接対策(セッション)"],
                "english_reading_standard": ["英語読解"],
                "english_reading_letter_style": ["過去問スタイル英語読解 - Letter"],
                "english_reading_comment_style": ["過去問スタイル英語読解 - 論文コメント"],
                "free_writing": ["医学部採用試験 自由記述"]
            }
            
            legacy_types = legacy_mapping.get(practice_type, [])
            filtered_history = []
            
            for item in all_history:
                item_type = item.get('type', '')
                # 完全一致または部分一致チェック
                if any(legacy_type in item_type for legacy_type in legacy_types):
                    filtered_history.append(item)
            
            # 日付順でソート（最新順）
            filtered_history.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            return filtered_history[:limit]
            
        except Exception as e:
            logger.error(f"旧システム履歴取得エラー: {e}")
            return []
    
    def _delete_legacy_history_by_type(self, practice_type: str) -> int:
        """旧システムから指定タイプの履歴を削除（フォールバック）"""
        try:
            import os
            import json
            from modules.utils import HISTORY_DIR
            
            # 旧DBキーマッピング（削除用）
            legacy_mapping = {
                "keyword_generation_paper": ["キーワード生成（論文検索用）"],
                "keyword_generation_freeform": ["キーワード生成（自由記述用）"],
                "keyword_generation_general": ["キーワード生成"],
                "paper_search": ["論文検索"],
                "medical_exam_comprehensive": ["採用試験"],
                "medical_exam_letter_style": ["過去問スタイル採用試験 - Letter"],
                "medical_exam_comment_style": ["過去問スタイル採用試験 - 論文コメント"],
                "essay_practice": ["小論文対策"],
                "interview_practice_general": ["面接対策"],
                "interview_practice_single": ["面接対策(単発)"],
                "interview_practice_session": ["面接対策(セッション)"],
                "english_reading_standard": ["英語読解"],
                "english_reading_letter_style": ["過去問スタイル英語読解 - Letter"],
                "english_reading_comment_style": ["過去問スタイル英語読解 - 論文コメント"],
                "free_writing": ["医学部採用試験 自由記述"]
            }
            
            legacy_types = legacy_mapping.get(practice_type, [])
            deleted_count = 0
            
            if os.path.exists(HISTORY_DIR) and legacy_types:
                for filename in os.listdir(HISTORY_DIR):
                    if filename.endswith('.json'):
                        filepath = os.path.join(HISTORY_DIR, filename)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            item_type = data.get('type', '')
                            
                            # 指定タイプに一致する場合は削除
                            if any(legacy_type in item_type for legacy_type in legacy_types):
                                os.remove(filepath)
                                deleted_count += 1
                                
                        except (json.JSONDecodeError, IOError, OSError):
                            continue
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"旧システム履歴削除エラー: {e}")
            return 0

    def _get_practice_type_id(self, type_name: str) -> Optional[int]:
        """練習タイプ名からIDを取得（新形式対応版）"""
        try:
            logger.info(f"Getting practice type ID for: '{type_name}'")
            
            # 新形式のtype名として直接検索を最初に試行
            practice_type_id = self._get_practice_type_id_by_new_key(type_name)
            if practice_type_id:
                logger.info(f"Found practice type ID {practice_type_id} for new format key: '{type_name}'")
                return practice_type_id
            
            # 新形式で見つからない場合、旧形式からの変換を試行
            logger.info(f"'{type_name}' not found as new format, trying legacy mapping...")
            
            # 練習タイプのマッピング（旧形式から新形式への変換）
            type_mapping = {
                # 旧形式のタイプ名から新DBキーへのマッピング
                '採用試験': 'medical_exam_comprehensive',
                '過去問スタイル採用試験': 'medical_exam_comprehensive',
                '過去問スタイル採用試験 - Letter形式（翻訳 + 意見）': 'medical_exam_letter_style',
                '過去問スタイル採用試験 - 論文コメント形式（コメント翻訳 + 意見）': 'medical_exam_comment_style',
                '英語読解': 'english_reading_standard',
                '過去問スタイル英語読解': 'english_reading_standard',
                '過去問スタイル英語読解 - Letter形式（翻訳 + 意見）': 'english_reading_letter_style',
                '過去問スタイル英語読解 - 論文コメント形式（コメント翻訳 + 意見）': 'english_reading_comment_style',
                '医学部採用試験 自由記述': 'free_writing',
                '小論文対策': 'essay_practice',
                '面接対策': 'interview_practice_general',
                '面接対策(単発)': 'interview_practice_single',
                '面接対策(セッション)': 'interview_practice_session',
                'キーワード生成': 'keyword_generation_general',
                'キーワード生成（論文検索用）': 'keyword_generation_paper',
                'キーワード生成（自由記述用）': 'keyword_generation_freeform',
                '論文検索': 'paper_search'
            }
            
            # 旧形式から新DBキーに変換
            mapped_key = type_mapping.get(type_name)
            if mapped_key:
                logger.info(f"Mapped legacy type '{type_name}' to new key '{mapped_key}'")
                # 新DBキーからIDを取得
                practice_type_id = self._get_practice_type_id_by_new_key(mapped_key)
                if practice_type_id:
                    logger.info(f"Found practice type ID {practice_type_id} for mapped key: '{mapped_key}'")
                    return practice_type_id
            
            logger.error(f"Could not find practice type ID for: '{type_name}' (neither new format nor legacy mapping)")
            return None
            
        except Exception as e:
            logger.error(f"Error getting practice type ID: {e}")
            return None
    
    def _convert_inputs(self, old_inputs: Dict[str, Any]) -> List[tuple]:
        """旧形式の入力データを新形式に変換"""
        inputs = []
        
        try:
            # 共通フィールドのマッピング
            field_mapping = {
                'theme': 'theme',
                'question': 'question',
                'answer': 'answer',
                'original_paper': 'original_paper',
                'translation': 'translation',
                'opinion': 'opinion',
                'essay': 'essay',
                'keywords': 'keywords',
                'category': 'category',
                'search_keywords': 'search_keywords',
                'paper_title': 'paper_title',
                'paper_abstract': 'paper_abstract'
            }
            
            for old_key, new_key in field_mapping.items():
                if old_key in old_inputs and old_inputs[old_key]:
                    inputs.append((new_key, str(old_inputs[old_key])))
            
            # 入力がない場合はダミーデータを追加
            if not inputs:
                inputs.append(('content', 'No input data'))
            
            return inputs
            
        except Exception as e:
            logger.error(f"Error converting inputs: {e}")
            return [('content', 'Error converting input data')]
    
    def _convert_scores(self, old_scores: Dict[str, Any]) -> List[tuple]:
        """旧形式のスコアデータを新形式に変換"""
        scores = []
        
        try:
            for category, score_value in old_scores.items():
                if score_value is not None:
                    try:
                        score_float = float(score_value)
                        # スコアの最大値を推定（10点満点が一般的）
                        max_score = 10.0 if score_float <= 10 else 100.0
                        scores.append((category, score_float, max_score))
                    except ValueError:
                        logger.warning(f"Invalid score value: {score_value}")
            
            return scores
            
        except Exception as e:
            logger.error(f"Error converting scores: {e}")
            return []
    
    def _extract_theme(self, old_inputs: Dict[str, Any]) -> str:
        """旧形式の入力からテーマを抽出"""
        theme_fields = ['theme', 'category', 'keywords', 'paper_title']
        
        for field in theme_fields:
            if field in old_inputs and old_inputs[field]:
                return str(old_inputs[field])[:200]  # 最大200文字
        
        return ''
    
    def _convert_to_old_format(self, new_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """新形式のデータを旧形式に変換"""
        try:
            # 基本情報
            old_format = {
                'type': new_item.get('practice_type_name', ''),
                'date': new_item.get('start_time', ''),
                'duration_seconds': new_item.get('duration_seconds', 0),
                'duration_display': self._format_duration(new_item.get('duration_seconds', 0))
            }
            
            # 入力データを変換
            inputs = {}
            for input_item in new_item.get('inputs', []):
                input_type = input_item.get('input_type', '')
                content = input_item.get('content', '')
                inputs[input_type] = content
            
            old_format['inputs'] = inputs
            
            # スコアデータを変換
            scores = {}
            for score_item in new_item.get('scores', []):
                category = score_item.get('score_category', '')
                score_value = score_item.get('score_value', 0)
                scores[category] = score_value
            
            old_format['scores'] = scores
            
            # フィードバックを統合
            feedback_parts = []
            for feedback_item in new_item.get('feedback', []):
                content = feedback_item.get('feedback_content', '')
                if content:
                    feedback_parts.append(content)
            
            old_format['feedback'] = '\n\n'.join(feedback_parts)
            
            return old_format
            
        except Exception as e:
            logger.error(f"Error converting to old format: {e}")
            return None
    
    def _format_duration(self, duration_seconds: int) -> str:
        """所要時間を表示用文字列に変換"""
        if not duration_seconds:
            return "未記録"
        
        minutes = duration_seconds // 60
        seconds = duration_seconds % 60
        
        if minutes > 0:
            return f"{minutes}分{seconds}秒"
        else:
            return f"{seconds}秒"
    
    # 旧APIとの互換性のため追加メソッド
    
    def get_database_status(self) -> Dict[str, Any]:
        """データベース接続状況を取得"""
        session = self.session_mgr.get_user_session()
        
        return {
            'available': self.is_available(),
            'session_id': session.user_id[:8] + '...',
            'identification_method': session.identification_method.value,
            'is_persistent': session.is_persistent,
            'offline_records': 0  # 新システムでは常に0
        }
    
    def export_history(self, practice_type: Optional[str] = None) -> str:
        """履歴データをJSON形式でエクスポート"""
        import json
        
        history = self.load_practice_history(practice_type)
        return json.dumps(history, ensure_ascii=False, indent=2)
    
    def get_recent_themes(self, practice_type: str, limit: int = 5) -> List[str]:
        """最近のテーマを取得"""
        try:
            history = self.load_practice_history(practice_type, limit * 2)
            themes = []
            
            for item in history:
                inputs = item.get('inputs', {})
                theme = inputs.get('theme') or inputs.get('category') or inputs.get('keywords')
                
                if theme and theme not in themes:
                    themes.append(theme)
                    if len(themes) >= limit:
                        break
            
            return themes
            
        except Exception as e:
            logger.error(f"Error getting recent themes: {e}")
            return []
    
    def is_theme_recently_used(self, practice_type: str, theme: str, recent_limit: int = 3) -> bool:
        """テーマが最近使用されたかチェック"""
        recent_themes = self.get_recent_themes(practice_type, recent_limit)
        return theme in recent_themes
    
    def get_user_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        ユーザーの全練習履歴を取得（学習履歴ページ用）
        
        Args:
            limit: 取得件数上限
            
        Returns:
            履歴データのリスト（日付降順）
        """
        try:
            # 新システムから全種類の履歴を取得
            if self.v2_manager and self.is_available():
                new_history = self.v2_manager.get_user_history(None, limit)
                
                # 旧形式に変換
                converted_history = []
                for item in new_history:
                    converted_item = self._convert_to_old_format(item)
                    if converted_item:
                        converted_history.append(converted_item)
                
                logger.info(f"Retrieved {len(converted_history)} total history items")
                return converted_history
            else:
                # フォールバック: 旧システムから取得
                logger.warning("Using fallback for user history")
                return self._get_legacy_all_history(limit)
                
        except Exception as e:
            logger.error(f"Error getting user history: {e}")
            return []
    
    def _get_legacy_all_history(self, limit: int) -> List[Dict[str, Any]]:
        """旧システムから全履歴を取得（フォールバック）"""
        try:
            from modules.utils import load_history
            all_history = load_history()
            
            # 日付順でソート（最新順）
            all_history.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            return all_history[:limit]
            
        except Exception as e:
            logger.error(f"旧システム履歴取得エラー: {e}")
            return []
    
    def analyze_user_history(self) -> Dict[str, Any]:
        """
        ユーザー履歴の分析情報を取得
        
        Returns:
            分析結果の辞書
        """
        try:
            history = self.get_user_history(1000)  # 多めに取得して分析
            
            if not history:
                return {"error": "No history data available"}
            
            # 基本統計
            total_sessions = len(history)
            practice_dates = set()
            total_duration = 0
            all_scores = []
            
            # 練習タイプ別統計
            by_practice_type = {}
            
            for item in history:
                # 日付処理
                date_str = item.get('date', '')
                if date_str:
                    try:
                        date_part = date_str.split('T')[0]  # 日付部分のみ
                        practice_dates.add(date_part)
                    except:
                        pass
                
                # 所要時間
                duration = item.get('duration_seconds', 0)
                if duration:
                    total_duration += duration
                
                # スコア
                scores = item.get('scores', {})
                if scores:
                    score_values = [float(v) for v in scores.values() if v is not None]
                    if score_values:
                        avg_score = sum(score_values) / len(score_values)
                        all_scores.append(avg_score)
                
                # 練習タイプ別
                practice_type = item.get('type', '不明')
                if practice_type not in by_practice_type:
                    by_practice_type[practice_type] = {
                        'count': 0,
                        'scores': [],
                        'last_practice': ''
                    }
                
                by_practice_type[practice_type]['count'] += 1
                if scores:
                    score_values = [float(v) for v in scores.values() if v is not None]
                    if score_values:
                        avg_score = sum(score_values) / len(score_values)
                        by_practice_type[practice_type]['scores'].append(avg_score)
                
                # 最新練習日
                if date_str > by_practice_type[practice_type]['last_practice']:
                    by_practice_type[practice_type]['last_practice'] = date_str
            
            # 練習タイプ別の平均・最高スコア計算
            for practice_type, stats in by_practice_type.items():
                if stats['scores']:
                    stats['avg_score'] = sum(stats['scores']) / len(stats['scores'])
                    stats['max_score'] = max(stats['scores'])
                else:
                    stats['avg_score'] = 0
                    stats['max_score'] = 0
            
            # 時系列データ（簡易版）
            timeline = []
            for item in history[-20:]:  # 最新20件
                scores = item.get('scores', {})
                if scores:
                    score_values = [float(v) for v in scores.values() if v is not None]
                    if score_values:
                        avg_score = sum(score_values) / len(score_values)
                        timeline.append({
                            'date': item.get('date', '').split('T')[0],
                            'score': avg_score,
                            'practice_type': item.get('type', '不明')
                        })
            
            analysis_result = {
                'total_sessions': total_sessions,
                'practice_days': len(practice_dates),
                'average_score': sum(all_scores) / len(all_scores) if all_scores else 0,
                'total_duration_hours': total_duration / 3600,
                'by_practice_type': by_practice_type,
                'timeline': timeline
            }
            
            logger.info(f"Analyzed {total_sessions} sessions across {len(practice_dates)} days")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing user history: {e}")
            return {"error": str(e)}
    
    def test_connection(self) -> Dict[str, Any]:
        """データベース接続をテスト"""
        try:
            if not self.is_available():
                return {"success": False, "error": "Database not available"}
            
            # 簡単な接続テスト
            history = self.get_user_history(1)
            
            return {
                "success": True,
                "record_count": len(history),
                "connection_type": "new_database" if self.v2_manager else "legacy"
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# 旧システムとの互換性のためのシングルトンインスタンス
db_manager = DatabaseAdapter() 