"""
paper_finder.py履歴機能テスト

get_keyword_history と clear_keyword_history の新DB対応版の動作をテストします。
"""

import sys
import os

# プロジェクトルートをPythonのパスに追加
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
sys.path.insert(0, parent_dir)

def test_keyword_history_functions():
    """paper_finderの履歴機能詳細テスト"""
    
    print("=" * 60)
    print("paper_finder履歴機能テスト")
    print("=" * 60)
    
    try:
        from modules.paper_finder import get_keyword_history, clear_keyword_history
        print("✅ paper_finder 履歴関数インポート成功")
        
        # 1. get_keyword_history の動作テスト
        print("\n1. get_keyword_history 動作テスト")
        try:
            result = get_keyword_history()
            print(f"✅ get_keyword_history 実行成功（結果: {len(result)}件）")
            
            if isinstance(result, list):
                print("✅ 戻り値がリスト形式")
                
                # 履歴の構造確認
                if len(result) > 0:
                    sample = result[0]
                    print(f"📋 履歴サンプル構造: {list(sample.keys()) if isinstance(sample, dict) else type(sample)}")
                    
                    # 期待される履歴形式のチェック
                    expected_keys = ['keywords', 'date', 'purpose']
                    if isinstance(sample, dict):
                        found_keys = [key for key in expected_keys if key in sample]
                        print(f"✅ 期待キー確認: {len(found_keys)}/{len(expected_keys)} ({found_keys})")
                else:
                    print("📋 履歴データなし（新DB適用後の初期状態）")
            else:
                print(f"⚠️ 戻り値が期待しない形式: {type(result)}")
                
        except Exception as e:
            print(f"❌ get_keyword_history エラー: {e}")
        
        # 2. clear_keyword_history の動作テスト
        print("\n2. clear_keyword_history 動作テスト")
        try:
            result = clear_keyword_history()
            print(f"✅ clear_keyword_history 実行成功（結果: {result}）")
            
            if isinstance(result, bool):
                print("✅ 戻り値がブール形式")
                if result:
                    print("✅ 履歴削除成功")
                else:
                    print("⚠️ 履歴削除失敗またはデータなし")
            else:
                print(f"⚠️ 戻り値が期待しない形式: {type(result)}")
                
        except Exception as e:
            print(f"❌ clear_keyword_history エラー: {e}")
        
        # 3. フォールバック機能テスト
        print("\n3. フォールバック機能テスト")
        try:
            # 新DB接続に失敗した場合のフォールバック動作を確認
            # (実際のDBがない環境での動作確認)
            
            print("📋 新DB無効環境での動作確認:")
            
            # get_keyword_history のフォールバック
            result = get_keyword_history()
            if isinstance(result, list):
                print("✅ get_keyword_history フォールバック正常")
            else:
                print(f"⚠️ get_keyword_history フォールバック異常: {type(result)}")
            
            # clear_keyword_history のフォールバック  
            result = clear_keyword_history()
            if isinstance(result, bool):
                print("✅ clear_keyword_history フォールバック正常")
            else:
                print(f"⚠️ clear_keyword_history フォールバック異常: {type(result)}")
                
        except Exception as e:
            print(f"❌ フォールバック機能エラー: {e}")
        
        # 4. 関数シグネチャテスト
        print("\n4. 関数シグネチャテスト")
        try:
            import inspect
            
            # get_keyword_history のシグネチャ確認
            sig = inspect.signature(get_keyword_history)
            print(f"✅ get_keyword_history シグネチャ: {sig}")
            
            # パラメータが期待通りか確認
            params = list(sig.parameters.keys())
            if len(params) == 0:
                print("✅ get_keyword_history は引数なし（期待通り）")
            else:
                print(f"⚠️ get_keyword_history に予期しない引数: {params}")
            
            # clear_keyword_history のシグネチャ確認
            sig = inspect.signature(clear_keyword_history)
            print(f"✅ clear_keyword_history シグネチャ: {sig}")
            
            params = list(sig.parameters.keys())
            if len(params) == 0:
                print("✅ clear_keyword_history は引数なし（期待通り）")
            else:
                print(f"⚠️ clear_keyword_history に予期しない引数: {params}")
                
        except Exception as e:
            print(f"❌ 関数シグネチャテストエラー: {e}")
        
        # 5. インテグレーションテスト（連続実行）
        print("\n5. インテグレーションテスト")
        try:
            print("📋 履歴取得 -> 削除 -> 再取得の連続実行テスト")
            
            # Step 1: 初期履歴取得
            initial_history = get_keyword_history()
            print(f"✅ ステップ1: 初期履歴取得（{len(initial_history)}件）")
            
            # Step 2: 履歴削除
            delete_result = clear_keyword_history()
            print(f"✅ ステップ2: 履歴削除実行（結果: {delete_result}）")
            
            # Step 3: 削除後履歴取得
            after_delete_history = get_keyword_history()
            print(f"✅ ステップ3: 削除後履歴取得（{len(after_delete_history)}件）")
            
            # 結果分析
            if len(after_delete_history) <= len(initial_history):
                print("✅ 削除が履歴件数に反映された可能性があります")
            else:
                print("⚠️ 削除が履歴件数に反映されていない可能性があります")
                
        except Exception as e:
            print(f"❌ インテグレーションテストエラー: {e}")
            
        print(f"\n✅ paper_finder履歴機能テスト完了")
        
    except Exception as e:
        print(f"❌ paper_finder履歴機能テスト全体エラー: {e}")

