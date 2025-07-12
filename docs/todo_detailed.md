# データベースリファクタリング - 詳細TODO

## 🎯 プロジェクト全体の進行状況

```
進行状況: [■□□□□□□□] 12.5% (1/8 完了)

✅ analyze_current_issues: 現在のデータベース構造とStreamlit Cloud問題の詳細分析 (完了)
🔄 design_new_schema: リレーショナルデータベース設計の詳細スキーマ設計 (進行中)
⏳ create_migration_plan: 既存データの新スキーマへの移行計画作成
⏳ implement_new_database_manager: 新しいスキーマに対応したDatabaseManagerクラスの実装
⏳ fix_session_management: Streamlit Cloudでのセッション管理問題の解決
⏳ update_pages: 各ページファイルの新DatabaseManager対応へのリファクタリング
⏳ data_migration: 既存データの新スキーマへの実際の移行実行
⏳ testing_verification: 移行後の動作確認とテスト
```

---

## 📋 タスク詳細

### ✅ Task 1: analyze_current_issues
**ステータス**: 完了  
**担当**: 分析完了  
**期限**: -

**完了内容**:
- 現在のpractice_historyテーブルの問題点を特定
- Streamlit Cloudでのセッション管理問題を確認  
- コードベースの依存関係を調査
- パフォーマンスボトルネックの特定

**成果物**:
- [x] 問題点リスト (database_refactoring_plan.md)
- [x] 現在のコード分析結果

---

### 🔄 Task 2: design_new_schema (進行中)
**ステータス**: 進行中  
**依存**: analyze_current_issues  
**期限**: 1-2日

**作業内容**:
- [x] ERD設計 (基本設計完了)
- [x] テーブル構造の詳細設計 (基本完了)
- [ ] インデックス戦略の設計
- [ ] 制約・トリガーの設計
- [ ] パフォーマンス最適化案

**詳細サブタスク**:
```
□ インデックス設計
  - session_id, user_id, practice_type_id の複合インデックス
  - created_at でのパーティショニング検討
  - フルテキスト検索インデックス (feedback内容)

□ 制約設計  
  - 外部キー制約
  - CHECK制約 (score_value範囲、status値)
  - UNIQUE制約

□ セキュリティ設計
  - Row Level Security (RLS) 設定
  - ユーザーレベルのアクセス制御
```

**成果物**:
- [x] ERD図
- [x] DDL (CREATE TABLE文)
- [ ] インデックス作成スクリプト
- [ ] 制約・トリガースクリプト

---

### ⏳ Task 3: create_migration_plan
**ステータス**: 待機中  
**依存**: design_new_schema  
**期限**: 2-3日

**作業内容**:
- [ ] データマッピング設計
  - practice_history → 新テーブル群へのマッピング
  - JSONデータの正規化戦略
  - データ検証・クリーニング手順

- [ ] 移行スクリプト作成
  - データ抽出スクリプト (existing → temp)
  - データ変換スクリプト (temp → new schema)
  - ロールバックスクリプト

- [ ] ダウンタイム最小化戦略
  - Blue-Green デプロイメント検討
  - 段階的移行手順
  - バックアップ・復旧手順

**成果物**:
- [ ] migration_script.sql
- [ ] data_mapping_specification.md
- [ ] rollback_procedure.md

---

### ⏳ Task 4: implement_new_database_manager  
**ステータス**: 待機中  
**依存**: design_new_schema  
**期限**: 3-4日

**作業内容**:
- [ ] 新DatabaseManagerV2クラス設計・実装
- [ ] ユーザー管理機能
- [ ] セッション管理機能 (Streamlit Cloud対応)
- [ ] 練習データCRUD操作
- [ ] 統計・分析機能

**詳細サブタスク**:
```
□ ユーザー管理 (UserManager)
  - create_or_get_user()
  - get_user_by_session()
  - update_user_preferences()

□ 練習セッション管理 (PracticeSessionManager)  
  - start_practice_session()
  - save_practice_inputs()
  - save_practice_scores() 
  - complete_practice_session()

□ 履歴管理 (HistoryManager)
  - get_user_practice_history()
  - get_practice_statistics()
  - export_user_data()

□ 統計・分析 (AnalyticsManager)
  - get_score_trends()
  - get_category_performance()
  - get_learning_insights()
```

