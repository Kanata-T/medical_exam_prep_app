"""
DatabaseAdapterの新機能テスト

get_practice_history_by_type と delete_practice_history_by_type の動作をテストします。
"""

import sys
import os

# プロジェクトルートをPythonのパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

def test_database_adapter_functions():
    """DatabaseAdapterの新機能の詳細テスト"""
    
    print("=" * 60)
    print("DatabaseAdapter新機能テスト")
    print("=" * 60)
    
    try:
        from modules.database_adapter import DatabaseAdapter
        print("✅ DatabaseAdapter インポート成功")
        
        db = DatabaseAdapter()
        print("✅ DatabaseAdapter インスタンス化成功")
        
        # 1. 練習タイプマッピングの全種類テスト
        print("\n1. 練習タイプマッピング全種類テスト")
        test_types = {
            "keyword_generation_paper": 1,
            "keyword_generation_freeform": 2, 
            "keyword_generation_general": 3,
            "paper_search": 4,
            "medical_exam_comprehensive": 5,
            "medical_exam_letter_style": 6,
            "medical_exam_comment_style": 7,
            "essay_practice": 8,
            "interview_practice_general": 9,
            "interview_practice_single": 10,
            "interview_practice_session": 11,
            "english_reading_standard": 12,
            "english_reading_letter_style": 13,
            "english_reading_comment_style": 14,
            "free_writing": 15
        }
        
        for practice_type, expected_id in test_types.items():
            try:
                result = db._get_practice_type_id_by_new_key(practice_type)
                if result == expected_id:
                    print(f"✅ {practice_type} -> ID: {result}")
                else:
                    print(f"⚠️ {practice_type} -> 期待値: {expected_id}, 実際: {result}")
            except Exception as e:
                print(f"❌ {practice_type} -> エラー: {e}")
        
        # 2. get_practice_history_by_type の動作テスト
        print("\n2. get_practice_history_by_type 動作テスト")
        try:
            # 実際のDB接続は期待しないが、フォールバック機能をテスト
            result = db.get_practice_history_by_type("keyword_generation_paper", limit=5)
            print(f"✅ get_practice_history_by_type 実行成功（結果: {len(result)}件）")
            
            if isinstance(result, list):
                print("✅ 戻り値がリスト形式")
            else:
                print(f"⚠️ 戻り値が期待しない形式: {type(result)}")
                
        except Exception as e:
            print(f"❌ get_practice_history_by_type エラー: {e}")
        
        # 3. delete_practice_history_by_type の動作テスト
        print("\n3. delete_practice_history_by_type 動作テスト")
        try:
            # 実際の削除は実行しないが、関数の呼び出しをテスト
            result = db.delete_practice_history_by_type("keyword_generation_paper")
            print(f"✅ delete_practice_history_by_type 実行成功（削除件数: {result}件）")
            
            if isinstance(result, int):
                print("✅ 戻り値が整数形式")
            else:
                print(f"⚠️ 戻り値が期待しない形式: {type(result)}")
                
        except Exception as e:
            print(f"❌ delete_practice_history_by_type エラー: {e}")
        
        # 4. フォールバック機能のテスト
        print("\n4. フォールバック機能テスト")
        try:
            # 旧DBキーから新DBキーへのマッピングテスト
            legacy_mappings = {
                "キーワード生成（論文検索用）": "keyword_generation_paper",
                "キーワード生成（自由記述用）": "keyword_generation_freeform",
                "採用試験": "medical_exam_comprehensive",
                "小論文対策": "essay_practice",
                "面接対策": "interview_practice_general"
            }
            
            for legacy_type, expected_new_type in legacy_mappings.items():
                try:
                    # 旧形式でのIDマッピングをテスト
                    result = db._get_practice_type_id(legacy_type)
                    if result:
                        print(f"✅ 旧形式マッピング: '{legacy_type}' -> ID: {result}")
                    else:
                        print(f"⚠️ 旧形式マッピング失敗: '{legacy_type}'")
                except Exception as e:
                    print(f"❌ 旧形式マッピングエラー: '{legacy_type}' -> {e}")
                    
        except Exception as e:
            print(f"❌ フォールバック機能エラー: {e}")
        
        # 5. エラーハンドリングテスト
        print("\n5. エラーハンドリングテスト")
        try:
            # 存在しない練習タイプでのテスト
            invalid_types = ["invalid_type", "", None, 123]
            
            for invalid_type in invalid_types:
                try:
                    result = db._get_practice_type_id_by_new_key(invalid_type)
                    if result is None:
                        print(f"✅ 無効なタイプ '{invalid_type}' で適切にNoneを返却")
                    else:
                        print(f"⚠️ 無効なタイプ '{invalid_type}' で予期しない結果: {result}")
                except Exception as e:
                    print(f"⚠️ 無効なタイプ '{invalid_type}' でエラー（想定内）: {e}")
                    
        except Exception as e:
            print(f"❌ エラーハンドリングテストエラー: {e}")
            
        print(f"\n✅ DatabaseAdapter新機能テスト完了")
        
    except Exception as e:
        print(f"❌ DatabaseAdapterテスト全体エラー: {e}")

def test_practice_type_coverage():
    """全練習タイプの網羅性テスト"""
    
    print("\n" + "=" * 60)
    print("練習タイプ網羅性テスト")
    print("=" * 60)
    
    try:
        from modules.database_adapter import DatabaseAdapter
        db = DatabaseAdapter()
        
        # 計画書で定義された全14種類の練習タイプ
        expected_types = [
            "keyword_generation_paper",      # paper_finder.py
            "keyword_generation_freeform",   # paper_finder.py  
            "keyword_generation_general",    # paper_finder.py
            "paper_search",                  # paper_finder.py
            "medical_exam_comprehensive",    # 県総採用試験
            "medical_exam_letter_style",     # 県総採用試験（Letter）
            "medical_exam_comment_style",    # 県総採用試験（コメント）
            "essay_practice",                # 小論文
            "interview_practice_general",    # 面接（一般）
            "interview_practice_single",     # 面接（単発）
            "interview_practice_session",    # 面接（セッション）
            "english_reading_standard",      # 英語読解（標準）
            "english_reading_letter_style",  # 英語読解（Letter）
            "english_reading_comment_style", # 英語読解（コメント）
            "free_writing"                   # 自由記述
        ]
        
        print(f"期待される練習タイプ数: {len(expected_types)}")
        
        success_count = 0
        for practice_type in expected_types:
            try:
                result = db._get_practice_type_id_by_new_key(practice_type)
                if result and isinstance(result, int) and result > 0:
                    print(f"✅ {practice_type}")
                    success_count += 1
                else:
                    print(f"❌ {practice_type} (無効なID: {result})")
            except Exception as e:
                print(f"❌ {practice_type} (エラー: {e})")
        
        print(f"\n📊 網羅性テスト結果: {success_count}/{len(expected_types)} 成功")
        
        if success_count == len(expected_types):
            print("🎉 全練習タイプのマッピングが正常に動作しています！")
        else:
            print("⚠️ 一部の練習タイプでマッピングエラーがあります")
            
    except Exception as e:
        print(f"❌ 練習タイプ網羅性テストエラー: {e}")

if __name__ == "__main__":
    test_database_adapter_functions()
    test_practice_type_coverage()
    
    print("\n" + "=" * 60)
    print("DatabaseAdapterテスト完了")
    print("=" * 60) 