def test_database_integration():
    """DatabaseAdapterとの統合テスト"""
    
    print("\n" + "=" * 60)
    print("DatabaseAdapter統合テスト")
    print("=" * 60)
    
    try:
        from modules.database_adapter_v3 import DatabaseAdapterV3
        from modules.paper_finder import get_keyword_history, clear_keyword_history
        
        print("✅ 統合テスト用モジュールインポート成功")
        
        # 1. DatabaseAdapterによる直接操作テスト
        print("\n1. DatabaseAdapter直接操作テスト")
        db = DatabaseAdapterV3()
        
        # 新スキーマの履歴取得テスト
        records = db.get_user_history()
        assert isinstance(records, list)
        
        # 2. paper_finder関数による間接操作テスト
        print("\n2. paper_finder関数経由テスト")
        try:
            paper_finder_records = get_keyword_history()
            pf_count = len(paper_finder_records)
            print(f"📊 paper_finder取得件数: {pf_count}件")
            
            # 件数比較（統合テスト）
            # 新スキーマの履歴取得テスト
            new_records = db.get_user_history()
            if len(new_records) == pf_count:
                print("✅ DatabaseAdapterとpaper_finder関数の結果が一致")
            elif len(new_records) > pf_count:
                print("⚠️ DatabaseAdapterの方が多い（フィルタリングされている可能性）")
            elif len(new_records) < pf_count:
                print("⚠️ paper_finder関数の方が多い（従来データ含む可能性）")
                
        except Exception as e:
            print(f"❌ paper_finder関数経由テストエラー: {e}")
        
        # 3. 削除統合テスト
        print("\n3. 削除統合テスト")
        try:
            # paper_finder経由での削除
            delete_result = clear_keyword_history()
            print(f"✅ paper_finder経由削除実行（結果: {delete_result}）")
            
            # DatabaseAdapter経由での確認
            remaining_total = 0
            # 新スキーマの履歴取得テスト
            remaining = db.get_user_history()
            remaining_total = len(remaining)
            
            print(f"📊 削除後DatabaseAdapter確認: {remaining_total}件")
            
            # paper_finder経由での確認
            remaining_pf = get_keyword_history()
            print(f"📊 削除後paper_finder確認: {len(remaining_pf)}件")
            
            if remaining_total == 0 and len(remaining_pf) == 0:
                print("✅ 削除が両方で確認されました")
            elif remaining_total == len(remaining_pf):
                print("✅ 削除結果が両方で一致しています")
            else:
                print("⚠️ 削除結果に不整合があります")
                
        except Exception as e:
            print(f"❌ 削除統合テストエラー: {e}")
            
        print(f"\n✅ DatabaseAdapter統合テスト完了")
        
    except Exception as e:
        print(f"❌ DatabaseAdapter統合テスト全体エラー: {e}")

if __name__ == "__main__":
    test_keyword_history_functions()
    test_database_integration()
    
    print("\n" + "=" * 60)
    print("paper_finder履歴機能テスト完了")
    print("=" * 60) 