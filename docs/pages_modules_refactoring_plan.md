# ページとモジュール新DB対応修正計画 (修正版)

## 📋 概要

このドキュメントでは、新しいDatabaseManagerV2システムへの対応のため、残りの4つのページ（県総_採用試験、小論文、面接、英語読解）と関連するmodulesの修正計画を詳述します。

## 🚨 **重要な発見: 計画修正が必要**

詳細実装確認により、`modules/paper_finder.py`に**新DB対応が必要な特殊な履歴機能**を発見しました：

### 🔧 **修正が必要な履歴機能**
1. **`get_keyword_history()`** - キーワード生成履歴の取得
2. **`clear_keyword_history()`** - キーワード履歴の削除
3. **キーワード生成時の保存** - 論文検索・自由記述用の分類

これらは`utils.py`の一般的な履歴機能では対応されていない**専用機能**です。

## 🎯 修正対象一覧

### 📄 対象ページ
1. `pages/01_県総_採用試験.py` (1037行)
2. `pages/02_小論文.py` (388行)
3. `pages/03_面接.py` (435行)
4. `pages/05_英語読解.py` (816行)

### 🔧 対象モジュール
1. **`modules/paper_finder.py` (1122行)** - **🚨 修正必須** 
   - 論文検索履歴、キーワード生成履歴の新DB対応
   - 特殊な履歴管理関数の新DB対応
2. `modules/scorer.py` (584行) - 修正不要（utils経由）
3. `modules/essay_scorer.py` (262行) - 修正不要（utils経由）
4. `modules/interview_prepper.py` (192行) - 修正不要（utils経由）
5. `modules/medical_knowledge_checker.py` (456行) - 修正不要（utils経由）

## 🔍 現在の実装分析

### データベース依存関係の分析（詳細版）

#### 📊 **paper_finder.pyの履歴処理パターン**

**1. キーワード生成時の保存**:
```python
# 現在の実装（3種類の練習タイプ）
practice_type = "キーワード生成（論文検索用）"  # purpose="general"
practice_type = "キーワード生成（自由記述用）"  # purpose="freeform"  
practice_type = "キーワード生成"              # デフォルト

history_data = {
    "type": practice_type,
    "date": datetime.now().isoformat(),
    "keywords": keyword_info["keywords"],
    "category": keyword_info["category"],
    "rationale": keyword_info["rationale"],
    "purpose": keyword_info["purpose"]
}
save_history(history_data)  # utils.save_history()を使用
```

**2. キーワード履歴取得**:
```python
def get_keyword_history():
    persistent_history = load_history()  # utils.load_history()を使用
    # "キーワード生成"で始まる全てのタイプを抽出
    for item in persistent_history:
        practice_type = item.get('type', '')
        if (practice_type == 'キーワード生成' or 
            practice_type.startswith('キーワード生成')):
            # キーワード履歴として処理
```

**3. キーワード履歴削除**:
```python
def clear_keyword_history():
    # 🚨 問題: 直接ファイルシステムを操作
    for filename in os.listdir(HISTORY_DIR):
        # ファイルを直接削除
        if practice_type.startswith('キーワード生成'):
            os.remove(filepath)
```

#### 📋 練習タイプマッピング（検証済み・修正版）

### **完全な練習タイプ変換表**

| 現在の実装 | 実装場所 | 新DBキー | カテゴリ | 修正優先度 |
|------------|----------|----------|----------|------------|
| **modules/paper_finder.py** |
| "キーワード生成（論文検索用）" | Line 539 | `keyword_generation_paper` | keyword_generation | 🔥 高 |
| "キーワード生成（自由記述用）" | Line 541 | `keyword_generation_freeform` | keyword_generation | 🔥 高 |
| "キーワード生成" | Line 543 | `keyword_generation_general` | keyword_generation | 🔥 高 |
| "論文検索" | Line 460, 486 | `paper_search` | research | 🔥 高 |
| **pages/01_県総_採用試験.py** |
| "採用試験" | Line 981 | `medical_exam_comprehensive` | comprehensive_exam | 🔶 中 |
| "過去問スタイル採用試験 - Letter形式" | Line 981 | `medical_exam_letter_style` | comprehensive_exam | 🔶 中 |
| "過去問スタイル採用試験 - 論文コメント形式" | Line 981 | `medical_exam_comment_style` | comprehensive_exam | 🔶 中 |
| **pages/02_小論文.py** |
| "小論文対策" | Line 325 | `essay_practice` | essay_writing | 🔶 中 |
| **pages/03_面接.py** |
| "面接対策" | Line 304, 369 | `interview_practice_general` | interview_prep | 🔶 中 |
| "面接対策(単発)" | Line 304 | `interview_practice_single` | interview_prep | 🔶 中 |
| "面接対策(セッション)" | Line 369 | `interview_practice_session` | interview_prep | 🔶 中 |
| **pages/05_英語読解.py** |
| "英語読解" | 予測 | `english_reading_standard` | english_reading | 🔶 中 |
| "過去問スタイル英語読解 - XXX" | 予測 | `english_reading_*_style` | english_reading | 🔶 中 |

