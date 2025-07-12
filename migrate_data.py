#!/usr/bin/env python3
"""
データ移行スクリプト

既存のpractice_historyテーブルから新しい正規化されたスキーマへデータを移行します。
Supabaseでのスキーマ作成後に実行してください。

実行方法:
    python migrate_data.py

注意：
- 移行前に必ずデータベースのバックアップを取ってください
- 本番環境での実行前にテスト環境で十分検証してください
"""

import os
import sys
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
import hashlib

# Supabaseクライアントをインポート
try:
    from supabase import create_client, Client
except ImportError:
    print("ERROR: supabaseライブラリがインストールされていません。")
    print("実行してください: pip install supabase")
    sys.exit(1)

# 新しいデータベースシステムをインポート
try:
    from modules.database_v2 import DatabaseManagerV2
    from modules.session_manager import StreamlitSessionManager
except ImportError as e:
    print(f"ERROR: 新しいデータベースシステムをインポートできません: {e}")
    print("modules/database_v2.py と modules/session_manager.py が存在することを確認してください。")
    sys.exit(1)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DataMigrator:
    """データ移行クラス"""
    
    def __init__(self):
        """初期化"""
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "SUPABASE_URLとSUPABASE_SERVICE_ROLE_KEY（またはSUPABASE_ANON_KEY）環境変数を設定してください"
            )
        
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        self.db_manager = DatabaseManagerV2()
        
        # 統計情報
        self.stats = {
            'total_records': 0,
            'migrated_records': 0,
            'skipped_records': 0,
            'error_records': 0,
            'users_created': 0,
            'sessions_created': 0,
            'practice_types_created': 0
        }
        
        # 練習タイプマッピング（旧→新）
        self.practice_type_mapping = {
            "採用試験": "medical_exam_comprehensive",
            "過去問スタイル採用試験 - Letter形式（翻訳 + 意見）": "medical_exam_letter_style",
            "過去問スタイル採用試験 - 論文コメント形式（コメント翻訳 + 意見）": "medical_exam_comment_style",
            "小論文対策": "essay_practice",
            "面接対策": "interview_practice_general",
            "面接対策(単発)": "interview_practice_single",
            "面接対策(セッション)": "interview_practice_session",
            "医学部採用試験 自由記述": "medical_knowledge_check",
            "英語読解": "english_reading_standard",
            "過去問スタイル英語読解 - Letter形式（翻訳 + 意見）": "english_reading_letter_style",
            "過去問スタイル英語読解 - 論文コメント形式（コメント翻訳 + 意見）": "english_reading_comment_style"
        }
    
    def validate_environment(self) -> bool:
        """環境の検証"""
        logger.info("環境を検証中...")
        
        try:
            # Supabase接続テスト
            result = self.supabase.table('users').select('count', count='exact').execute()
            logger.info(f"Supabase接続成功")
            
            # 新しいテーブルの存在確認
            required_tables = ['users', 'practice_categories', 'practice_types', 
                             'practice_sessions', 'practice_inputs', 'practice_scores', 'practice_feedback']
            
            for table in required_tables:
                try:
                    self.supabase.table(table).select('count', count='exact').execute()
                    logger.info(f"✓ テーブル '{table}' 存在確認")
                except Exception as e:
                    logger.error(f"✗ テーブル '{table}' が見つかりません: {e}")
                    return False
            
            # 旧テーブルの存在確認
            try:
                result = self.supabase.table('practice_history').select('count', count='exact').execute()
                old_count = result.count
                logger.info(f"✓ 旧テーブル 'practice_history' に {old_count} 件のレコードが存在")
                self.stats['total_records'] = old_count
            except Exception as e:
                logger.warning(f"⚠ 旧テーブル 'practice_history' が見つかりません: {e}")
                logger.info("新規インストールの可能性があります。")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"環境検証エラー: {e}")
            return False
    
    def create_default_user(self) -> str:
        """デフォルトユーザーを作成"""
        try:
            default_user_id = "legacy_user_001"
            
            # 既存確認
            existing = self.supabase.table('users').select('*').eq('id', default_user_id).execute()
            if existing.data:
                logger.info(f"デフォルトユーザー '{default_user_id}' は既に存在します")
                return default_user_id
            
            # 作成
            user_data = {
                'id': default_user_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_active_at': datetime.now(timezone.utc).isoformat(),
                'session_method': 'legacy_migration',
                'metadata': {
                    'migration_source': 'old_practice_history',
                    'migration_date': datetime.now(timezone.utc).isoformat()
                }
            }
            
            result = self.supabase.table('users').insert(user_data).execute()
            logger.info(f"デフォルトユーザー '{default_user_id}' を作成しました")
            self.stats['users_created'] += 1
            
            return default_user_id
            
        except Exception as e:
            logger.error(f"デフォルトユーザー作成エラー: {e}")
            raise
    
    def ensure_practice_types(self) -> Dict[str, str]:
        """練習タイプの存在確認・作成"""
        logger.info("練習タイプを確認・作成中...")
        
        type_mapping = {}
        
        for old_type, new_type_key in self.practice_type_mapping.items():
            try:
                # 既存確認
                existing = self.supabase.table('practice_types').select('*').eq('type_key', new_type_key).execute()
                
                if existing.data:
                    type_mapping[old_type] = existing.data[0]['id']
                    logger.debug(f"練習タイプ '{new_type_key}' は既に存在します")
                    continue
                
                # カテゴリ判定
                category_id = self._get_category_for_type(new_type_key)
                
                # 新規作成
                type_data = {
                    'type_key': new_type_key,
                    'display_name': old_type,
                    'category_id': category_id,
                    'description': f"Migrated from: {old_type}",
                    'is_active': True,
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                
                result = self.supabase.table('practice_types').insert(type_data).execute()
                type_mapping[old_type] = result.data[0]['id']
                
                logger.info(f"練習タイプ '{new_type_key}' ('{old_type}') を作成しました")
                self.stats['practice_types_created'] += 1
                
            except Exception as e:
                logger.error(f"練習タイプ '{old_type}' の処理エラー: {e}")
                # デフォルトタイプを使用
                type_mapping[old_type] = self._get_default_practice_type_id()
        
        return type_mapping
    
    def _get_category_for_type(self, type_key: str) -> str:
        """練習タイプに対応するカテゴリIDを取得"""
        category_mapping = {
            'medical_exam_': 'comprehensive_exam',
            'essay_': 'essay_writing', 
            'interview_': 'interview_prep',
            'medical_knowledge_': 'knowledge_check',
            'english_reading_': 'english_reading'
        }
        
        for prefix, category_key in category_mapping.items():
            if type_key.startswith(prefix):
                # カテゴリIDを取得
                result = self.supabase.table('practice_categories').select('id').eq('category_key', category_key).execute()
                if result.data:
                    return result.data[0]['id']
        
        # デフォルトカテゴリ
        result = self.supabase.table('practice_categories').select('id').eq('category_key', 'comprehensive_exam').execute()
        return result.data[0]['id'] if result.data else "00000000-0000-0000-0000-000000000001"
    
    def _get_default_practice_type_id(self) -> str:
        """デフォルト練習タイプIDを取得"""
        result = self.supabase.table('practice_types').select('id').eq('type_key', 'medical_exam_comprehensive').execute()
        return result.data[0]['id'] if result.data else "00000000-0000-0000-0000-000000000001"
    
    def migrate_records(self, user_id: str, type_mapping: Dict[str, str]) -> bool:
        """レコードの移行"""
        logger.info("データレコードの移行を開始...")
        
        try:
            # 旧データを取得（バッチ処理）
            batch_size = 100
            offset = 0
            
            while True:
                logger.info(f"バッチ処理中: offset={offset}, size={batch_size}")
                
                result = self.supabase.table('practice_history')\
                    .select('*')\
                    .range(offset, offset + batch_size - 1)\
                    .order('created_at', desc=False)\
                    .execute()
                
                if not result.data:
                    break
                
                # バッチ内の各レコードを処理
                for record in result.data:
                    try:
                        self._migrate_single_record(record, user_id, type_mapping)
                        self.stats['migrated_records'] += 1
                    except Exception as e:
                        logger.error(f"レコード移行エラー (ID: {record.get('id', 'unknown')}): {e}")
                        self.stats['error_records'] += 1
                
                offset += batch_size
                
                # 進捗表示
                if offset % 500 == 0:
                    logger.info(f"進捗: {offset} / {self.stats['total_records']} レコード処理完了")
            
            logger.info("データ移行が完了しました")
            return True
            
        except Exception as e:
            logger.error(f"データ移行エラー: {e}")
            return False
    
    def _migrate_single_record(self, record: Dict[str, Any], user_id: str, type_mapping: Dict[str, str]):
        """単一レコードの移行"""
        practice_type = record.get('practice_type', 'unknown')
        
        # 練習タイプIDの取得
        practice_type_id = type_mapping.get(practice_type)
        if not practice_type_id:
            logger.warning(f"未知の練習タイプ: {practice_type}, デフォルトを使用")
            practice_type_id = self._get_default_practice_type_id()
        
        # セッション作成
        session_id = self._create_practice_session(record, user_id, practice_type_id)
        
        # 入力データの移行
        if record.get('inputs'):
            self._migrate_inputs(session_id, record['inputs'])
        
        # スコアデータの移行
        if record.get('scores'):
            self._migrate_scores(session_id, record['scores'])
        
        # フィードバックの移行
        if record.get('feedback'):
            self._migrate_feedback(session_id, record['feedback'])
    
    def _create_practice_session(self, record: Dict[str, Any], user_id: str, practice_type_id: str) -> str:
        """練習セッションの作成"""
        session_data = {
            'user_id': user_id,
            'practice_type_id': practice_type_id,
            'started_at': record.get('date', datetime.now(timezone.utc).isoformat()),
            'completed_at': record.get('date', datetime.now(timezone.utc).isoformat()),
            'duration_seconds': record.get('duration_seconds', 0),
            'metadata': {
                'migrated_from': 'practice_history',
                'original_id': record.get('id'),
                'migration_timestamp': datetime.now(timezone.utc).isoformat()
            }
        }
        
        result = self.supabase.table('practice_sessions').insert(session_data).execute()
        self.stats['sessions_created'] += 1
        
        return result.data[0]['id']
    
    def _migrate_inputs(self, session_id: str, inputs: Dict[str, Any]):
        """入力データの移行"""
        for field_name, field_value in inputs.items():
            if field_value and str(field_value).strip():
                input_data = {
                    'session_id': session_id,
                    'field_name': field_name,
                    'field_value': str(field_value),
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                
                self.supabase.table('practice_inputs').insert(input_data).execute()
    
    def _migrate_scores(self, session_id: str, scores: Dict[str, Any]):
        """スコアデータの移行"""
        for score_category, score_value in scores.items():
            try:
                score_data = {
                    'session_id': session_id,
                    'score_category': score_category,
                    'score_value': float(score_value) if score_value is not None else 0.0,
                    'max_score': 10.0,  # デフォルトの最大スコア
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
                
                self.supabase.table('practice_scores').insert(score_data).execute()
                
            except (ValueError, TypeError) as e:
                logger.warning(f"スコア変換エラー: {score_category}={score_value}, エラー: {e}")
    
    def _migrate_feedback(self, session_id: str, feedback: str):
        """フィードバックの移行"""
        feedback_data = {
            'session_id': session_id,
            'feedback_text': feedback,
            'feedback_type': 'ai_generated',
            'created_at': datetime.now(timezone.utc).isoformat()
        }
        
        self.supabase.table('practice_feedback').insert(feedback_data).execute()
    
    def generate_migration_report(self) -> str:
        """移行レポートの生成"""
        report = f"""
データ移行レポート
=================
実行日時: {datetime.now().isoformat()}

移行統計:
- 総レコード数: {self.stats['total_records']}
- 移行成功: {self.stats['migrated_records']}
- スキップ: {self.stats['skipped_records']}
- エラー: {self.stats['error_records']}
- 作成されたユーザー: {self.stats['users_created']}
- 作成されたセッション: {self.stats['sessions_created']}
- 作成された練習タイプ: {self.stats['practice_types_created']}

成功率: {(self.stats['migrated_records'] / max(self.stats['total_records'], 1) * 100):.2f}%

練習タイプマッピング:
"""
        for old_type, new_type in self.practice_type_mapping.items():
            report += f"- {old_type} -> {new_type}\n"
        
        return report
    
    def run_migration(self) -> bool:
        """メイン移行処理"""
        logger.info("データ移行を開始します...")
        
        try:
            # 環境検証
            if not self.validate_environment():
                logger.error("環境検証に失敗しました")
                return False
            
            # デフォルトユーザー作成
            user_id = self.create_default_user()
            
            # 練習タイプの確認・作成
            type_mapping = self.ensure_practice_types()
            
            # データ移行
            if not self.migrate_records(user_id, type_mapping):
                logger.error("データ移行に失敗しました")
                return False
            
            # レポート生成
            report = self.generate_migration_report()
            logger.info(report)
            
            # レポートをファイルに保存
            with open('migration_report.txt', 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info("移行が正常に完了しました")
            return True
            
        except Exception as e:
            logger.error(f"移行処理中に予期しないエラーが発生しました: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

def main():
    """メイン関数"""
    print("=" * 50)
    print("Supabase データ移行スクリプト")
    print("=" * 50)
    
    # 確認プロンプト
    response = input("データ移行を実行しますか？ (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("移行をキャンセルしました")
        return
    
    print("\n⚠️  重要な注意事項:")
    print("1. 移行前にデータベースのバックアップを取得してください")
    print("2. SUPABASE_URLとSUPABASE_SERVICE_ROLE_KEY環境変数が設定されていることを確認してください")
    print("3. 新しいスキーマがSupabaseに作成済みであることを確認してください")
    
    response = input("\n上記を確認し、移行を続行しますか？ (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("移行をキャンセルしました")
        return
    
    try:
        migrator = DataMigrator()
        success = migrator.run_migration()
        
        if success:
            print("\n✅ データ移行が正常に完了しました！")
            print("📄 詳細なレポートは migration_report.txt に保存されました")
            print("📋 ログは migration.log に保存されました")
        else:
            print("\n❌ データ移行に失敗しました")
            print("📋 詳細はログファイル migration.log を確認してください")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 移行処理中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 