# データ移行ガイド

## 概要

このガイドは、既存のSupabase `practice_history` テーブルから新しい正規化されたスキーマへのデータ移行手順を説明します。

## 前提条件

### 1. 環境の準備

- ✅ Supabaseプロジェクトが作成済み
- ✅ 新しいスキーマが `docs/supabase_schema_setup.sql` を使用して作成済み
- ✅ 環境変数の設定:
  - `SUPABASE_URL`: SupabaseプロジェクトのURL
  - `SUPABASE_SERVICE_ROLE_KEY`: サービスロールキー（推奨）または `SUPABASE_ANON_KEY`

### 2. 必要なPythonパッケージ

```bash
pip install supabase
```

### 3. バックアップの作成

**⚠️ 重要: 移行前に必ずデータベースのバックアップを作成してください**

Supabaseダッシュボードから：
1. Settings → Database
2. Database backups からバックアップを作成
3. または手動でデータをエクスポート

## 移行手順

### Step 1: 環境変数の設定

#### Windows (PowerShell)
```powershell
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
```

#### Windows (Command Prompt)
```cmd
set SUPABASE_URL=https://your-project.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

#### macOS/Linux
```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
```

### Step 2: 移行スクリプトの実行

```bash
python migrate_data.py
```

### Step 3: 移行の確認

スクリプト実行後、以下を確認してください：

1. **移行レポートの確認**
   - `migration_report.txt` ファイルが生成されます
   - 移行統計と結果を確認

2. **ログの確認**
   - `migration.log` ファイルでエラーやワーニングを確認

3. **データベースの確認**
   - Supabaseダッシュボードで新しいテーブルにデータが追加されていることを確認

## 移行の詳細

### データ変換マッピング

#### 練習タイプのマッピング

| 旧タイプ | 新タイプキー | カテゴリ |
|---------|------------|----------|
| 採用試験 | medical_exam_comprehensive | comprehensive_exam |
| 過去問スタイル採用試験 - Letter形式 | medical_exam_letter_style | comprehensive_exam |
| 過去問スタイル採用試験 - 論文コメント形式 | medical_exam_comment_style | comprehensive_exam |
| 小論文対策 | essay_practice | essay_writing |
| 面接対策 | interview_practice_general | interview_prep |
| 面接対策(単発) | interview_practice_single | interview_prep |
| 面接対策(セッション) | interview_practice_session | interview_prep |
| 医学部採用試験 自由記述 | medical_knowledge_check | knowledge_check |
| 英語読解 | english_reading_standard | english_reading |
| 過去問スタイル英語読解 - Letter形式 | english_reading_letter_style | english_reading |
| 過去問スタイル英語読解 - 論文コメント形式 | english_reading_comment_style | english_reading |

#### データ構造の変換

**旧スキーマ (practice_history):**
```json
{
  "id": "uuid",
  "practice_type": "採用試験",
  "inputs": {"translation": "...", "opinion": "..."},
  "scores": {"翻訳評価": 8, "意見評価": 7},
  "feedback": "AIからのフィードバック...",
  "date": "2024-01-01T10:00:00Z",
  "duration_seconds": 1800
}
```

**新スキーマ（正規化）:**
- **practice_sessions**: セッション基本情報
- **practice_inputs**: 各入力フィールド
- **practice_scores**: 各スコアカテゴリ
- **practice_feedback**: フィードバックテキスト

### 作成されるデフォルトデータ

1. **デフォルトユーザー**
   - ID: `legacy_user_001`
   - 既存データの移行用ユーザー

2. **練習タイプ**
   - マッピングテーブルに基づいて自動作成
   - 不明な練習タイプはデフォルトタイプに変換

## トラブルシューティング

### よくあるエラーと対処法

#### 1. 環境変数が設定されていない
```
ERROR: SUPABASE_URLとSUPABASE_SERVICE_ROLE_KEY環境変数を設定してください
```
**対処法**: 環境変数を正しく設定してください

#### 2. テーブルが見つからない
```
ERROR: テーブル 'users' が見つかりません
```
**対処法**: `docs/supabase_schema_setup.sql` を実行してスキーマを作成してください

#### 3. 権限エラー
```
ERROR: insufficient privileges
```
**対処法**: SERVICE_ROLE_KEYを使用するか、適切な権限を持つキーを使用してください

#### 4. 接続エラー
```
ERROR: Supabase接続に失敗
```
**対処法**: 
- SUPABASE_URLが正しいか確認
- インターネット接続を確認
- Supabaseプロジェクトがアクティブか確認

### ログレベルの調整

詳細なデバッグ情報が必要な場合、`migrate_data.py` の以下の行を変更：

```python
logging.basicConfig(level=logging.DEBUG)  # INFOからDEBUGに変更
```

## 移行後の確認事項

### 1. データ整合性の確認

```sql
-- セッション数の確認
SELECT COUNT(*) FROM practice_sessions;