### **修正必要箇所の詳細**

#### **🔥 最優先修正: modules/paper_finder.py**

**1. キーワード生成時の練習タイプ統一**
```python
# 修正箇所: Line 537-543
# 修正前
if purpose == "paper_search":
    practice_type = "キーワード生成（論文検索用）"
elif purpose == "free_writing":
    practice_type = "キーワード生成（自由記述用）"
else:
    practice_type = "キーワード生成"

# 修正後  
if purpose == "paper_search":
    practice_type = "keyword_generation_paper"
elif purpose == "free_writing":
    practice_type = "keyword_generation_freeform"
else:
    practice_type = "keyword_generation_general"
```

**2. 論文検索時の練習タイプ統一**
```python
# 修正箇所: Line 460, 486
# 修正前
"type": "論文検索"

# 修正後
"type": "paper_search"
```

**3. キーワード履歴関数の新DB対応**（前述の詳細実装通り）

#### **🔶 中優先修正: 各ページの練習タイプ統一**

**pages/01_県総_採用試験.py (Line 981周辺)**
```python
# 修正前
if submitted.get('exam_style', False):
    exam_type = "過去問スタイル採用試験"
    format_name = format_names.get(submitted.get('format_type', ''), '不明')
    exam_type += f" - {format_name}"
else:
    exam_type = "採用試験"

# 修正後
if submitted.get('exam_style', False):
    format_type = submitted.get('format_type', '')
    if format_type == "letter_translation_opinion":
        exam_type = "medical_exam_letter_style"
    elif format_type == "paper_comment_translation_opinion":
        exam_type = "medical_exam_comment_style"
    else:
        exam_type = "medical_exam_comprehensive"
else:
    exam_type = "medical_exam_comprehensive"
```

**pages/02_小論文.py (Line 325周辺)**
```python
# 修正前
"type": "小論文対策"

# 修正後
"type": "essay_practice"
```

**pages/03_面接.py (Line 304, 369周辺)**
```python
# 修正前（複数パターン）
"type": "面接対策"
"type": "面接対策(単発)"  
"type": "面接対策(セッション)"

# 修正後（文脈に応じて）
"type": "interview_practice_general"
"type": "interview_practice_single"
"type": "interview_practice_session"
```

## 🚀 修正戦略（修正版）

### Phase 1: modules/paper_finder.py の修正（高優先度）

#### 1.1 **履歴保存の新DB対応**

**現在の問題**:
```python
# 現在の実装 - 正常動作（utils経由）
save_history(history_data)  # ✅ これは既に新DB対応済み
```

**修正内容**: 練習タイプ名の統一のみ必要

#### 1.2 **履歴取得の新DB対応**

**現在の問題**:
```python
# 現在の実装
def get_keyword_history():
    persistent_history = load_history()  # utils.load_history()使用
    # 🚨 問題: 新DBから適切にキーワード履歴を取得できるか不明
```