**成果物**:
- [ ] modules/database_v2.py
- [ ] modules/user_manager.py
- [ ] modules/session_manager.py
- [ ] テストファイル群

---

### ⏳ Task 5: fix_session_management
**ステータス**: 待機中  
**依存**: design_new_schema  
**期限**: 1-2日

**作業内容**:
- [ ] Streamlit Cloud環境でのユーザー識別方法の実装
- [ ] セッションの永続化戦略
- [ ] 複数デバイス対応

**技術選択肢**:
```
Option A: ブラウザのLocal Storage + Cookie
Option B: Streamlit session_state + user_id parameter  
Option C: Simple email-based identification
```

**成果物**:
- [ ] user_identification.py
- [ ] session_persistence.py

---

### ⏳ Task 6: update_pages
**ステータス**: 待機中  
**依存**: implement_new_database_manager  
**期限**: 2-3日

**作業内容**:
- [ ] 各ページファイルの新DatabaseManager対応
- [ ] 履歴表示ロジックの更新
- [ ] エラーハンドリングの改善

**対象ファイル**:
```
□ pages/01_県総_採用試験.py
□ pages/02_小論文.py  
□ pages/03_面接.py
□ pages/04_自由記述.py
□ pages/05_英語読解.py
□ pages/06_学習履歴.py
```

**成果物**:
- [ ] リファクタリングされたページファイル群
- [ ] 共通コンポーネント (components.py)

---

### ⏳ Task 7: data_migration
**ステータス**: 待機中  
**依存**: create_migration_plan + implement_new_database_manager  
**期限**: 1-2日

**作業内容**:
- [ ] Supabaseでの新テーブル作成
- [ ] 既存データの移行実行
- [ ] データ検証・整合性チェック
- [ ] 移行結果レポート作成

**安全策**:
- [ ] フルバックアップ作成
- [ ] 段階的移行実行
- [ ] ロールバック準備

**成果物**:
- [ ] 移行実行ログ
- [ ] データ検証レポート

---

### ⏳ Task 8: testing_verification
**ステータス**: 待機中  
**依存**: data_migration + update_pages  
**期限**: 1-2日

**作業内容**:
- [ ] 機能テスト実行
- [ ] パフォーマンステスト
- [ ] Streamlit Cloud環境での動作確認
- [ ] ユーザー受け入れテスト

**テスト項目**:
```
□ 基本機能テスト
  - 各練習タイプの動作確認
  - 履歴保存・表示確認
  - スコア計算・表示確認

□ 統合テスト
  - ページ間遷移
  - データ整合性
  - エラーハンドリング

□ パフォーマンステスト  
  - 大量データでの動作確認
  - 複数ユーザー同時アクセス
  - レスポンス時間測定

□ Streamlit Cloud特有テスト
  - セッション永続化確認
  - 履歴の継続性確認
  - 複数ブラウザでのテスト
```

**成果物**:
- [ ] テスト結果レポート
- [ ] パフォーマンス測定結果
- [ ] 改善提案リスト

---

## 🚨 リスク管理

### 高リスク項目
1. **データ消失リスク**: 移行時のデータ損失
   - 対策: 完全なバックアップ + 段階的移行
   
2. **ダウンタイム**: サービス停止時間の長期化
   - 対策: Blue-Green デプロイメント + 事前テスト

3. **Streamlit Cloud制約**: 予期しない環境制約
   - 対策: 事前の制約調査 + 代替案準備

### 中リスク項目
1. **パフォーマンス低下**: 新スキーマでの性能問題
   - 対策: 事前のパフォーマンステスト + インデックス最適化

2. **ユーザビリティ**: 新機能の使いにくさ
   - 対策: プロトタイプでの事前検証

---

## 📊 成功指標

### 技術指標
- [ ] 履歴表示エラー: 0件/日
- [ ] レスポンス時間: 500ms以下
- [ ] データ整合性: 100%維持

### ユーザビリティ指標  
- [ ] 学習履歴の継続表示: 100%
- [ ] 新機能の使用率: 80%以上
- [ ] ユーザー満足度: 90%以上

---

## 📅 全体スケジュール（推定）

```
Week 1: design_new_schema + create_migration_plan
Week 2: implement_new_database_manager + fix_session_management  
Week 3: update_pages + data_migration
Week 4: testing_verification + 本番リリース
```

**注意**: スケジュールは現在のタスクの複雑さと依存関係に基づく推定値です。 