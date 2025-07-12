#!/usr/bin/env python3
"""
自由記述v2版の新練習タイプフォーマット対応テスト
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# テスト用のパス設定
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

class TestFreeWritingV2PracticeType(unittest.TestCase):
    """自由記述v2版の練習タイプテスト"""

    def setUp(self):
        """テスト用のセットアップ"""
        # モックセッション状態
        self.mock_session_state = {
            'knowledge_checker_v2': {
                'step': 'theme_selection',
                'theme': 'テストテーマ',
                'question': 'テスト問題',
                'answer': 'テスト回答',
                'feedback': 'テストフィードバック',
                'start_time': None
            }
        }

    @patch('streamlit.session_state', new_callable=lambda: Mock())
    @patch('modules.database_adapter.db_manager')
    def test_load_practice_history_uses_correct_type(self, mock_db_manager, mock_st_session):
        """履歴読み込み時に正しい練習タイプを使用することをテスト"""
        # テスト用のモックデータ
        mock_db_manager.load_practice_history.return_value = [
            {
                'type': 'free_writing',
                'date': '2024-01-01T10:00:00',
                'inputs': {'theme': 'テストテーマ'},
                'scores': {'総合': 8}
            }
        ]
        
        # v2ファイルのパスを設定
        v2_file_path = os.path.join(parent_dir, 'pages', '04_自由記述_v2.py')
        
        # v2ファイルから関数を動的にインポート
        import importlib.util
        spec = importlib.util.spec_from_file_location("free_writing_v2", v2_file_path)
        free_writing_v2 = importlib.util.module_from_spec(spec)
        
        # 必要な依存関係をモック
        with patch.dict('sys.modules', {
            'streamlit': Mock(),
            'modules.database_adapter': Mock(db_manager=mock_db_manager),
            'modules.session_manager': Mock(),
            'modules.medical_knowledge_checker': Mock(),
            'modules.utils': Mock()
        }):
            spec.loader.exec_module(free_writing_v2)
            
            # load_and_process_free_writing_history関数をテスト
            result = free_writing_v2.load_and_process_free_writing_history()
            
            # 正しい練習タイプで呼び出されることを確認
            mock_db_manager.load_practice_history.assert_called_with('free_writing')

    @patch('modules.database_adapter.db_manager')
    def test_is_theme_recently_used_correct_type(self, mock_db_manager):
        """最近使用テーマチェック時に正しい練習タイプを使用することをテスト"""
        mock_db_manager.is_available.return_value = True
        mock_db_manager.is_theme_recently_used.return_value = False
        
        # v2ファイルのパスを設定
        v2_file_path = os.path.join(parent_dir, 'pages', '04_自由記述_v2.py')
        
        # v2ファイルから関数を動的にインポート
        import importlib.util
        spec = importlib.util.spec_from_file_location("free_writing_v2", v2_file_path)
        free_writing_v2 = importlib.util.module_from_spec(spec)
        
        # 必要な依存関係をモック
        with patch.dict('sys.modules', {
            'streamlit': Mock(),
            'modules.database_adapter': Mock(db_manager=mock_db_manager),
            'modules.session_manager': Mock(),
            'modules.medical_knowledge_checker': Mock(),
            'modules.utils': Mock()
        }):
            spec.loader.exec_module(free_writing_v2)
            
            # database_availableをTrueに設定
            free_writing_v2.database_available = True
            
            # is_theme_recently_used_local関数をテスト
            result = free_writing_v2.is_theme_recently_used_local('テストテーマ', 3)
            
            # 正しい練習タイプで呼び出されることを確認
            mock_db_manager.is_theme_recently_used.assert_called_with('free_writing', 'テストテーマ', 3)

    def test_history_data_creation_format(self):
        """履歴データ作成時の形式をテスト"""
        # v2ファイルの内容を直接読み込んで確認
        v2_file_path = os.path.join(parent_dir, 'pages', '04_自由記述_v2.py')
        
        with open(v2_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 新しい練習タイプが使用されていることを確認
        self.assertIn("'type': 'free_writing'", content)
        self.assertNotIn("'type': '医学部採用試験 自由記述'", content)
        
        # データベース呼び出しで正しい練習タイプが使用されていることを確認
        self.assertIn("load_practice_history('free_writing')", content)
        self.assertIn("is_theme_recently_used('free_writing'", content)

    def test_v2_file_structure_compliance(self):
        """v2ファイルが新システムの構造に準拠していることをテスト"""
        v2_file_path = os.path.join(parent_dir, 'pages', '04_自由記述_v2.py')
        
        with open(v2_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 新システムのインポートが含まれていることを確認
        self.assertIn("from modules.database_adapter import db_manager", content)
        self.assertIn("from modules.session_manager import session_manager", content)
        
        # フォールバック機能が実装されていることを確認
        self.assertIn("フォールバック", content)
        
        # v2という識別が含まれていることを確認
        self.assertIn("V2", content)
        self.assertIn("新システム", content)

if __name__ == '__main__':
    print("=== 自由記述v2版の新練習タイプフォーマット対応テスト ===")
    unittest.main(verbosity=2) 