**修正後の実装**:
```python
def get_keyword_history():
    """新DB対応版のキーワード履歴取得"""
    from modules.database_adapter import DatabaseAdapter
    
    db_adapter = DatabaseAdapter()
    
    try:
        # 新DBからキーワード生成関連の履歴を取得
        keyword_types = [
            'keyword_generation_paper',
            'keyword_generation_freeform', 
            'keyword_generation_general'
        ]
        
        all_history = []
        for practice_type in keyword_types:
            history = db_adapter.get_practice_history_by_type(practice_type)
            all_history.extend(history)
        
        # 日付順でソート
        all_history.sort(key=lambda x: x.get('created_at', ''))
        
        # 必要な形式に変換
        keyword_history = []
        for item in all_history:
            keyword_history.append({
                'keywords': item.get('keywords', ''),
                'category': item.get('category', ''),
                'rationale': item.get('rationale', ''),
                'date': item.get('created_at', ''),
                'purpose': item.get('purpose', 'general')
            })
        
        return keyword_history
        
    except Exception as e:
        # フォールバック: 従来のload_history()を使用
        logger.warning(f"新DB履歴取得失敗、フォールバック使用: {e}")
        return _get_keyword_history_legacy()

def _get_keyword_history_legacy():
    """従来版のキーワード履歴取得（フォールバック用）"""
    from modules.utils import load_history
    
    persistent_history = load_history()
    keyword_history = []
    
    for item in persistent_history:
        practice_type = item.get('type', '')
        if (practice_type == 'キーワード生成' or 
            practice_type.startswith('キーワード生成')):
            keyword_history.append({
                'keywords': item.get('keywords', ''),
                'category': item.get('category', ''),
                'rationale': item.get('rationale', ''),
                'date': item.get('date', ''),
                'purpose': item.get('purpose', 'general')
            })
    
    return keyword_history
```

#### 1.3 **履歴削除の新DB対応**

**現在の問題**:
```python
# 現在の実装 - 🚨 新DBに対応していない
def clear_keyword_history():
    # 直接ファイルシステムを操作
    for filename in os.listdir(HISTORY_DIR):
        # ファイルを削除
```

**修正後の実装**:
```python
def clear_keyword_history():
    """新DB対応版のキーワード履歴削除"""
    from modules.database_adapter import DatabaseAdapter
    
    db_adapter = DatabaseAdapter()
    
    try:
        # 新DBからキーワード生成関連の履歴を削除
        keyword_types = [
            'keyword_generation_paper',
            'keyword_generation_freeform',
            'keyword_generation_general'
        ]
        
        deleted_count = 0
        for practice_type in keyword_types:
            count = db_adapter.delete_practice_history_by_type(practice_type)
            deleted_count += count
        
        # セッション状態の履歴もクリア
        if 'keyword_history' in st.session_state:
            st.session_state.keyword_history = []
            
        logger.info(f"キーワード履歴削除完了: {deleted_count}件")
        return True
        
    except Exception as e:
        # フォールバック: 従来のファイル削除を実行
        logger.warning(f"新DB履歴削除失敗、フォールバック使用: {e}")
        return _clear_keyword_history_legacy()

def _clear_keyword_history_legacy():
    """従来版のキーワード履歴削除（フォールバック用）"""
    import os
    from modules.utils import HISTORY_DIR
    
    deleted_count = 0
    if os.path.exists(HISTORY_DIR):
        for filename in os.listdir(HISTORY_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(HISTORY_DIR, filename)
                try:
                    import json
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    practice_type = data.get('type', '')
                    if (practice_type == 'キーワード生成' or 
                        practice_type.startswith('キーワード生成')):
                        os.remove(filepath)
                        deleted_count += 1
                except (json.JSONDecodeError, IOError):
                    continue
    
    # セッション状態もクリア
    if 'keyword_history' in st.session_state:
        st.session_state.keyword_history = []
        
    logger.info(f"従来形式でキーワード履歴削除: {deleted_count}件")
    return True
```

#### 1.4 **練習タイプ名の統一**

**修正箇所**:
```python
# 修正前
practice_type = "キーワード生成（論文検索用）"
practice_type = "キーワード生成（自由記述用）"
practice_type = "キーワード生成"

# 修正後
if purpose == "general":
    practice_type = "keyword_generation_paper"
elif purpose == "freeform":
    practice_type = "keyword_generation_freeform"
else:
    practice_type = "keyword_generation_general"
```

### Phase 2: ページ修正（前回と同様）

#### 2.1 pages/01_県総_採用試験.py の修正

**修正項目**:

1. **インポート部分の更新**:
```python
# 追加
from modules.database_adapter import DatabaseAdapter
from modules.session_manager import StreamlitSessionManager

# セッション管理初期化
session_manager = StreamlitSessionManager()
session_manager.initialize_session()
db_adapter = DatabaseAdapter()
```

2. **セッション状態表示の追加**:
```python
# セッション状況の表示（学習履歴ページと同様）
session_status = session_manager.get_session_status()
if session_status["authenticated"]:
    st.info(f"🔐 セッション: {session_status['method']} ({session_status['persistence']})")
```

