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

class PracticeTypeManager:
    """練習タイプの管理と分類を行うクラス"""
    
    # 練習タイプの階層的分類
    PRACTICE_TYPE_CATEGORIES = {
        "採用試験系": {
            "標準採用試験": ["採用試験"],
            "過去問スタイル採用試験": [
                "過去問スタイル採用試験",
                "過去問スタイル採用試験 - Letter形式（翻訳 + 意見）",
                "過去問スタイル採用試験 - 論文コメント形式（コメント翻訳 + 意見）"
            ]
        },
        "英語読解系": {
            "標準英語読解": ["英語読解"],
            "過去問スタイル英語読解": [
                "過去問スタイル英語読解",
                "過去問スタイル英語読解 - Letter形式（翻訳 + 意見）",
                "過去問スタイル英語読解 - 論文コメント形式（コメント翻訳 + 意見）"
            ]
        },
        "記述系": {
            "小論文対策": ["小論文対策"],
            "自由記述": ["医学部採用試験 自由記述"]
        },
        "面接系": {
            "単発面接": ["面接対策(単発)"],
            "セッション面接": ["面接対策(セッション)"]
        },
        "論文研究系": {
            "キーワード生成": [
                "キーワード生成",
                "キーワード生成（論文検索用）",
                "キーワード生成（自由記述用）"
            ],
            "論文検索": ["論文検索"]
        }
    }
    
    @classmethod
    def get_category_for_type(cls, practice_type: str) -> tuple[str, str]:
        """練習タイプからカテゴリと種別を取得"""
        for category, subcategories in cls.PRACTICE_TYPE_CATEGORIES.items():
            for subcategory, types in subcategories.items():
                if practice_type in types or any(practice_type.startswith(t) for t in types):
                    return category, subcategory
        return "その他", "不明"
    
    @classmethod
    def is_exam_style_type(cls, practice_type: str) -> bool:
        """過去問スタイルかどうかを判定"""
        return "過去問スタイル" in practice_type
    
    @classmethod
    def is_keyword_generation_type(cls, practice_type: str) -> bool:
        """キーワード生成タイプかどうかを判定"""
        return practice_type.startswith("キーワード生成")
    
    @classmethod
    def is_paper_search_type(cls, practice_type: str) -> bool:
        """論文検索タイプかどうかを判定"""
        return practice_type == "論文検索"
    
    @classmethod
    def get_display_name(cls, practice_type: str) -> str:
        """表示用の短縮名を取得"""
        display_names = {
            "過去問スタイル採用試験 - Letter形式（翻訳 + 意見）": "過去問採用試験（Letter）",
            "過去問スタイル採用試験 - 論文コメント形式（コメント翻訳 + 意見）": "過去問採用試験（Comment）",
            "過去問スタイル英語読解 - Letter形式（翻訳 + 意見）": "過去問英語読解（Letter）",
            "過去問スタイル英語読解 - 論文コメント形式（コメント翻訳 + 意見）": "過去問英語読解（Comment）",
            "キーワード生成（論文検索用）": "キーワード生成（論文用）",
            "キーワード生成（自由記述用）": "キーワード生成（記述用）",
            "医学部採用試験 自由記述": "自由記述"
        }
        return display_names.get(practice_type, practice_type)

