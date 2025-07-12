#!/usr/bin/env python3
"""
移行後テストスクリプト

データ移行完了後のシステム動作を包括的にテストします。

実行方法:
    python test_migration.py

このスクリプトは以下をテストします：
1. データベース接続とスキーマの整合性
2. セッション管理システム
3. 新しいDatabaseManagerV2の基本機能
4. DatabaseAdapterの互換性
5. 履歴データの読み込みと表示
6. 新しいデータの保存機能
"""

import os
import sys
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# テスト結果の格納
test_results = {
    'passed': 0,
    'failed': 0,
    'errors': [],
    'warnings': []
}

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_test_result(test_name: str, success: bool, message: str = ""):
    """テスト結果をログに記録"""
    if success:
        test_results['passed'] += 1
        logger.info(f"✅ {test_name}: PASS {message}")
    else:
        test_results['failed'] += 1
        test_results['errors'].append(f"{test_name}: {message}")
        logger.error(f"❌ {test_name}: FAIL {message}")

def log_warning(message: str):
    """警告をログに記録"""
    test_results['warnings'].append(message)
    logger.warning(f"⚠️  {message}")

class MigrationTester:
    """移行テストクラス"""
    
    def __init__(self):
        """初期化"""
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        
        # モジュールの動的インポート
        self.db_manager_v2 = None
        self.db_adapter = None
        self.session_manager = None
        self.supabase = None
    
    def setup_connections(self) -> bool:
        """接続の設定"""
        try:
            # Supabase接続
            if self.supabase_url and self.supabase_key:
                from supabase import create_client
                self.supabase = create_client(self.supabase_url, self.supabase_key)
                log_test_result("Supabase接続", True)
            else:
                log_warning("Supabase環境変数が設定されていません。データベーステストはスキップされます。")
                return False
            
            # 新しいデータベースシステム
            from modules.database_v2 import DatabaseManagerV2
            from modules.database_adapter import DatabaseAdapter
            from modules.session_manager import StreamlitSessionManager
            
            self.session_manager = StreamlitSessionManager()
            self.db_manager_v2 = DatabaseManagerV2()
            self.db_adapter = DatabaseAdapter()
            
            log_test_result("モジュールインポート", True)
            return True
            
        except ImportError as e:
            log_test_result("モジュールインポート", False, f"インポートエラー: {e}")
            return False
        except Exception as e:
            log_test_result("接続設定", False, f"設定エラー: {e}")
            return False
    
    def test_database_schema(self) -> bool:
        """データベーススキーマのテスト"""
        if not self.supabase:
            log_warning("Supabase接続なし - スキーマテストをスキップ")
            return True
        
        try:
            required_tables = [
                'users', 'practice_categories', 'practice_types',
                'practice_sessions', 'practice_inputs', 'practice_scores', 'practice_feedback'
            ]
            
            for table in required_tables:
                try:
                    result = self.supabase.table(table).select('count', count='exact').execute()
                    log_test_result(f"テーブル存在確認: {table}", True, f"レコード数: {result.count}")
                except Exception as e:
                    log_test_result(f"テーブル存在確認: {table}", False, str(e))
                    return False
            
            return True
            
        except Exception as e:
            log_test_result("スキーマテスト", False, f"スキーマエラー: {e}")
            return False
    
    def test_session_management(self) -> bool:
        """セッション管理のテスト"""
        try:
            if not self.session_manager:
                log_test_result("セッション管理テスト", False, "SessionManagerが初期化されていません")
                return False
            
            # 基本的なセッション機能のテスト
            # 注意: Streamlitコンテキスト外なので、一部の機能はテストできません
            
            # セッション状態の取得テスト
            try:
                status = self.session_manager.get_session_status()
                log_test_result("セッション状態取得", True, f"メソッド: {status.get('method', 'unknown')}")
            except Exception as e:
                log_test_result("セッション状態取得", False, str(e))
                return False
            
            return True
            
        except Exception as e:
            log_test_result("セッション管理テスト", False, f"セッションエラー: {e}")
            return False
    
    def test_database_manager_v2(self) -> bool:
        """DatabaseManagerV2のテスト"""
        try:
            if not self.db_manager_v2:
                log_test_result("DatabaseManagerV2テスト", False, "DatabaseManagerV2が初期化されていません")
                return False
            
            # 基本的な接続テスト
            try:
                # UserManagerのテスト
                user_manager = self.db_manager_v2.user_manager
                log_test_result("UserManager初期化", True)
                
                # SessionManagerのテスト
                session_manager = self.db_manager_v2.session_manager
                log_test_result("SessionManager初期化", True)
                
                # HistoryManagerのテスト
                history_manager = self.db_manager_v2.history_manager
                log_test_result("HistoryManager初期化", True)
                
                # AnalyticsManagerのテスト
                analytics_manager = self.db_manager_v2.analytics_manager
                log_test_result("AnalyticsManager初期化", True)
                
            except Exception as e:
                log_test_result("DatabaseManagerV2サブマネージャー", False, str(e))
                return False
            
            return True
            
        except Exception as e:
            log_test_result("DatabaseManagerV2テスト", False, f"DatabaseManagerV2エラー: {e}")
            return False
    
    def test_database_adapter(self) -> bool:
        """DatabaseAdapterのテスト"""
        try:
            if not self.db_adapter:
                log_test_result("DatabaseAdapterテスト", False, "DatabaseAdapterが初期化されていません")
                return False
            
            # 接続テスト
            try:
                test_result = self.db_adapter.test_connection()
                if test_result.get("success"):
                    log_test_result("DatabaseAdapter接続テスト", True, f"レコード数: {test_result.get('record_count', 'N/A')}")
                else:
                    log_test_result("DatabaseAdapter接続テスト", False, test_result.get("error", "不明なエラー"))
                    return False
            except Exception as e:
                log_test_result("DatabaseAdapter接続テスト", False, str(e))
                return False
            
            # 基本機能のテスト
            try:
                # 履歴取得テスト
                history = self.db_adapter.get_user_history()
                log_test_result("履歴取得テスト", True, f"取得件数: {len(history)}")
                
                # 分析機能テスト
                analysis = self.db_adapter.analyze_user_history()
                if "error" not in analysis:
                    log_test_result("履歴分析テスト", True, f"総セッション数: {analysis.get('total_sessions', 0)}")
                else:
                    log_test_result("履歴分析テスト", False, analysis["error"])
                
            except Exception as e:
                log_test_result("DatabaseAdapter基本機能", False, str(e))
                return False
            
            return True
            
        except Exception as e:
            log_test_result("DatabaseAdapterテスト", False, f"DatabaseAdapterエラー: {e}")
            return False
    
    def test_data_migration_integrity(self) -> bool:
        """データ移行の整合性テスト"""
        if not self.supabase:
            log_warning("Supabase接続なし - 移行整合性テストをスキップ")
            return True
        
        try:
            # 旧テーブルと新テーブルのデータ数比較
            try:
                old_result = self.supabase.table('practice_history').select('count', count='exact').execute()
                old_count = old_result.count
                log_test_result("旧テーブルデータ確認", True, f"practice_history: {old_count}件")
            except Exception:
                log_warning("旧テーブル 'practice_history' が見つかりません（新規インストールの可能性）")
                old_count = 0
            
            # 新テーブルのデータ数確認
            new_result = self.supabase.table('practice_sessions').select('count', count='exact').execute()
            new_count = new_result.count
            log_test_result("新テーブルデータ確認", True, f"practice_sessions: {new_count}件")
            
            # データ整合性の簡単なチェック
            if old_count > 0:
                if new_count >= old_count * 0.9:  # 90%以上が移行されていれば成功とみなす
                    log_test_result("データ移行整合性", True, f"移行率: {(new_count/old_count)*100:.1f}%")
                else:
                    log_test_result("データ移行整合性", False, f"移行が不完全: {new_count}/{old_count}")
                    return False
            else:
                log_test_result("データ移行整合性", True, "新規インストール")
            
            # 関連テーブルの整合性確認
            inputs_result = self.supabase.table('practice_inputs').select('count', count='exact').execute()
            scores_result = self.supabase.table('practice_scores').select('count', count='exact').execute()
            feedback_result = self.supabase.table('practice_feedback').select('count', count='exact').execute()
            
            log_test_result("関連データ確認", True, 
                          f"inputs: {inputs_result.count}, scores: {scores_result.count}, feedback: {feedback_result.count}")
            
            return True
            
        except Exception as e:
            log_test_result("データ移行整合性テスト", False, f"整合性エラー: {e}")
            return False
    
    def test_new_data_saving(self) -> bool:
        """新しいデータ保存のテスト"""
        try:
            # テスト用のデータを作成
            test_data = {
                "type": "テスト練習",
                "date": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": 120,
                "inputs": {
                    "test_field": "テストデータ"
                },
                "scores": {
                    "テストスコア": 8
                },
                "feedback": "これはテスト用のフィードバックです。"
            }
            
            # DatabaseAdapterでの保存テスト
            if self.db_adapter:
                try:
                    success = self.db_adapter.save_practice_history(test_data)
                    if success:
                        log_test_result("新データ保存テスト", True, "DatabaseAdapterでの保存成功")
                    else:
                        log_test_result("新データ保存テスト", False, "DatabaseAdapterでの保存失敗")
                        return False
                except Exception as e:
                    log_test_result("新データ保存テスト", False, f"保存エラー: {e}")
                    return False
            else:
                log_warning("DatabaseAdapterが利用できないため、新データ保存テストをスキップ")
            
            return True
            
        except Exception as e:
            log_test_result("新データ保存テスト", False, f"保存テストエラー: {e}")
            return False
    
    def test_utility_functions(self) -> bool:
        """ユーティリティ関数のテスト"""
        try:
            # modules.utilsの動作テスト
            from modules.utils import save_history, load_history
            
            # テストデータでの保存・読み込みテスト
            test_data = {
                "type": "ユーティリティテスト",
                "date": datetime.now(timezone.utc).isoformat(),
                "inputs": {"test": "utility test"},
                "scores": {"test_score": 9},
                "feedback": "ユーティリティ関数のテスト"
            }
            
            # 保存テスト
            try:
                result = save_history(test_data)
                if result:
                    log_test_result("ユーティリティ保存テスト", True, f"戻り値: {result}")
                else:
                    log_test_result("ユーティリティ保存テスト", False, "save_historyがFalseを返しました")
                    return False
            except Exception as e:
                log_test_result("ユーティリティ保存テスト", False, f"保存エラー: {e}")
                return False
            
            # 読み込みテスト
            try:
                history = load_history()
                log_test_result("ユーティリティ読み込みテスト", True, f"取得件数: {len(history)}")
            except Exception as e:
                log_test_result("ユーティリティ読み込みテスト", False, f"読み込みエラー: {e}")
                return False
            
            return True
            
        except ImportError as e:
            log_test_result("ユーティリティ関数テスト", False, f"インポートエラー: {e}")
            return False
        except Exception as e:
            log_test_result("ユーティリティ関数テスト", False, f"ユーティリティエラー: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """全テストの実行"""
        logger.info("=" * 60)
        logger.info("移行後テストを開始します")
        logger.info("=" * 60)
        
        # 環境設定
        if not self.setup_connections():
            logger.error("接続設定に失敗しました。テストを中断します。")
            return False
        
        # 各テストの実行
        tests = [
            ("データベーススキーマテスト", self.test_database_schema),
            ("セッション管理テスト", self.test_session_management),
            ("DatabaseManagerV2テスト", self.test_database_manager_v2),
            ("DatabaseAdapterテスト", self.test_database_adapter),
            ("データ移行整合性テスト", self.test_data_migration_integrity),
            ("新データ保存テスト", self.test_new_data_saving),
            ("ユーティリティ関数テスト", self.test_utility_functions)
        ]
        
        all_passed = True
        for test_name, test_func in tests:
            logger.info(f"\n--- {test_name} ---")
            try:
                if not test_func():
                    all_passed = False
            except Exception as e:
                log_test_result(test_name, False, f"予期しないエラー: {e}")
                all_passed = False
        
        return all_passed
    
    def generate_test_report(self) -> str:
        """テストレポートの生成"""
        total_tests = test_results['passed'] + test_results['failed']
        success_rate = (test_results['passed'] / max(total_tests, 1)) * 100
        
        report = f"""
移行後テストレポート
==================
実行日時: {datetime.now().isoformat()}

テスト結果サマリー:
- 総テスト数: {total_tests}
- 成功: {test_results['passed']}
- 失敗: {test_results['failed']}
- 成功率: {success_rate:.1f}%

環境情報:
- SUPABASE_URL: {'設定済み' if self.supabase_url else '未設定'}
- SUPABASE_KEY: {'設定済み' if self.supabase_key else '未設定'}
"""
        
        if test_results['warnings']:
            report += "\n警告:\n"
            for warning in test_results['warnings']:
                report += f"- {warning}\n"
        
        if test_results['errors']:
            report += "\nエラー:\n"
            for error in test_results['errors']:
                report += f"- {error}\n"
        
        if success_rate == 100:
            report += "\n✅ 全てのテストが成功しました！移行は正常に完了しています。"
        elif success_rate >= 80:
            report += "\n⚠️  一部のテストで問題がありますが、基本的な機能は動作しています。"
        else:
            report += "\n❌ 重要な問題が検出されました。移行の見直しが必要です。"
        
        return report

def main():
    """メイン関数"""
    print("=" * 60)
    print("移行後テストスクリプト")
    print("=" * 60)
    
    try:
        tester = MigrationTester()
        
        # テストの実行
        success = tester.run_all_tests()
        
        # レポートの生成
        report = tester.generate_test_report()
        
        # 結果の表示
        logger.info("\n" + "=" * 60)
        logger.info("テスト完了")
        logger.info("=" * 60)
        print(report)
        
        # レポートをファイルに保存
        with open('test_migration_report.txt', 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info("\n📄 詳細なレポートは test_migration_report.txt に保存されました")
        logger.info("📋 ログは test_migration.log に保存されました")
        
        if success:
            logger.info("\n🎉 全てのテストが成功しました！")
            sys.exit(0)
        else:
            logger.error("\n⚠️  一部のテストで問題が発生しました")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"\n💥 テスト実行中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 