3. **練習タイプ名の統一**:
```python
# 修正前
practice_type = "採用試験"
if exam_style_enabled:
    practice_type = f"過去問スタイル採用試験 - {format_type}"

# 修正後
practice_type = "medical_exam_comprehensive"
if exam_style_enabled:
    if format_type == "letter_translation_opinion":
        practice_type = "medical_exam_letter_style"
    else:
        practice_type = "medical_exam_comment_style"
```

#### 2.2 pages/02_小論文.py の修正

**修正項目**:

1. **インポートとセッション管理**:
```python
from modules.database_adapter import DatabaseAdapter
from modules.session_manager import StreamlitSessionManager

session_manager = StreamlitSessionManager()
session_manager.initialize_session()
```

2. **練習タイプ名の統一**:
```python
# 修正前
"type": "小論文対策"

# 修正後  
"type": "essay_practice"
```

3. **セッション状態表示の追加**:
```python
# セッション状況をサイドバーに表示
with st.sidebar:
    session_status = session_manager.get_session_status()
    if session_status["authenticated"]:
        st.success(f"🔐 セッション継続中")
```

#### 2.3 pages/03_面接.py の修正

**修正項目**:

1. **インポートとセッション管理**:
```python
from modules.database_adapter import DatabaseAdapter
from modules.session_manager import StreamlitSessionManager

# グローバル初期化
session_manager = StreamlitSessionManager()
session_manager.initialize_session()
```

2. **練習タイプ名の統一**:
```python
# 修正前
"type": "面接対策"
"type": "面接対策(単発)"
"type": "面接対策(セッション)"

# 修正後
"type": "interview_practice_general"
"type": "interview_practice_single" 
"type": "interview_practice_session"
```

3. **セッション継続機能の強化**:
```python
# 面接セッション中の状態保存
def save_interview_session_state():
    session_data = {
        'interview_mode': st.session_state.interview_mode,
        'single_practice_vars': st.session_state.get('single_practice_vars', {}),
        'session_practice_vars': st.session_state.get('session_practice_vars', {})
    }
    session_manager.save_session_state(session_data)
```

#### 2.4 pages/05_英語読解.py の修正

**修正項目**:

1. **インポートとセッション管理** (01_県総と同様)

2. **練習タイプ名の統一**:
```python
# 修正前
practice_type = "英語読解"
if exam_style_enabled:
    practice_type = f"過去問スタイル英語読解 - {format_type}"

# 修正後
practice_type = "english_reading_standard"
if exam_style_enabled:
    if format_type == "letter_translation_opinion":
        practice_type = "english_reading_letter_style"
    else:
        practice_type = "english_reading_comment_style"
```

## 📋 修正スケジュール（修正版）

### Week 1: 重要モジュール修正

| 日程 | 作業項目 | 担当範囲 | 完了条件 |
|------|----------|----------|----------|
| Day 1 | paper_finder.py履歴関数修正 | get_keyword_history()の新DB対応 | 新DBからキーワード履歴取得成功 |
| Day 2 | paper_finder.py履歴関数修正 | clear_keyword_history()の新DB対応 | 新DBでキーワード履歴削除成功 |
| Day 3 | paper_finder.py練習タイプ統一 | キーワード生成タイプ名変更 | 新しいタイプで保存・取得動作 |
| Day 4 | 動作テスト・検証 | paper_finder全機能確認 | 論文検索・キーワード機能正常動作 |

### Week 2: ページ修正

| 日程 | 作業項目 | 担当範囲 | 完了条件 |
|------|----------|----------|----------|
| Day 1 | 02_小論文.py修正 | 新DB対応・セッション管理 | 小論文結果が新DBに保存 |
| Day 2 | 05_英語読解.py修正 | 新DB対応・セッション管理 | 読解結果が新DBに保存 |
| Day 3 | 01_県総_採用試験.py修正 | 新DB対応・セッション管理 | 採点結果が新DBに保存 |
| Day 4 | 03_面接.py修正 | 新DB対応・セッション管理 | 面接結果が新DBに保存 |
| Day 5 | 統合テスト | 全ページ動作確認 | 全機能正常動作 |

## 🔧 技術仕様（修正版）

### **新たに必要なDatabaseAdapter機能（詳細仕様）**