class DatabaseManager:
    """Supabaseを使った履歴データベース管理クラス"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.practice_type_manager = PracticeTypeManager()
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
    
    def _extract_inputs_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """練習タイプに応じてinputsデータを抽出（改良版）"""
        practice_type = data.get('type', '')
        
        # キーワード生成系の場合の特別処理
        if self.practice_type_manager.is_keyword_generation_type(practice_type):
            inputs_data = {
                'keywords': data.get('keywords', ''),
                'category': data.get('category', ''),
                'rationale': data.get('rationale', ''),
                'purpose': self._extract_keyword_purpose(practice_type)  # 用途を追加
            }
            logger.info(f"Keyword generation inputs: {inputs_data}")
            return inputs_data
        
        # 論文検索の場合の特別処理
        elif self.practice_type_manager.is_paper_search_type(practice_type):
            inputs_data = {
                'search_keywords': data.get('search_keywords', ''),
                'paper_title': data.get('paper_title', ''),
                'paper_abstract': data.get('paper_abstract', ''),
                'study_type': data.get('study_type', ''),
                'relevance_score': data.get('relevance_score', ''),
                'citations': data.get('citations', [])
            }
            logger.info(f"Paper search inputs: {list(inputs_data.keys())}")
            return inputs_data
        
        # 過去問スタイル系の場合の特別処理
        elif self.practice_type_manager.is_exam_style_type(practice_type):
            inputs_data = data.get('inputs', {})
            # 過去問スタイルの場合は形式情報も保存
            inputs_data['exam_style_variant'] = self._extract_exam_style_variant(practice_type)
            logger.info(f"Exam style inputs for {practice_type}: {list(inputs_data.keys())}")
            return inputs_data
        
        # 通常の練習の場合
        else:
            inputs_data = data.get('inputs', {})
            logger.info(f"Regular practice inputs for {practice_type}: {list(inputs_data.keys()) if isinstance(inputs_data, dict) else 'Not a dict'}")
            return inputs_data
    
    def _extract_keyword_purpose(self, practice_type: str) -> str:
        """キーワード生成の用途を抽出"""
        if "論文検索用" in practice_type:
            return "paper_search"
        elif "自由記述用" in practice_type:
            return "free_writing"
        else:
            return "general"
    
    def _extract_exam_style_variant(self, practice_type: str) -> str:
        """過去問スタイルのバリエーションを抽出"""
        if "Letter形式" in practice_type:
            return "letter_format"
        elif "論文コメント形式" in practice_type:
            return "comment_format"
        else:
            return "standard"

    def _restore_data_structure(self, practice_type: str, practice_date: str, inputs: Dict[str, Any], 
                               feedback: str, scores: Dict[str, Any], duration_seconds: int, 
                               duration_display: str) -> Dict[str, Any]:
        """練習タイプに応じてデータ構造を復元（改良版）"""
        
        # 共通データ構造
        base_result = {
            'type': practice_type,
            'date': practice_date,
            'feedback': feedback,
            'scores': scores,
            'duration_seconds': duration_seconds,
            'duration_display': duration_display,
            'category': self.practice_type_manager.get_category_for_type(practice_type)[0],
            'subcategory': self.practice_type_manager.get_category_for_type(practice_type)[1],
            'display_name': self.practice_type_manager.get_display_name(practice_type)
        }
        
        # キーワード生成の場合の特別処理
        if self.practice_type_manager.is_keyword_generation_type(practice_type):
            # inputsから直接キーとして展開
            base_result.update({
                'keywords': inputs.get('keywords', ''),
                'category': inputs.get('category', ''),
                'rationale': inputs.get('rationale', ''),
                'purpose': inputs.get('purpose', 'general')
            })
            logger.debug(f"Restored keyword generation data: {list(base_result.keys())}")
            return base_result
        
        # 論文検索の場合の特別処理  
        elif self.practice_type_manager.is_paper_search_type(practice_type):
            # inputsから直接キーとして展開
            base_result.update({
                'search_keywords': inputs.get('search_keywords', ''),
                'paper_title': inputs.get('paper_title', ''),
                'paper_abstract': inputs.get('paper_abstract', ''),
                'study_type': inputs.get('study_type', ''),
                'relevance_score': inputs.get('relevance_score', ''),
                'citations': inputs.get('citations', [])
            })
            logger.debug(f"Restored paper search data: {list(base_result.keys())}")
            return base_result
        
        # 通常の練習の場合（過去問スタイルを含む）
        else:
            base_result['inputs'] = inputs
            # 過去問スタイルの場合は追加情報を設定
            if self.practice_type_manager.is_exam_style_type(practice_type):
                base_result['exam_style_variant'] = inputs.get('exam_style_variant', 'standard')
            
            logger.debug(f"Restored regular practice data for {practice_type}: inputs keys = {list(inputs.keys()) if isinstance(inputs, dict) else 'Not a dict'}")
            return base_result
    
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
            # 練習タイプ別のデータ構造に対応
            inputs_data = self._extract_inputs_data(data)
            scores_data = data.get('scores', {})
            
            logger.info(f"Extracted inputs_data type: {type(inputs_data)}, keys: {list(inputs_data.keys()) if isinstance(inputs_data, dict) else 'Not a dict'}")
            
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
                        
                        # 練習タイプに応じてデータ構造を復元
                        converted_item = self._restore_data_structure(
                            item['practice_type'],
                            item['practice_date'],
                            inputs,
                            item['feedback'],
                            scores,
                            item['duration_seconds'],
                            item['duration_display']
                        )
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

    def load_all_practice_history_batch(self, practice_types: Optional[List[str]] = None, limit: int = 1000) -> Dict[str, List[Dict[str, Any]]]:
        """
        複数の練習タイプの履歴を一括で効率的に取得します。
        重複するAPIリクエストを削減し、パフォーマンスを向上させます。
        
        Args:
            practice_types: 取得したい練習タイプのリスト。Noneの場合は全てを取得
            limit: 取得する最大レコード数
            
        Returns:
            練習タイプをキーとした辞書。各値は履歴のリスト
        """
        if not self.is_available():
            logger.warning("Database not available. Loading from session state only.")
            return self._load_batch_from_session_state(practice_types, limit)

        try:
            session_id = self.get_session_id()
            
            # 一度のクエリで全履歴を取得
            query = self.client.table('practice_history').select('*').eq('session_id', session_id)
            
            if practice_types:
                # IN句を使用して複数の練習タイプを一度に取得
                query = query.in_('practice_type', practice_types)
            
            result = query.order('practice_date', desc=True).limit(limit).execute()
            
            # 練習タイプ別に分類
            history_by_type = {}
            if practice_types:
                # 指定された練習タイプで初期化
                for practice_type in practice_types:
                    history_by_type[practice_type] = []
            
            if result.data:
                for item in result.data:
                    try:
                        practice_type = item['practice_type']
                        
                        # JSON解析を安全に実行
                        inputs = {}
                        if item['inputs']:
                            try:
                                inputs = json.loads(item['inputs'])
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse inputs JSON: {e}")
                        
                        scores = {}
                        if item['scores']:
                            try:
                                scores = json.loads(item['scores'])
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse scores JSON: {e}")
                        
                        # 練習タイプに応じてデータ構造を復元
                        converted_item = self._restore_data_structure(
                            practice_type,
                            item['practice_date'],
                            inputs,
                            item['feedback'],
                            scores,
                            item['duration_seconds'],
                            item['duration_display']
                        )
                        
                        # 練習タイプ別に分類して追加
                        if practice_type not in history_by_type:
                            history_by_type[practice_type] = []
                        history_by_type[practice_type].append(converted_item)
                        
                    except Exception as e:
                        logger.error(f"Failed to convert database record: {e}")
                        continue
                
                logger.info(f"Successfully batch loaded {len(result.data)} records for {len(history_by_type)} practice types")
                return history_by_type
            else:
                return history_by_type if practice_types else {}
                
        except Exception as e:
            logger.error(f"Error batch loading practice history from database: {e}")
            return self._load_batch_from_session_state(practice_types, limit)

    def _load_batch_from_session_state(self, practice_types: Optional[List[str]] = None, limit: int = 1000) -> Dict[str, List[Dict[str, Any]]]:
        """フォールバック: セッション状態から一括読み込み"""
        if 'offline_history' not in st.session_state:
            return {} if not practice_types else {pt: [] for pt in practice_types}
        
        history = st.session_state.offline_history
        history_by_type = {}
        
        if practice_types:
            for practice_type in practice_types:
                history_by_type[practice_type] = [
                    item for item in history 
                    if item.get('type') == practice_type
                ][:limit]
        else:
            # 全てを練習タイプ別に分類
            for item in history:
                practice_type = item.get('type', '不明')
                if practice_type not in history_by_type:
                    history_by_type[practice_type] = []
                history_by_type[practice_type].append(item)
        
        return history_by_type

    def _load_from_session_state(self, practice_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """フォールバック: セッション状態から読み込み"""
        if 'offline_history' not in st.session_state:
            return []
        
        history = st.session_state.offline_history
        
        if practice_type:
            history = [item for item in history if item.get('type') == practice_type]
        
        return history[:limit]

    def has_scoring_errors(self, practice_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        採点エラーが発生した履歴を特定します。
        
        Args:
            practice_type: 特定の練習タイプに絞る場合は指定
            
        Returns:
            エラーが発生した履歴のリスト
        """
        try:
            history = self.load_practice_history(practice_type, limit=200)
            error_history = []
            
            for item in history:
                feedback = item.get('feedback', '')
                scores = item.get('scores', {})
                
                # エラーの兆候をチェック
                has_error = (
                    # フィードバックにエラーメッセージが含まれている
                    'システムエラー' in feedback or
                    '503 UNAVAILABLE' in feedback or
                    'UNAVAILABLE' in feedback or
                    'overloaded' in feedback or
                    # スコアが空または無効
                    not scores or
                    (isinstance(scores, dict) and len(scores) == 0) or
                    # フィードバックが短すぎる（エラーメッセージの可能性）
                    (feedback and len(feedback.strip()) < 100 and 'エラー' in feedback)
                )
                
                if has_error:
                    # 再採点に必要な情報があるかチェック
                    inputs = item.get('inputs', {})
                    if inputs and isinstance(inputs, dict):
                        error_history.append({
                            'record_id': item.get('id'),  # データベースのレコードID（もしあれば）
                            'practice_type': item.get('type'),
                            'date': item.get('date'),
                            'inputs': inputs,
                            'error_feedback': feedback,
                            'original_item': item
                        })
            
            logger.info(f"Found {len(error_history)} records with scoring errors")
            return error_history
            
        except Exception as e:
            logger.error(f"Error checking for scoring errors: {e}")
            return []
    
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

    def analyze_practice_types(self) -> Dict[str, Any]:
        """
        データベースに実際に保存されている練習タイプを分析し、
        統計情報と分類結果を返します。
        """
        if not self.is_available():
            logger.warning("Database not available. Cannot analyze practice types.")
            return {"error": "Database not available"}
        
        try:
            session_id = self.get_session_id()
            
            # 全ての練習タイプと件数を取得
            result = self.client.table('practice_history').select('practice_type').eq('session_id', session_id).execute()
            
            if not result.data:
                return {"total_records": 0, "practice_types": {}, "categories": {}}
            
            # 練習タイプ別の集計
            type_counts = {}
            for record in result.data:
                practice_type = record['practice_type']
                type_counts[practice_type] = type_counts.get(practice_type, 0) + 1
            
            # カテゴリ別の集計
            category_analysis = {}
            unrecognized_types = []
            
            for practice_type, count in type_counts.items():
                category, subcategory = self.practice_type_manager.get_category_for_type(practice_type)
                
                if category == "その他":
                    unrecognized_types.append(practice_type)
                
                if category not in category_analysis:
                    category_analysis[category] = {"total": 0, "subcategories": {}}
                
                category_analysis[category]["total"] += count
                
                if subcategory not in category_analysis[category]["subcategories"]:
                    category_analysis[category]["subcategories"][subcategory] = {"total": 0, "types": {}}
                
                category_analysis[category]["subcategories"][subcategory]["total"] += count
                category_analysis[category]["subcategories"][subcategory]["types"][practice_type] = count
            
            analysis_result = {
                "total_records": len(result.data),
                "unique_practice_types": len(type_counts),
                "practice_types": type_counts,
                "categories": category_analysis,
                "unrecognized_types": unrecognized_types,
                "display_names": {
                    practice_type: self.practice_type_manager.get_display_name(practice_type)
                    for practice_type in type_counts.keys()
                }
            }
            
            logger.info(f"Practice type analysis completed: {analysis_result['unique_practice_types']} unique types found")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing practice types: {e}")
            return {"error": str(e)}

    def get_all_unique_practice_types(self) -> List[str]:
        """
        データベースに存在する全ての一意な練習タイプを取得します。
        動的に練習タイプリストを生成する際に使用します。
        """
        if not self.is_available():
            return []
        
        try:
            session_id = self.get_session_id()
            
            # SQLで一意な練習タイプを取得
            result = self.client.table('practice_history')\
                .select('practice_type')\
                .eq('session_id', session_id)\
                .execute()
            
            if result.data:
                unique_types = list(set(record['practice_type'] for record in result.data))
                logger.info(f"Found {len(unique_types)} unique practice types in database")
                return sorted(unique_types)
            else:
                return []
                
        except Exception as e:
            logger.error(f"Error getting unique practice types: {e}")
            return []

# グローバルインスタンス
db_manager = DatabaseManager() 