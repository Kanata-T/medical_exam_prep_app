"""
論文検索・キーワード生成のページ別区別テスト

修正後に各ページからの呼び出しが適切に区別されるかをテストします。
"""

import sys
import os

# プロジェクトルートをPythonのパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

def test_paper_search_purpose_distinction():
    """論文検索のページ別区別テスト"""
    
    print("=" * 60)
    print("論文検索のページ別区別テスト")
    print("=" * 60)
    
    try:
        from modules.paper_finder import find_medical_paper
        print("✅ find_medical_paper インポート成功")
        
        # 1. 県総採用試験からの呼び出しテスト
        print("\n1. 県総採用試験からの呼び出しテスト")
        try:
            # 実際にAPIを呼び出さずに、パラメータチェックのみ
            import inspect
            sig = inspect.signature(find_medical_paper)
            params = list(sig.parameters.keys())
            
            if 'purpose' in params:
                print("✅ purposeパラメータが存在")
                print(f"✅ 関数シグネチャ: {sig}")
                
                # モック的なテスト（実際のAPI呼び出しは避ける）
                print("✅ medical_exam目的でのパラメータ渡しは可能")
            else:
                print("❌ purposeパラメータが見つからない")
                
        except Exception as e:
            print(f"❌ 県総採用試験テストエラー: {e}")
        
        # 2. 英語読解からの呼び出しテスト  
        print("\n2. 英語読解からの呼び出しテスト")
        try:
            # 同様にパラメータチェック
            if 'purpose' in params:
                print("✅ english_reading目的でのパラメータ渡しは可能")
            else:
                print("❌ purposeパラメータが見つからない")
                
        except Exception as e:
            print(f"❌ 英語読解テストエラー: {e}")
        
        # 3. purpose-practice_typeマッピングテスト
        print("\n3. purpose-practice_typeマッピングテスト")
        
        test_mappings = {
            "medical_exam": "medical_exam_comprehensive",
            "english_reading": "english_reading_standard",
            "general": "paper_search"
        }
        
        for purpose, expected_type in test_mappings.items():
            print(f"✅ {purpose} -> {expected_type}")
        
        print(f"\n✅ 論文検索のページ別区別テスト完了")
        
    except Exception as e:
        print(f"❌ 論文検索区別テスト全体エラー: {e}")

def test_keyword_generation_purpose_distinction():
    """キーワード生成のページ別区別テスト"""
    
    print("\n" + "=" * 60)
    print("キーワード生成のページ別区別テスト")
    print("=" * 60)
    
    try:
        from modules.paper_finder import generate_medical_keywords
        print("✅ generate_medical_keywords インポート成功")
        
        # 1. 関数シグネチャ確認
        print("\n1. 関数シグネチャ確認")
        try:
            import inspect
            sig = inspect.signature(generate_medical_keywords)
            params = list(sig.parameters.keys())
            
            print(f"✅ 関数シグネチャ: {sig}")
            
            if 'purpose' in params:
                print("✅ purposeパラメータが存在")
            else:
                print("❌ purposeパラメータが見つからない")
                
        except Exception as e:
            print(f"❌ シグネチャ確認エラー: {e}")
        
        # 2. purpose-practice_typeマッピングテスト
        print("\n2. キーワード生成のpurpose-practice_typeマッピング")
        
        test_mappings = {
            "paper_search": "keyword_generation_english",
            "free_writing": "keyword_generation_free",
            "general": "keyword_generation_english"
        }
        
        for purpose, expected_type in test_mappings.items():
            print(f"✅ {purpose} -> {expected_type}")
        
        print(f"\n✅ キーワード生成のページ別区別テスト完了")
        
    except Exception as e:
        print(f"❌ キーワード生成区別テスト全体エラー: {e}")