-- ユーザー別セッション数
SELECT u.id, COUNT(ps.id) as session_count
FROM users u
LEFT JOIN practice_sessions ps ON u.id = ps.user_id
GROUP BY u.id;

-- 練習タイプ別セッション数
SELECT pt.display_name, COUNT(ps.id) as session_count
FROM practice_types pt
LEFT JOIN practice_sessions ps ON pt.id = ps.practice_type_id
GROUP BY pt.id, pt.display_name
ORDER BY session_count DESC;
```

### 2. アプリケーションでのテスト

1. **学習履歴ページ**: 既存データが表示されることを確認
2. **各練習ページ**: 新しいデータが正常に保存されることを確認
3. **セッション管理**: ユーザー認証とセッション継続を確認

### 3. パフォーマンスの確認

- 新しいインデックスが効いているか確認
- クエリ実行時間の改善を確認
- メモリ使用量の最適化を確認

## ロールバック手順

移行に問題が発生した場合のロールバック手順：

### 1. 新しいテーブルのデータ削除

```sql
-- 外部キー制約の順序に従って削除
DELETE FROM practice_feedback;
DELETE FROM practice_scores;
DELETE FROM practice_inputs;
DELETE FROM practice_sessions;
DELETE FROM practice_types WHERE display_name LIKE '%Migrated from:%';
DELETE FROM users WHERE id = 'legacy_user_001';
```

### 2. バックアップからの復元

Supabaseダッシュボードから事前に作成したバックアップを復元

### 3. アプリケーションの設定変更

必要に応じて古いデータベースシステムに戻す

## 本番環境での注意事項

### 1. メンテナンス時間の設定

- ユーザーへの事前通知
- 適切なメンテナンス時間帯の選択
- 移行時間の見積もり（1000件あたり約5-10分）

### 2. 段階的移行

大量のデータがある場合：

1. **テスト移行**: 少量のデータで事前テスト
2. **部分移行**: 練習タイプ別に段階的に移行
3. **完全移行**: 全データの移行

### 3. 監視とアラート

- 移行プロセスの監視
- エラーアラートの設定
- リソース使用量の監視

## 移行後の最適化

### 1. インデックスの再構築

```sql
-- 統計情報の更新
ANALYZE practice_sessions;
ANALYZE practice_inputs;
ANALYZE practice_scores;
ANALYZE practice_feedback;
```

### 2. 不要なデータの削除

移行が成功し、十分なテスト期間を経た後：

```sql
-- 旧テーブルのバックアップ作成後に削除
-- DROP TABLE practice_history;
```

### 3. 定期メンテナンスの設定

- データベースの定期的なVACUUM
- インデックスの再構築
- 統計情報の更新

## サポートとドキュメント

### 関連ドキュメント

- `docs/database_refactoring_plan.md`: 全体計画
- `docs/technical_specifications.md`: 技術仕様
- `docs/migration_strategy.md`: 移行戦略
- `docs/supabase_schema_setup.sql`: スキーマ定義

### ログとレポート

移行後に生成されるファイル：
- `migration.log`: 詳細な実行ログ
- `migration_report.txt`: 移行結果レポート

問題が発生した場合は、これらのファイルを確認してください。 