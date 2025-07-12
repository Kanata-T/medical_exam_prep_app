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
        
        from modules.database_adapter import DatabaseAdapter
        from modules.database_v2 import DatabaseManagerV2
        from modules.paper_finder import get_keyword_history, clear_keyword_history
        from modules.session_manager import StreamlitSessionManager
        
        db = DatabaseAdapter()
        db_v2 = DatabaseManagerV2()
        
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
        
        # 練習タイプマッピングテスト
        expected_types = [
            "keyword_generation_paper", "keyword_generation_freeform", "keyword_generation_general",
            "paper_search", "medical_exam_comprehensive", "medical_exam_letter_style",
            "medical_exam_comment_style", "essay_practice", "interview_practice_general",
            "interview_practice_single", "interview_practice_session", "english_reading_standard",
            "english_reading_letter_style", "english_reading_comment_style", "free_writing"
        ]
        
        db = DatabaseAdapter()
        success_count = 0
        
        for practice_type in expected_types:
            try:
                result = db._get_practice_type_id_by_new_key(practice_type)
                if result and isinstance(result, int) and result > 0:
                    success_count += 1
            except:
                pass
        
        # 新機能動作テスト
        try:
            db.get_practice_history_by_type("keyword_generation_paper", limit=5)
            db.delete_practice_history_by_type("keyword_generation_paper")
            new_functions_work = True
        except:
            new_functions_work = False
        
        elapsed = time.time() - start_time
        
        if success_count == len(expected_types) and new_functions_work:
            test_results['adapter_test'] = {'status': f'✅ 成功 ({success_count}/{len(expected_types)})', 'time': f'{elapsed:.2f}s'}
            print(f"✅ DatabaseAdapter新機能テスト成功 ({success_count}/{len(expected_types)})")
        else:
            test_results['adapter_test'] = {'status': f'⚠️ 部分成功 ({success_count}/{len(expected_types)})', 'time': f'{elapsed:.2f}s'}
            print(f"⚠️ DatabaseAdapter新機能テスト部分成功 ({success_count}/{len(expected_types)})")
            
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
        
        from modules.database_adapter import DatabaseAdapter
        from modules.paper_finder import get_keyword_history
        
        db = DatabaseAdapter()
        
        # DatabaseAdapter経由での取得
        db_records = 0
        keyword_types = ["keyword_generation_paper", "keyword_generation_freeform", "keyword_generation_general"]
        for practice_type in keyword_types:
            try:
                records = db.get_practice_history_by_type(practice_type, limit=10)
                db_records += len(records)
            except:
                pass
        
        # paper_finder経由での取得
        pf_records = get_keyword_history()
        pf_count = len(pf_records)
        
        elapsed = time.time() - start_time
        
        # 結果の一致性確認
        if db_records == pf_count:
            test_results['integration_test'] = {'status': f'✅ 一致 ({db_records}件)', 'time': f'{elapsed:.2f}s'}
            print(f"✅ 統合動作テスト成功 - データ一致 ({db_records}件)")
        else:
            test_results['integration_test'] = {'status': f'⚠️ 不一致 (DB:{db_records}, PF:{pf_count})', 'time': f'{elapsed:.2f}s'}
            print(f"⚠️ 統合動作テスト - データ不一致 (DB:{db_records}, PF:{pf_count})")
            
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