```python
class DatabaseAdapter:
    def get_practice_history_by_type(self, practice_type: str, limit: int = 50) -> List[Dict]:
        """
        指定された練習タイプの履歴を取得
        
        Args:
            practice_type: 新DBキー（例: "keyword_generation_paper"）
            limit: 取得件数上限
            
        Returns:
            履歴データのリスト（created_at降順）
        """
        try:
            # 新DBから指定タイプの履歴を取得
            if self.v2_manager:
                # practice_typeを新DBのpractice_type_idに変換
                practice_type_id = self._get_practice_type_id(practice_type)
                if practice_type_id:
                    return self.v2_manager.get_user_history(practice_type_id, limit)
            
            # フォールバック: 旧システムから取得
            return self._get_legacy_history_by_type(practice_type, limit)
            
        except Exception as e:
            logger.error(f"練習タイプ別履歴取得エラー: {e}")
            return []
    
    def delete_practice_history_by_type(self, practice_type: str) -> int:
        """
        指定された練習タイプの履歴を削除
        
        Args:
            practice_type: 新DBキー
            
        Returns:
            削除件数
        """
        try:
            deleted_count = 0
            if self.v2_manager:
                # 新DBから削除
                practice_type_id = self._get_practice_type_id(practice_type)
                if practice_type_id:
                    deleted_count = self.v2_manager.delete_user_history_by_type(practice_type_id)
            
            # フォールバック: 旧システムからも削除
            legacy_count = self._delete_legacy_history_by_type(practice_type)
            
            return deleted_count + legacy_count
            
        except Exception as e:
            logger.error(f"練習タイプ別履歴削除エラー: {e}")
            return 0
    
    def _get_practice_type_id(self, practice_type: str) -> int:
        """新DBキーからpractice_type_idを取得"""
        # 実装が必要: 新DBキーとIDのマッピング
        type_mapping = {
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
            "english_reading_comment_style": 14
        }
        return type_mapping.get(practice_type)
    
    def _get_legacy_history_by_type(self, practice_type: str, limit: int) -> List[Dict]:
        """旧システムから指定タイプの履歴を取得（フォールバック）"""
        try:
            from modules.utils import load_history
            all_history = load_history()
            
            # 旧DBキーから新DBキーへのマッピング
            legacy_mapping = {
                "keyword_generation_paper": ["キーワード生成（論文検索用）"],
                "keyword_generation_freeform": ["キーワード生成（自由記述用）"],
                "keyword_generation_general": ["キーワード生成"],
                "paper_search": ["論文検索"],
                "medical_exam_comprehensive": ["採用試験"],
                "medical_exam_letter_style": ["過去問スタイル採用試験 - Letter"],
                "medical_exam_comment_style": ["過去問スタイル採用試験 - 論文コメント"],
                "essay_practice": ["小論文対策"],
                "interview_practice_general": ["面接対策"],
                "interview_practice_single": ["面接対策(単発)"],
                "interview_practice_session": ["面接対策(セッション)"],
                "english_reading_standard": ["英語読解"],
                "english_reading_letter_style": ["過去問スタイル英語読解 - Letter"],
                "english_reading_comment_style": ["過去問スタイル英語読解 - 論文コメント"]
            }
            
            legacy_types = legacy_mapping.get(practice_type, [])
            filtered_history = []
            
            for item in all_history:
                item_type = item.get('type', '')
                # 完全一致または部分一致チェック
                if any(legacy_type in item_type for legacy_type in legacy_types):
                    filtered_history.append(item)
            
            # 日付順でソート（最新順）
            filtered_history.sort(key=lambda x: x.get('date', ''), reverse=True)
            
            return filtered_history[:limit]
            
        except Exception as e:
            logger.error(f"旧システム履歴取得エラー: {e}")
            return []
    
    def _delete_legacy_history_by_type(self, practice_type: str) -> int:
        """旧システムから指定タイプの履歴を削除（フォールバック）"""
        try:
            import os
            from modules.utils import HISTORY_DIR
            
            # 旧DBキーマッピング（削除用）
            legacy_mapping = {
                "keyword_generation_paper": ["キーワード生成（論文検索用）"],
                "keyword_generation_freeform": ["キーワード生成（自由記述用）"],
                "keyword_generation_general": ["キーワード生成"],
                "paper_search": ["論文検索"],
                "medical_exam_comprehensive": ["採用試験"],
                "essay_practice": ["小論文対策"],
                "interview_practice_general": ["面接対策"],
                "interview_practice_single": ["面接対策(単発)"],
                "interview_practice_session": ["面接対策(セッション)"]
            }
            
            legacy_types = legacy_mapping.get(practice_type, [])
            deleted_count = 0
            
            if os.path.exists(HISTORY_DIR) and legacy_types:
                for filename in os.listdir(HISTORY_DIR):
                    if filename.endswith('.json'):
                        filepath = os.path.join(HISTORY_DIR, filename)
                        try:
                            import json
                            with open(filepath, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            item_type = data.get('type', '')
                            
                            # 指定タイプに一致する場合は削除
                            if any(legacy_type in item_type for legacy_type in legacy_types):
                                os.remove(filepath)
                                deleted_count += 1
                                
                        except (json.JSONDecodeError, IOError, OSError):
                            continue
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"旧システム履歴削除エラー: {e}")
            return 0
```

