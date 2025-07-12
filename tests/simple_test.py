"""
シンプルなモジュールテスト
"""

import sys
import os

# プロジェクトルートをPythonのパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

print("=" * 50)
print("新DB対応リファクタリング - シンプルテスト")
print("=" * 50)
print(f"プロジェクトルート: {parent_dir}")
print(f"Python PATH: {sys.path[:3]}...")  # 最初の3つだけ表示

# 1. DatabaseAdapterのテスト
print("\n1. DatabaseAdapterのテスト")
try:
    from modules.database_adapter import DatabaseAdapter
    print("✅ DatabaseAdapter インポート成功")
    
    db = DatabaseAdapter()
    print("✅ DatabaseAdapter インスタンス化成功")
    
    # 新機能の存在確認
    if hasattr(db, 'get_practice_history_by_type'):
        print("✅ get_practice_history_by_type メソッド存在")
    else:
        print("❌ get_practice_history_by_type メソッドなし")
        
    if hasattr(db, 'delete_practice_history_by_type'):
        print("✅ delete_practice_history_by_type メソッド存在")
    else:
        print("❌ delete_practice_history_by_type メソッドなし")
        
except Exception as e:
    print(f"❌ DatabaseAdapter エラー: {e}")

# 2. DatabaseManagerV2のテスト
print("\n2. DatabaseManagerV2のテスト")
try:
    from modules.database_v2 import DatabaseManagerV2
    print("✅ DatabaseManagerV2 インポート成功")
    
    db_v2 = DatabaseManagerV2()
    print("✅ DatabaseManagerV2 インスタンス化成功")
    
    if hasattr(db_v2, 'delete_user_history_by_type'):
        print("✅ delete_user_history_by_type メソッド存在")
    else:
        print("❌ delete_user_history_by_type メソッドなし")
        
except Exception as e:
    print(f"❌ DatabaseManagerV2 エラー: {e}")

# 3. paper_finderのテスト
print("\n3. paper_finderのテスト")
try:
    from modules.paper_finder import get_keyword_history, clear_keyword_history
    print("✅ paper_finder 関数インポート成功")
    
    # 関数が呼び出し可能かチェック（実際には実行しない）
    if callable(get_keyword_history):
        print("✅ get_keyword_history 関数は呼び出し可能")
    if callable(clear_keyword_history):
        print("✅ clear_keyword_history 関数は呼び出し可能")
        
except Exception as e:
    print(f"❌ paper_finder エラー: {e}")

# 4. SessionManagerのテスト
print("\n4. SessionManagerのテスト")
try:
    from modules.session_manager import StreamlitSessionManager
    print("✅ StreamlitSessionManager インポート成功")
    
except Exception as e:
    print(f"❌ StreamlitSessionManager エラー: {e}")

# 5. 練習タイプマッピングのテスト
print("\n5. 練習タイプマッピングのテスト")
try:
    from modules.database_adapter import DatabaseAdapter
    db = DatabaseAdapter()
    
    # 練習タイプマッピングの確認
    test_types = [
        "keyword_generation_paper",
        "keyword_generation_freeform", 
        "keyword_generation_general",
        "paper_search",
        "medical_exam_comprehensive",
        "essay_practice",
        "interview_practice_single",
        "english_reading_standard"
    ]
    
    if hasattr(db, '_get_practice_type_id_by_new_key'):
        print("✅ 練習タイプマッピング関数存在")
        
        # サンプルマッピングテスト
        for practice_type in test_types[:3]:  # 最初の3つだけテスト
            try:
                result = db._get_practice_type_id_by_new_key(practice_type)
                if result:
                    print(f"✅ {practice_type} -> ID: {result}")
                else:
                    print(f"⚠️ {practice_type} -> マッピングなし")
            except Exception as e:
                print(f"❌ {practice_type} -> エラー: {e}")
    else:
        print("❌ 練習タイプマッピング関数なし")
        
except Exception as e:
    print(f"❌ 練習タイプマッピング エラー: {e}")

print("\n" + "=" * 50)
print("テスト完了")
print("=" * 50) 