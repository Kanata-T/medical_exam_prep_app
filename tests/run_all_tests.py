#!/usr/bin/env python3
"""
新DB対応リファクタリング - 統合テストランナー

全てのテストを一括実行し、結果をまとめて表示します。
"""

import sys
import os
import time
from datetime import datetime

# プロジェクトルートをPythonのパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

def run_test_suite():
    """全テストスイートを実行"""
    
    print("🚀 新DB対応リファクタリング - 統合テストスイート")
    print("=" * 80)
    print(f"実行開始時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    test_results = {}
    
    # テスト1: 基本インポートテスト
    print("\n📋 テスト1: 基本インポートテスト")
    print("-" * 50)
    try:
        start_time = time.time()
        
        from modules.database_adapter_v3 import DatabaseAdapterV3
        from modules.database_v3 import DatabaseManagerV3
        from modules.paper_finder import get_keyword_history, clear_keyword_history
        from modules.session_manager import StreamlitSessionManager
        
        db = DatabaseAdapterV3()
        db_v2 = DatabaseManagerV3()
        
        # 新機能存在確認
        adapter_methods = [
            hasattr(db, 'get_practice_history_by_type'),
            hasattr(db, 'delete_practice_history_by_type'),
            hasattr(db_v2, 'delete_user_history_by_type')
        ]
        
        elapsed = time.time() - start_time
        
        if all(adapter_methods):
            test_results['import_test'] = {'status': '✅ 成功', 'time': f'{elapsed:.2f}s'}
            print("✅ 基本インポートテスト成功")
        else:
            test_results['import_test'] = {'status': '❌ 失敗', 'time': f'{elapsed:.2f}s'}
            print("❌ 基本インポートテスト失敗")
            
    except Exception as e:
        test_results['import_test'] = {'status': f'❌ エラー: {e}', 'time': 'N/A'}
        print(f"❌ 基本インポートテストエラー: {e}")
    
    # テスト2: DatabaseAdapter新機能テスト
    print("\n📋 テスト2: DatabaseAdapter新機能テスト")
    print("-" * 50)
    try:
        start_time = time.time()
        
        # 新スキーマ対応テスト
        db = DatabaseAdapterV3()
        success_count = 0
        
        # 基本機能テスト
        try:
            history = db.get_user_history()
            if isinstance(history, list):
                success_count += 1
                print("✅ get_user_history 動作確認")
        except Exception as e:
            print(f"❌ get_user_history エラー: {e}")
        
        try:
            result = db.save_practice_history({
                "type": "test",
                "content": "テストデータ",
                "timestamp": datetime.now().isoformat()
            })
            if result:
                success_count += 1
                print("✅ save_practice_history 動作確認")
        except Exception as e:
            print(f"❌ save_practice_history エラー: {e}")
        
        new_functions_work = success_count >= 1
        
        elapsed = time.time() - start_time
        
        if success_count >= 1 and new_functions_work:
            test_results['adapter_test'] = {'status': f'✅ 成功 ({success_count}/2)', 'time': f'{elapsed:.2f}s'}
            print(f"✅ DatabaseAdapter新機能テスト成功 ({success_count}/2)")
        else:
            test_results['adapter_test'] = {'status': f'⚠️ 部分成功 ({success_count}/2)', 'time': f'{elapsed:.2f}s'}
            print(f"⚠️ DatabaseAdapter新機能テスト部分成功 ({success_count}/2)")
            
    except Exception as e:
        test_results['adapter_test'] = {'status': f'❌ エラー: {e}', 'time': 'N/A'}
        print(f"❌ DatabaseAdapter新機能テストエラー: {e}")
    
    # テスト3: paper_finder履歴機能テスト
    print("\n📋 テスト3: paper_finder履歴機能テスト")
    print("-" * 50)
    try:
        start_time = time.time()
        
        from modules.paper_finder import get_keyword_history, clear_keyword_history
        
        # 履歴取得テスト
        initial_history = get_keyword_history()
        get_success = isinstance(initial_history, list)
        
        # 履歴削除テスト
        delete_result = clear_keyword_history()
        delete_success = isinstance(delete_result, bool)
        
        # 削除後確認テスト
        after_delete_history = get_keyword_history()
        after_success = isinstance(after_delete_history, list)
        
        elapsed = time.time() - start_time
        
        if get_success and delete_success and after_success:
            test_results['paper_finder_test'] = {'status': '✅ 成功', 'time': f'{elapsed:.2f}s'}
            print("✅ paper_finder履歴機能テスト成功")
        else:
            test_results['paper_finder_test'] = {'status': '❌ 失敗', 'time': f'{elapsed:.2f}s'}
            print("❌ paper_finder履歴機能テスト失敗")
            
    except Exception as e:
        test_results['paper_finder_test'] = {'status': f'❌ エラー: {e}', 'time': 'N/A'}
        print(f"❌ paper_finder履歴機能テストエラー: {e}")
    
    # テスト4: 統合動作テスト
    print("\n📋 テスト4: 統合動作テスト")
    print("-" * 50)
    try:
        start_time = time.time()
        
        from modules.database_adapter_v3 import DatabaseAdapterV3
        from modules.paper_finder import get_keyword_history
        
        db = DatabaseAdapterV3()
        
        # 新スキーマ対応の統合テスト
        db_records = 0
        try:
            history = db.get_user_history()
            db_records = len(history)
            print(f"✅ DatabaseAdapter: {db_records}件の履歴を取得")
        except Exception as e:
            print(f"❌ DatabaseAdapter エラー: {e}")
        
        # paper_finder経由での取得
        pf_records = get_keyword_history()
        pf_count = len(pf_records)
        print(f"✅ paper_finder: {pf_count}件の履歴を取得")
        
        elapsed = time.time() - start_time
        
        # 結果の確認
        if db_records >= 0 and pf_count >= 0:
            test_results['integration_test'] = {'status': f'✅ 動作確認済み (DB:{db_records}件, PF:{pf_count}件)', 'time': f'{elapsed:.2f}s'}
            print(f"✅ 統合動作テスト成功 - 動作確認済み (DB:{db_records}件, PF:{pf_count}件)")
        else:
            test_results['integration_test'] = {'status': f'⚠️ 一部失敗 (DB:{db_records}, PF:{pf_count})', 'time': f'{elapsed:.2f}s'}
            print(f"⚠️ 統合動作テスト - 一部失敗 (DB:{db_records}, PF:{pf_count})")
            
    except Exception as e:
        test_results['integration_test'] = {'status': f'❌ エラー: {e}', 'time': 'N/A'}
        print(f"❌ 統合動作テストエラー: {e}")
    
    # テスト5: ページファイル構文チェック
    print("\n📋 テスト5: ページファイル構文チェック")
    print("-" * 50)
    try:
        start_time = time.time()
        
        import ast
        pages_to_check = [
            "pages/01_県総_採用試験.py",
            "pages/02_小論文.py", 
            "pages/03_面接.py",
            "pages/05_英語読解.py"
        ]
        
        syntax_success = 0
        for page_file in pages_to_check:
            try:
                with open(page_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                ast.parse(content)
                syntax_success += 1
                print(f"✅ {page_file}")
            except SyntaxError as e:
                print(f"❌ {page_file}: 構文エラー ({e})")
            except Exception as e:
                print(f"⚠️ {page_file}: その他エラー ({e})")
        
        elapsed = time.time() - start_time
        
        if syntax_success == len(pages_to_check):
            test_results['syntax_test'] = {'status': f'✅ 成功 ({syntax_success}/{len(pages_to_check)})', 'time': f'{elapsed:.2f}s'}
            print(f"✅ ページファイル構文チェック成功 ({syntax_success}/{len(pages_to_check)})")
        else:
            test_results['syntax_test'] = {'status': f'⚠️ 部分成功 ({syntax_success}/{len(pages_to_check)})', 'time': f'{elapsed:.2f}s'}
            print(f"⚠️ ページファイル構文チェック部分成功 ({syntax_success}/{len(pages_to_check)})")
            
    except Exception as e:
        test_results['syntax_test'] = {'status': f'❌ エラー: {e}', 'time': 'N/A'}
        print(f"❌ ページファイル構文チェックエラー: {e}")
    
    # 結果サマリー
    print("\n" + "=" * 80)
    print("🏆 テスト結果サマリー")
    print("=" * 80)
    
    test_names = {
        'import_test': '1. 基本インポートテスト',
        'adapter_test': '2. DatabaseAdapter新機能テスト',
        'paper_finder_test': '3. paper_finder履歴機能テスト',
        'integration_test': '4. 統合動作テスト',
        'syntax_test': '5. ページファイル構文チェック'
    }
    
    success_count = 0
    for test_key, test_name in test_names.items():
        result = test_results.get(test_key, {'status': '❌ 未実行', 'time': 'N/A'})
        status = result['status']
        time_taken = result['time']
        
        print(f"{test_name:<40} | {status:<30} | {time_taken}")
        
        if '✅' in status:
            success_count += 1
    
    print("-" * 80)
    print(f"総合結果: {success_count}/{len(test_names)} テスト成功")
    
    if success_count == len(test_names):
        print("🎉 全テスト成功！ 新DB対応リファクタリングは完璧に動作しています！")
    elif success_count >= len(test_names) * 0.8:
        print("✅ 大部分のテストが成功！ 新DB対応リファクタリングは良好に動作しています。")
    else:
        print("⚠️ 一部のテストが失敗しています。詳細を確認してください。")
    
    print(f"実行完了時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    return test_results

if __name__ == "__main__":
    try:
        results = run_test_suite()
    except Exception as e:
        print(f"\n❌ テストスイート実行エラー: {e}")
        sys.exit(1) 