### **DatabaseManagerV2への追加実装**

```python
class HistoryManager:
    def delete_user_history_by_type(self, user_id: str, practice_type_id: int) -> int:
        """
        指定ユーザーの指定練習タイプの履歴を削除
        
        Args:
            user_id: ユーザーID
            practice_type_id: 練習タイプID
            
        Returns:
            削除件数
        """
        try:
            query = """
            DELETE FROM practice_history 
            WHERE user_id = %s AND practice_type_id = %s
            """
            
            cursor = self.db_manager.connection.cursor()
            cursor.execute(query, (user_id, practice_type_id))
            deleted_count = cursor.rowcount
            self.db_manager.connection.commit()
            cursor.close()
            
            logger.info(f"練習履歴削除: user_id={user_id}, type_id={practice_type_id}, count={deleted_count}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"練習履歴削除エラー: {e}")
            if self.db_manager.connection:
                self.db_manager.connection.rollback()
            return 0

class DatabaseManagerV2:
    def delete_user_history_by_type(self, practice_type_id: int) -> int:
        """
        現在のユーザーの指定練習タイプの履歴を削除
        
        Args:
            practice_type_id: 練習タイプID
            
        Returns:
            削除件数
        """
        try:
            user_id = self.get_current_user_id()
            if not user_id:
                logger.warning("ユーザーIDが取得できないため履歴削除をスキップ")
                return 0
                
            return self.history_manager.delete_user_history_by_type(user_id, practice_type_id)
            
        except Exception as e:
            logger.error(f"ユーザー履歴削除エラー: {e}")
            return 0
```

### セッション管理の統合

**各ページに追加する共通コード**:
```python
# ページ上部に追加
from modules.database_adapter import DatabaseAdapter
from modules.session_manager import StreamlitSessionManager

# セッション初期化（ページ読み込み時に1回）
if 'session_initialized' not in st.session_state:
    session_manager = StreamlitSessionManager()
    session_manager.initialize_session()
    st.session_state.session_initialized = True
    st.session_state.session_manager = session_manager

# セッション状態の表示（オプション）
session_status = st.session_state.session_manager.get_session_status()
if session_status["authenticated"]:
    st.sidebar.success(f"🔐 セッション: {session_status['method']}")
```

### データ保存の統一

**新しい practice_type 使用パターン**:
```python
# 各ページでの統一された保存方法
def save_practice_result(practice_type_key, inputs, scores, feedback, duration_seconds=0):
    """練習結果を新DBシステムに保存"""
    history_data = {
        "type": practice_type_key,  # 新しい統一キー
        "date": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": duration_seconds,
        "inputs": inputs,
        "scores": scores,
        "feedback": feedback
    }
    
    # utils.save_history()が新システム対応済み
    return save_history(history_data)
```

### エラーハンドリングの強化

**新しいエラーハンドリングパターン**:
```python
try:
    # データ保存処理
    success = save_practice_result(...)
    if success:
        st.success("✅ 結果を保存しました")
    else:
        st.warning("⚠️ 保存に失敗しましたが、ローカルファイルに保存されました")
except Exception as e:
    st.error(f"❌ 保存処理中にエラーが発生しました: {e}")
    st.info("💡 結果はブラウザに表示されており、手動でコピー可能です")
```

## 🧪 テスト計画（修正版）

