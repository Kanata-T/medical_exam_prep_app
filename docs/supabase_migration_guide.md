# Supabase データベース対応ガイド

## 🎯 概要

アプリケーションが新しい練習タイプフォーマットに対応したため、Supabase側のデータベーススキーマも同様に更新する必要があります。

## ⚠️ 重要な注意事項

- **データ損失を防ぐため、必ず事前にバックアップを取ってください**
- 実行前に本番環境以外での検証を推奨します
- 手順は順番通りに実行してください

## 🔍 現在の状況

### アプリケーション側（対応済み）
新しい練習タイプマッピング：
- `essay_practice` (小論文)
- `interview_practice_single`、`interview_practice_session` (面接)
- `english_reading_standard`、`english_reading_*` (英語読解)
- `medical_exam_comprehensive`、`medical_exam_*` (医学部採用試験)
- `free_writing` (自由記述)

### Supabase側（要更新）
既存の練習タイプ：
- `essay_writing` → `essay_practice` に変更が必要
- `interview_single` → `interview_practice_single` に変更が必要
- `standard_reading` → `english_reading_standard` に変更が必要
- など

## 📋 実行手順

### ステップ1: 現在のデータベースのバックアップ

```sql
-- 1. Supabaseダッシュボードの「Database」→「Backups」でスナップショットを作成
-- 2. または手動バックアップSQL実行：

CREATE TABLE practice_history_backup_$(date +%Y%m%d) AS 
SELECT * FROM practice_history;

CREATE TABLE practice_types_backup_$(date +%Y%m%d) AS 
SELECT * FROM practice_types;

CREATE TABLE user_sessions_backup_$(date +%Y%m%d) AS 
SELECT * FROM user_sessions;
```

### ステップ2: 新しいスキーマの作成

**注意**: 初回セットアップの場合のみ実行してください。

```sql
-- docs/supabase_schema_setup.sql の内容を実行
-- Supabaseダッシュボード → Database → SQL Editor で実行
```

### ステップ3: 練習タイプの更新

```sql
-- docs/supabase_update_practice_types.sql の内容を実行
-- Supabaseダッシュボード → Database → SQL Editor で実行
```

### ステップ4: 更新結果の確認

```sql
-- 練習タイプが正しく更新されているかチェック
SELECT type_name, display_name, is_active 
FROM practice_types 
WHERE type_name IN (
    'essay_practice',
    'interview_practice_single', 
    'interview_practice_session',
    'english_reading_standard',
    'english_reading_letter_style',
    'english_reading_comment_style',
    'medical_exam_comprehensive',
    'medical_exam_letter_style',
    'medical_exam_comment_style',
    'free_writing'
)
ORDER BY type_name;

-- 期待される結果：上記10個の練習タイプがすべて表示される
```

### ステップ5: 既存データの整合性確認

```sql
-- 練習履歴データで使用されている練習タイプを確認
SELECT DISTINCT practice_type, COUNT(*) as count
FROM practice_history 
GROUP BY practice_type
ORDER BY practice_type;

-- 新しい練習タイプとの対応関係を確認
```

## 🚨 トラブルシューティング

### Q1: 練習タイプの更新でエラーが発生した場合

```sql
-- エラーの詳細を確認
SELECT constraint_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'practice_types';

-- 制約を一時的に無効化してから再実行
ALTER TABLE practice_types DISABLE TRIGGER ALL;
-- 更新SQL実行
ALTER TABLE practice_types ENABLE TRIGGER ALL;
```

### Q2: 既存データとの互換性問題

```sql
-- 旧練習タイプを使用している履歴データを確認
SELECT practice_type, COUNT(*) 
FROM practice_history 
WHERE practice_type NOT IN (
    SELECT type_name FROM practice_types
)
GROUP BY practice_type;
```

### Q3: RLS（Row Level Security）ポリシーエラー

```sql
-- RLSポリシーを一時的に無効化
ALTER TABLE practice_types DISABLE ROW LEVEL SECURITY;
-- 更新実行後
ALTER TABLE practice_types ENABLE ROW LEVEL SECURITY;
```

## ✅ 検証手順

### データベース側検証

```sql
-- 1. 必要な練習タイプがすべて存在することを確認
WITH required_types AS (
    SELECT unnest(ARRAY[
        'essay_practice', 'interview_practice_single', 'interview_practice_session',
        'english_reading_standard', 'english_reading_letter_style', 'english_reading_comment_style',
        'medical_exam_comprehensive', 'medical_exam_letter_style', 'medical_exam_comment_style',
        'free_writing'
    ]) as type_name
)
SELECT 
    rt.type_name,
    CASE WHEN pt.type_name IS NOT NULL THEN '✅' ELSE '❌' END as exists
FROM required_types rt
LEFT JOIN practice_types pt ON rt.type_name = pt.type_name;

-- 2. テーブル構造の確認
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('practice_types', 'practice_categories', 'practice_sessions')
ORDER BY table_name, ordinal_position;
```

### アプリケーション側検証

1. **Streamlitアプリを起動**
2. **各ページで新しい練習を実行**：
   - 小論文ページ → `essay_practice`で保存されるか
   - 面接ページ → `interview_practice_*`で保存されるか
   - 英語読解ページ → `english_reading_*`で保存されるか
   - 県総採用試験ページ → `medical_exam_*`で保存されるか
   - 自由記述v2ページ → `free_writing`で保存されるか

3. **学習履歴ページで履歴が正しく表示されるか確認**

## 📊 期待される結果

### ✅ 成功時の状態
- 全16種類の練習タイプが`practice_types`テーブルに存在
- 新しい練習データが適切な練習タイプで保存される
- 学習履歴が正しく表示される
- セッション管理が正常に動作する

### ❌ 失敗時の症状
- 新しい練習データが保存されない
- 練習タイプエラーが発生する
- 履歴ページでデータが表示されない

## 🔄 ロールバック手順

問題が発生した場合：

```sql
-- 1. バックアップからの復元
DROP TABLE IF EXISTS practice_types;
CREATE TABLE practice_types AS SELECT * FROM practice_types_backup_YYYYMMDD;

-- 2. アプリケーション設定の一時的な変更
-- modules/database_adapter.py で旧マッピングに戻す

-- 3. 問題解決後に再実行
```

## 📞 サポート情報

### ログ確認場所
- Supabase Dashboard → Logs
- Streamlit アプリのコンソール出力

### よくある問題
1. **権限エラー**: SupabaseのService Roleキーを使用
2. **制約エラー**: 既存データとの整合性を確認
3. **接続エラー**: SUPABASE_URLとSUPABASE_ANON_KEYを確認

---

## 🚀 最終チェックリスト

実行前に以下を確認してください：

- [ ] バックアップ作成済み
- [ ] 本番環境でない場合は検証環境で実行済み
- [ ] Supabaseの権限が適切に設定されている
- [ ] アプリケーション側が最新版になっている

実行後に以下を確認してください：

- [ ] 16種類の練習タイプが存在する
- [ ] 新しい練習データが保存される
- [ ] 履歴が正しく表示される
- [ ] エラーメッセージが表示されない

すべてチェックが完了したら、新システムでの運用開始です！ 🎉 