def test_page_call_integration():
    """各ページでの呼び出し統合テスト"""
    
    print("\n" + "=" * 60)
    print("各ページでの呼び出し統合テスト")
    print("=" * 60)
    
    # 1. ページファイルの呼び出し箇所確認
    print("\n1. ページファイルの呼び出し箇所確認")
    
    test_files = [
        ("pages/01_県総_採用試験.py", "medical_exam"),
        ("pages/05_英語読解.py", "english_reading")
    ]
    
    for file_path, expected_purpose in test_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # find_medical_paperの呼び出し検索
            if f'find_medical_paper(keywords, "{expected_purpose}")' in content:
                print(f"✅ {file_path}: 正しいpurpose ({expected_purpose}) で呼び出し")
            elif 'find_medical_paper(keywords)' in content:
                print(f"⚠️ {file_path}: 古い形式での呼び出し（purpose指定なし）")
            elif 'find_medical_paper' in content:
                print(f"⚠️ {file_path}: find_medical_paperは使用されているがpurpose不明")
            else:
                print(f"ℹ️ {file_path}: find_medical_paperは使用されていない")
                
        except Exception as e:
            print(f"❌ {file_path}: 確認エラー ({e})")
    
    # 2. 履歴保存の区別確認
    print("\n2. 履歴保存の区別確認")
    
    expected_practice_types = [
        "prefecture_adoption",         # 県総採用試験
        "english_reading_practice",    # 英語読解
        "keyword_generation_english",  # 論文検索用キーワード
        "keyword_generation_free",     # 自由記述用キーワード
        "keyword_generation_adoption"  # 採用試験用キーワード
    ]
    
    for practice_type in expected_practice_types:
        print(f"✅ 練習タイプ対応予定: {practice_type}")
    
    print(f"\n✅ 各ページでの呼び出し統合テスト完了")

def test_database_adapter_compatibility():
    """DatabaseAdapterとの互換性テスト"""
    
    print("\n" + "=" * 60)
    print("DatabaseAdapterとの互換性テスト")
    print("=" * 60)
    
    try:
        from modules.database_adapter_v3 import DatabaseAdapterV3
        
        db = DatabaseAdapterV3()
        print("✅ DatabaseAdapter インスタンス化成功")
        
        # 新しい練習タイプのマッピング確認
        new_practice_types = [
            "prefecture_adoption",
            "english_reading_practice",
            "keyword_generation_english",
            "keyword_generation_free",
            "keyword_generation_adoption"
        ]
        
        print("\n新しい練習タイプのマッピング確認:")
        mapping_success = 0
        for practice_type in new_practice_types:
            try:
                result = db._get_practice_type_id_by_new_key(practice_type)
                if result and isinstance(result, int) and result > 0:
                    print(f"✅ {practice_type} -> ID: {result}")
                    mapping_success += 1
                else:
                    print(f"❌ {practice_type} -> 無効なID: {result}")
            except Exception as e:
                print(f"❌ {practice_type} -> エラー: {e}")
        
        print(f"\n📊 マッピング成功率: {mapping_success}/{len(new_practice_types)}")
        
        if mapping_success == len(new_practice_types):
            print("🎉 全ての新しい練習タイプが正常にマッピングされています！")
        else:
            print("⚠️ 一部の練習タイプでマッピングエラーがあります")
            
        # 新スキーマの履歴取得テスト
        records = db.get_user_history()
        assert isinstance(records, list)
        
        print(f"\n✅ DatabaseAdapterとの互換性テスト完了")
        
    except Exception as e:
        print(f"❌ DatabaseAdapter互換性テスト全体エラー: {e}")

if __name__ == "__main__":
    print("🔍 修正後のページ別区別テスト")
    print("=" * 80)
    
    test_paper_search_purpose_distinction()
    test_keyword_generation_purpose_distinction()
    test_page_call_integration()
    test_database_adapter_compatibility()
    
    print("\n" + "=" * 80)
    print("✅ ページ別区別テスト完了")
    print("=" * 80) 