### 単体テスト

#### **modules/paper_finder.py（重要）**
- [ ] `get_keyword_history()` - 新DBから履歴を正しく取得できる
- [ ] `clear_keyword_history()` - 新DBの履歴削除が動作する
- [ ] `generate_medical_keywords()` - 新しい練習タイプで保存される
- [ ] `find_medical_paper()` - 論文検索履歴が新DBに正しく記録される
- [ ] フォールバック機能 - 新DB接続失敗時に従来機能が動作する

#### **DatabaseAdapter（新機能）**
- [ ] `get_practice_history_by_type()` - 指定タイプの履歴取得
- [ ] `delete_practice_history_by_type()` - 指定タイプの履歴削除

#### pages/01_県総_採用試験.py
- [ ] セッション初期化が正常に動作する
- [ ] 採点結果が新DBに `medical_exam_comprehensive` として保存される
- [ ] 過去問スタイルの結果が適切な練習タイプで保存される
- [ ] セッション継続機能が動作する

#### pages/02_小論文.py
- [ ] セッション初期化が正常に動作する
- [ ] 小論文結果が `essay_practice` として保存される
- [ ] 追加質問機能が新DBと連携して動作する

#### pages/03_面接.py
- [ ] セッション初期化が正常に動作する
- [ ] 単発練習結果が `interview_practice_single` として保存される
- [ ] セッション練習結果が `interview_practice_session` として保存される
- [ ] 面接状態の保存・復元が動作する

#### pages/05_英語読解.py
- [ ] セッション初期化が正常に動作する
- [ ] 英語読解結果が `english_reading_standard` として保存される
- [ ] 過去問スタイルの結果が適切な練習タイプで保存される

### 統合テスト

#### セッション管理
- [ ] ページ間移動でセッションが継続される
- [ ] ブラウザリロードでセッションが復元される
- [ ] 7日間の持続性が確保される

#### データ整合性
- [ ] 学習履歴ページで全ての新しい練習結果が表示される
- [ ] 練習タイプ別の統計が正しく集計される
- [ ] スコア推移が正確に表示される
- [ ] **キーワード履歴機能が正常に動作する**

#### パフォーマンス
- [ ] 各ページの読み込み時間が許容範囲内
- [ ] データ保存処理が高速化されている
- [ ] 複数ユーザーの同時利用で問題が発生しない

## 🚨 リスク管理（修正版）

### 最高リスク項目

1. **paper_finder.pyの履歴機能不全**
   - **リスク**: キーワード履歴の取得・削除が新DBで機能しない
   - **対策**: フォールバック機能で従来のファイル操作を維持
   - **検証**: 新DB接続エラー時の従来機能動作確認

### 高リスク項目

2. **DatabaseAdapterの新機能実装不備**
   - **リスク**: 必要な履歴操作関数が未実装
   - **対策**: 実装前に詳細仕様を確定
   - **検証**: 各関数の単体テスト実施

3. **セッション管理の整合性**
   - **リスク**: ページ間でセッション状態が不整合になる
   - **対策**: 共通のセッション初期化関数を作成
   - **検証**: 全ページでセッション状態をログ出力して確認

4. **練習タイプの変更による履歴表示問題**
   - **リスク**: 既存の履歴が新しい練習タイプで表示されない
   - **対策**: DatabaseAdapterで旧タイプから新タイプへのマッピング
   - **検証**: 移行前後の履歴件数を比較

### 中リスク項目

1. **パフォーマンスの劣化**
   - **リスク**: 新システムでレスポンスが遅くなる
   - **対策**: セッション初期化の最適化
   - **検証**: ページ読み込み時間の測定

2. **ユーザー体験の変化**
   - **リスク**: セッション管理UIが混乱を招く
   - **対策**: 控えめで分かりやすい表示
   - **検証**: ユーザビリティテスト

## 📊 成功指標（修正版）

### 機能面
- ✅ 全ページで新DB保存が動作する
- ✅ **paper_finder.pyの履歴機能が新DBで正常動作する**
- ✅ セッション継続率 > 95%
- ✅ データ保存成功率 > 98%
- ✅ 学習履歴表示の正確性 100%

### パフォーマンス面  
- ✅ ページ読み込み時間 < 3秒
- ✅ データ保存時間 < 2秒
- ✅ 同時接続100ユーザーで安定動作

### ユーザー体験面
- ✅ セッション断絶による履歴消失 0件
- ✅ **キーワード履歴機能の継続性確保**
- ✅ エラー表示の改善
- ✅ 直感的なセッション状態表示

## 📁 ファイル構成（修正版）

### 修正対象ファイル
```
pages/
├── 01_県総_採用試験.py          (修正: セッション管理、練習タイプ統一)
├── 02_小論文.py                (修正: セッション管理、練習タイプ統一)
├── 03_面接.py                  (修正: セッション管理、練習タイプ統一)
├── 05_英語読解.py              (修正: セッション管理、練習タイプ統一)
└── 06_学習履歴.py              (✅ 完了済み)

modules/
├── paper_finder.py             (🚨 重要修正: 履歴関数の新DB対応)
├── database_adapter.py         (追加機能: タイプ別履歴操作)
├── scorer.py                   (修正不要: utils経由で対応済み)
├── essay_scorer.py             (修正不要: utils経由で対応済み)
├── interview_prepper.py        (修正不要: utils経由で対応済み)
├── medical_knowledge_checker.py (修正不要: utils経由で対応済み)
├── database_v2.py              (✅ 完了済み)
├── session_manager.py          (✅ 完了済み)
└── utils.py                    (✅ 完了済み)
```

### 新規作成ファイル
```
docs/
└── pages_modules_refactoring_plan.md  (本ドキュメント・修正版)

tests/ (新規作成)
├── test_paper_finder_history.py       (paper_finder履歴機能テスト)
├── test_pages_integration.py          (ページ統合テスト)
├── test_session_management.py         (セッション管理テスト)
└── test_database_integration.py       (DB統合テスト)
```

## 🎯 次のアクション（修正版）

### 最優先
1. **DatabaseAdapter機能拡張**: `get_practice_history_by_type()`、`delete_practice_history_by_type()`の実装
2. **paper_finder.pyの履歴関数修正**: 最も重要かつ複雑

### 推奨実行順序
1. `modules/database_adapter.py` の機能拡張
2. `modules/paper_finder.py` の履歴関数修正・テスト
3. `pages/02_小論文.py` の修正・テスト（最も単純）
4. `pages/05_英語読解.py` の修正・テスト（01_県総と類似）
5. `pages/01_県総_採用試験.py` の修正・テスト（最も複雑）
6. `pages/03_面接.py` の修正・テスト（状態管理が特殊）
7. 全体統合テスト

---

## 📞 サポート情報

**関連ドキュメント**:
- `docs/database_refactoring_plan.md`: 全体設計
- `docs/technical_specifications.md`: 技術仕様  
- `docs/migration_guide.md`: 移行手順
- `docs/implementation_status.md`: 実装状況

**既存の実装参考**:
- `pages/06_学習履歴.py`: 新DB対応の完成例
- `modules/database_adapter.py`: 互換性レイヤーの実装例
- `modules/session_manager.py`: セッション管理の実装例

**🚨 注意点**: 
この修正版計画では、特に`modules/paper_finder.py`の履歴機能が新DBシステムで正常動作することが成功の鍵となります。DatabaseAdapterの機能拡張とフォールバック実装により、リスクを最小化しながら移行を進めることができます。 

## 🎯 **修正優先順位（検証結果反映版）**

### **Phase 1: 最優先（Week 1）**
1. **DatabaseAdapter機能拡張** (Day 1-2)
   - `get_practice_history_by_type()` 実装
   - `delete_practice_history_by_type()` 実装
   - practice_type IDマッピング作成

2. **modules/paper_finder.py修正** (Day 3-4)
   - 練習タイプ名の統一（4箇所）
   - `get_keyword_history()` 新DB対応
   - `clear_keyword_history()` 新DB対応

### **Phase 2: 中優先（Week 2）**
1. **pages/02_小論文.py** (Day 1) - 最もシンプル
2. **pages/03_面接.py** (Day 2) - 複数タイプ対応
3. **pages/05_英語読解.py** (Day 3) - 01_県総と類似
4. **pages/01_県総_採用試験.py** (Day 4) - 最も複雑

### **検証・統合テスト** (Day 5)

---

**🎯 結論**: 計画は**概ね適切**ですが、**paper_finder.pyの修正が最重要**です。特にキーワード履歴機能の新DB対応とDatabaseAdapterの機能拡張が成功の鍵となります。 