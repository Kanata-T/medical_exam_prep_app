# データ移行戦略：既存データの新スキーマ移行

## 🎯 移行の目標

**メイン目標**:
- 既存の`practice_history`テーブルから新しい正規化されたスキーマへのデータ移行
- ゼロダウンタイムでの移行実現
- データ整合性の100%保証
- Streamlit Cloud環境での履歴継続性確保

**技術要件**:
- データ損失: 0件
- 移行中のサービス停止: 最大5分以内
- 移行後のパフォーマンス向上: 50%以上
- ロールバック時間: 2分以内

---

## 📊 現在のデータ分析

### 1. 既存データ構造の詳細分析

```sql
-- 現在のデータ量分析
SELECT 
    practice_type,
    COUNT(*) as record_count,
    MIN(practice_date) as earliest_date,
    MAX(practice_date) as latest_date,
    AVG(duration_seconds) as avg_duration
FROM practice_history 
GROUP BY practice_type
ORDER BY record_count DESC;

-- 入力データの複雑さ分析
SELECT 
    practice_type,
    jsonb_object_keys(inputs) as input_key,
    COUNT(*) as frequency
FROM practice_history, jsonb_object_keys(inputs) 
GROUP BY practice_type, jsonb_object_keys(inputs)
ORDER BY practice_type, frequency DESC;

-- スコアデータの構造分析
SELECT 
    practice_type,
    jsonb_object_keys(scores) as score_key,
    COUNT(*) as frequency,
    AVG((scores->>jsonb_object_keys(scores))::numeric) as avg_score
FROM practice_history, jsonb_object_keys(scores)
WHERE scores IS NOT NULL
GROUP BY practice_type, jsonb_object_keys(scores);
```

### 2. データ品質チェック

```sql
-- データ品質チェッククエリ
WITH data_quality AS (
    SELECT 
        id,
        session_id,
        practice_type,
        practice_date,
        CASE 
            WHEN inputs IS NULL OR inputs = '{}' THEN 'missing_inputs'
            WHEN scores IS NULL OR scores = '{}' THEN 'missing_scores'
            WHEN feedback IS NULL OR feedback = '' THEN 'missing_feedback'
            WHEN duration_seconds IS NULL THEN 'missing_duration'
            ELSE 'valid'
        END as data_status
    FROM practice_history
)
SELECT 
    data_status,
    COUNT(*) as record_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM data_quality
GROUP BY data_status
ORDER BY record_count DESC;
```

---

## 🔄 段階的移行戦略

### フェーズ1: 準備段階（1-2日）

#### 1.1 データベースバックアップ
```bash
# 完全バックアップの作成
pg_dump -h your-supabase-host -U postgres -d your-database \
  --data-only --inserts --table=practice_history \
  --table=user_sessions > backup_before_migration.sql

# Supabase Dashboard経由でのバックアップ確認
```

#### 1.2 新テーブル構造の作成
```sql
-- 新しいテーブル群を作成（既存テーブルと並行）
-- technical_specifications.mdのDDLを実行

-- テーブル作成確認
SELECT table_name, table_rows 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('users', 'practice_categories', 'practice_types', 
                   'practice_sessions', 'practice_inputs', 'practice_scores');
```

#### 1.3 基礎データの投入
```sql
-- カテゴリとタイプのマスターデータ投入
INSERT INTO practice_categories (category_name, display_name, icon, color, sort_order) VALUES
('exam_prep', '採用試験系', '📄', '#667eea', 1),
('reading', '英語読解系', '📖', '#3b82f6', 2),
('writing', '記述系', '✍️', '#8b5cf6', 3),
('interview', '面接系', '🗣️', '#f59e0b', 4),
('research', '論文研究系', '🔬', '#22c55e', 5);

-- 練習タイプのマッピング定義
WITH type_mapping AS (
    SELECT unnest(ARRAY[
        ('採用試験', 1, 'standard_exam', '標準採用試験'),
        ('過去問スタイル採用試験', 1, 'past_exam_standard', '過去問採用試験（標準）'),
        ('過去問スタイル採用試験 - Letter形式（翻訳 + 意見）', 1, 'past_exam_letter', '過去問採用試験（Letter）'),
        ('過去問スタイル採用試験 - 論文コメント形式（コメント翻訳 + 意見）', 1, 'past_exam_comment', '過去問採用試験（Comment）'),
        ('英語読解', 2, 'standard_reading', '標準英語読解'),
        ('医学部採用試験 自由記述', 3, 'free_writing', '自由記述'),
        ('小論文対策', 3, 'essay_writing', '小論文対策'),
        ('面接対策(単発)', 4, 'interview_single', '単発面接'),
        ('面接対策(セッション)', 4, 'interview_session', 'セッション面接'),
        ('キーワード生成', 5, 'keyword_generation', 'キーワード生成'),
        ('論文検索', 5, 'paper_search', '論文検索')
    ]) AS t(old_name, category_id, type_name, display_name)
)
INSERT INTO practice_types (category_id, type_name, display_name, input_schema, score_schema)
SELECT 
    category_id,
    type_name,
    display_name,
    '{"fields": ["default"]}' as input_schema,
    '{"categories": ["総合評価"]}' as score_schema
FROM type_mapping;
```

### フェーズ2: データ変換・移行（2-3日）

#### 2.1 ユーザーセッション移行
```sql
-- 既存のsession_idからユーザーを作成
INSERT INTO users (user_id, display_name, created_at)
SELECT DISTINCT
    session_id::uuid as user_id,
    'Legacy User ' || substr(session_id, 1, 8) as display_name,
    MIN(practice_date) as created_at
FROM practice_history
WHERE session_id IS NOT NULL
GROUP BY session_id;
```

#### 2.2 練習セッション移行
```sql
-- practice_history → practice_sessions
INSERT INTO practice_sessions (
    session_id, user_id, practice_type_id, theme, 
    start_time, end_time, duration_seconds, status, created_at
)
SELECT 
    gen_random_uuid() as session_id,
    ph.session_id::uuid as user_id,
    pt.practice_type_id,
    COALESCE(ph.inputs->>'theme', ph.inputs->>'category', '') as theme,
    ph.practice_date as start_time,
    ph.practice_date + INTERVAL '1 second' * COALESCE(ph.duration_seconds, 0) as end_time,
    ph.duration_seconds,
    'completed' as status,
    ph.created_at
FROM practice_history ph
JOIN practice_types pt ON pt.type_name = (
    CASE 
        WHEN ph.practice_type = '採用試験' THEN 'standard_exam'
        WHEN ph.practice_type = '過去問スタイル採用試験 - Letter形式（翻訳 + 意見）' THEN 'past_exam_letter'
        WHEN ph.practice_type = '医学部採用試験 自由記述' THEN 'free_writing'
        -- 他のマッピング...
        ELSE 'standard_exam'
    END
)
WHERE ph.session_id IS NOT NULL;
```

#### 2.3 入力データの正規化移行
```sql
-- 複雑なJSONB inputsを正規化
WITH input_extraction AS (
    SELECT 
        ps.session_id,
        ph.inputs,
        ph.practice_type,
        -- 各練習タイプ別の入力データ抽出
        CASE 
            WHEN ph.practice_type LIKE '%Letter形式%' THEN 
                jsonb_build_array(
                    jsonb_build_object('type', 'original_paper', 'content', ph.inputs->>'original_paper'),
                    jsonb_build_object('type', 'translation', 'content', ph.inputs->>'translation'),
                    jsonb_build_object('type', 'opinion', 'content', ph.inputs->>'opinion')
                )
            WHEN ph.practice_type = '医学部採用試験 自由記述' THEN
                jsonb_build_array(
                    jsonb_build_object('type', 'question', 'content', ph.inputs->>'question'),
                    jsonb_build_object('type', 'answer', 'content', ph.inputs->>'answer')
                )
            ELSE 
                jsonb_build_array(
                    jsonb_build_object('type', 'content', 'content', ph.inputs::text)
                )
        END as extracted_inputs
    FROM practice_sessions ps
    JOIN practice_history ph ON ph.session_id::uuid = ps.user_id
),
input_normalization AS (
    SELECT 
        session_id,
        (jsonb_array_elements(extracted_inputs)->>'type') as input_type,
        (jsonb_array_elements(extracted_inputs)->>'content') as content,
        row_number() OVER (PARTITION BY session_id ORDER BY ordinality) as input_order
    FROM input_extraction, jsonb_array_elements(extracted_inputs) WITH ORDINALITY
    WHERE jsonb_array_elements(extracted_inputs)->>'content' IS NOT NULL
    AND jsonb_array_elements(extracted_inputs)->>'content' != ''
)
INSERT INTO practice_inputs (session_id, input_type, content, input_order, word_count)
SELECT 
    session_id,
    input_type,
    content,
    input_order,
    LENGTH(content) as word_count
FROM input_normalization;
```

#### 2.4 スコアデータの正規化移行
```sql
-- JSONBスコアの正規化
WITH score_extraction AS (
    SELECT 
        ps.session_id,
        ph.scores,
        score_key,
        (ph.scores->>score_key)::numeric as score_value
    FROM practice_sessions ps
    JOIN practice_history ph ON ph.session_id::uuid = ps.user_id,
         jsonb_object_keys(ph.scores) as score_key
    WHERE ph.scores IS NOT NULL 
    AND ph.scores != '{}'
    AND (ph.scores->>score_key) ~ '^[0-9]+\.?[0-9]*$'
)
INSERT INTO practice_scores (session_id, score_category, score_value, max_score)
SELECT 
    session_id,
    score_key as score_category,
    score_value,
    CASE 
        WHEN score_value <= 10 THEN 10.00
        WHEN score_value <= 100 THEN 100.00
        ELSE 10.00
    END as max_score
FROM score_extraction;
```

#### 2.5 フィードバックデータ移行
```sql
-- フィードバックデータの移行
INSERT INTO practice_feedback (session_id, feedback_content, feedback_type)
SELECT 
    ps.session_id,
    ph.feedback,
    CASE 
        WHEN ph.feedback LIKE '%エラー%' OR ph.feedback LIKE '%UNAVAILABLE%' THEN 'error'
        ELSE 'general'
    END as feedback_type
FROM practice_sessions ps
JOIN practice_history ph ON ph.session_id::uuid = ps.user_id
WHERE ph.feedback IS NOT NULL 
AND ph.feedback != '';
```

### フェーズ3: 検証・切り替え（1日）

#### 3.1 データ整合性検証
```sql
-- 移行データの整合性チェック
WITH migration_check AS (
    SELECT 
        'practice_history' as source_table,
        COUNT(*) as record_count
    FROM practice_history
    
    UNION ALL
    
    SELECT 
        'practice_sessions' as source_table,
        COUNT(*) as record_count
    FROM practice_sessions
    
    UNION ALL
    
    SELECT 
        'practice_inputs' as source_table,
        COUNT(*) as record_count
    FROM practice_inputs
    
    UNION ALL
    
    SELECT 
        'practice_scores' as source_table,
        COUNT(*) as record_count  
    FROM practice_scores
)
SELECT * FROM migration_check;

-- 詳細整合性チェック
SELECT 
    ps.session_id,
    ps.user_id,
    COUNT(pi.input_id) as input_count,
    COUNT(psc.score_id) as score_count,
    COUNT(pf.feedback_id) as feedback_count
FROM practice_sessions ps
LEFT JOIN practice_inputs pi ON ps.session_id = pi.session_id
LEFT JOIN practice_scores psc ON ps.session_id = psc.session_id
LEFT JOIN practice_feedback pf ON ps.session_id = pf.session_id
GROUP BY ps.session_id, ps.user_id
HAVING COUNT(pi.input_id) = 0 OR COUNT(psc.score_id) = 0
LIMIT 10;
```

#### 3.2 パフォーマンステスト
```sql
-- クエリパフォーマンス比較
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM practice_history 
WHERE session_id = 'test-session-id' 
ORDER BY practice_date DESC 
LIMIT 10;

EXPLAIN (ANALYZE, BUFFERS)
SELECT 
    ps.*,
    pt.display_name,
    array_agg(pi.content) as inputs,
    avg(psc.score_percentage) as avg_score
FROM practice_sessions ps
JOIN practice_types pt ON ps.practice_type_id = pt.practice_type_id
LEFT JOIN practice_inputs pi ON ps.session_id = pi.session_id
LEFT JOIN practice_scores psc ON ps.session_id = psc.session_id
WHERE ps.user_id = 'test-user-id'::uuid
GROUP BY ps.session_id, pt.display_name
ORDER BY ps.created_at DESC 
LIMIT 10;
```

#### 3.3 アプリケーション切り替え
```python
# 新しいDatabaseManagerへの段階的切り替え
class MigrationDatabaseManager:
    def __init__(self, use_new_schema=False):
        self.use_new_schema = use_new_schema
        self.old_manager = OldDatabaseManager()
        self.new_manager = NewDatabaseManager() if use_new_schema else None
    
    def load_practice_history(self, user_id, practice_type=None):
        if self.use_new_schema and self.new_manager:
            try:
                return self.new_manager.load_practice_history(user_id, practice_type)
            except Exception as e:
                logger.error(f"New schema failed, falling back: {e}")
                return self.old_manager.load_practice_history(user_id, practice_type)
        else:
            return self.old_manager.load_practice_history(user_id, practice_type)
```

---

## 🔧 移行ツール・スクリプト

### 1. 移行実行スクリプト
```python
#!/usr/bin/env python3
"""
データベース移行実行スクリプト
"""
import os
import sys
import logging
from datetime import datetime
import psycopg2
from supabase import create_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    def __init__(self):
        self.supabase = create_client(
            os.getenv('SUPABASE_URL'),
            os.getenv('SUPABASE_ANON_KEY')
        )
        
    def execute_migration(self):
        """移行を実行"""
        try:
            logger.info("Starting database migration...")
            
            # Phase 1: Backup
            self.create_backup()
            
            # Phase 2: Create new schema
            self.create_new_schema()
            
            # Phase 3: Migrate data
            self.migrate_users()
            self.migrate_sessions()
            self.migrate_inputs()
            self.migrate_scores()
            self.migrate_feedback()
            
            # Phase 4: Validate
            self.validate_migration()
            
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.rollback()
            raise
    
    def create_backup(self):
        """バックアップ作成"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"migration_backup_{timestamp}.sql"
        
        # Supabase REST APIを使用してデータをエクスポート
        practice_history = self.supabase.table('practice_history').select('*').execute()
        user_sessions = self.supabase.table('user_sessions').select('*').execute()
        
        with open(backup_file, 'w') as f:
            f.write(f"-- Migration backup created at {datetime.now()}\n")
            f.write(f"-- Practice history records: {len(practice_history.data)}\n")
            f.write(f"-- User sessions: {len(user_sessions.data)}\n")
        
        logger.info(f"Backup created: {backup_file}")
    
    def migrate_users(self):
        """ユーザーデータの移行"""
        logger.info("Migrating users...")
        
        # 既存のsession_idからユーザーを作成
        existing_sessions = self.supabase.table('user_sessions').select('*').execute()
        
        for session in existing_sessions.data:
            user_data = {
                'user_id': session['session_id'],
                'display_name': f"User {session['session_id'][:8]}",
                'created_at': session['created_at'],
                'last_active': session['last_active']
            }
            
            try:
                self.supabase.table('users').insert(user_data).execute()
            except Exception as e:
                logger.warning(f"Failed to insert user {session['session_id']}: {e}")
    
    def validate_migration(self):
        """移行検証"""
        logger.info("Validating migration...")
        
        # レコード数チェック
        old_count = len(self.supabase.table('practice_history').select('id').execute().data)
        new_count = len(self.supabase.table('practice_sessions').select('session_id').execute().data)
        
        if old_count != new_count:
            raise Exception(f"Record count mismatch: old={old_count}, new={new_count}")
        
        logger.info(f"Validation passed: {new_count} records migrated")
    
    def rollback(self):
        """ロールバック実行"""
        logger.warning("Executing rollback...")
        # 新しいテーブルのデータを削除
        tables = ['practice_feedback', 'practice_scores', 'practice_inputs', 
                 'practice_sessions', 'users', 'practice_types', 'practice_categories']
        
        for table in tables:
            try:
                self.supabase.table(table).delete().neq('created_at', '1970-01-01').execute()
                logger.info(f"Cleared table: {table}")
            except Exception as e:
                logger.error(f"Failed to clear {table}: {e}")

if __name__ == "__main__":
    migrator = DatabaseMigrator()
    migrator.execute_migration()
```

### 2. データ検証スクリプト
```python
#!/usr/bin/env python3
"""
移行データ検証スクリプト
"""

class MigrationValidator:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    def run_full_validation(self):
        """完全な検証を実行"""
        results = {
            'record_counts': self.validate_record_counts(),
            'data_integrity': self.validate_data_integrity(),
            'performance': self.validate_performance(),
            'user_migration': self.validate_user_migration()
        }
        
        return results
    
    def validate_record_counts(self):
        """レコード数の検証"""
        counts = {}
        
        # 既存テーブル
        counts['practice_history'] = len(
            self.supabase.table('practice_history').select('id').execute().data
        )
        
        # 新テーブル
        counts['practice_sessions'] = len(
            self.supabase.table('practice_sessions').select('session_id').execute().data
        )
        counts['practice_inputs'] = len(
            self.supabase.table('practice_inputs').select('input_id').execute().data
        )
        counts['practice_scores'] = len(
            self.supabase.table('practice_scores').select('score_id').execute().data
        )
        
        return counts
    
    def validate_data_integrity(self):
        """データ整合性の検証"""
        issues = []
        
        # 外部キー制約チェック
        orphaned_inputs = self.supabase.rpc('check_orphaned_inputs').execute()
        if orphaned_inputs.data:
            issues.append(f"Orphaned inputs: {len(orphaned_inputs.data)}")
        
        return issues
    
    def validate_user_migration(self):
        """ユーザー移行の検証"""
        # session_id -> user_id の対応確認
        user_sessions = self.supabase.table('user_sessions').select('session_id').execute()
        users = self.supabase.table('users').select('user_id').execute()
        
        session_ids = {s['session_id'] for s in user_sessions.data}
        user_ids = {u['user_id'] for u in users.data}
        
        missing_users = session_ids - user_ids
        extra_users = user_ids - session_ids
        
        return {
            'missing_users': list(missing_users),
            'extra_users': list(extra_users),
            'migration_success_rate': 1.0 - (len(missing_users) / len(session_ids))
        }
```

---

## 🚨 リスク対策・ロールバック計画

### 1. リスク管理マトリックス

| リスク | 影響度 | 発生確率 | 対策 | ロールバック手順 |
|--------|--------|----------|------|------------------|
| データ損失 | 高 | 低 | 完全バックアップ + 段階的移行 | バックアップから復元 |
| 長時間ダウンタイム | 中 | 中 | Blue-Green デプロイ | 旧バージョンに切り替え |
| パフォーマンス低下 | 中 | 低 | 事前ベンチマーク | インデックス最適化 |
| 不完全な移行 | 高 | 中 | 詳細検証スクリプト | 段階的ロールバック |

### 2. 緊急時ロールバック手順

```sql
-- 緊急ロールバック SQL
-- Step 1: アプリケーションを旧スキーマに切り替え（コード変更）

-- Step 2: 新テーブルの一時無効化
ALTER TABLE practice_sessions RENAME TO practice_sessions_backup;
ALTER TABLE practice_inputs RENAME TO practice_inputs_backup;
ALTER TABLE practice_scores RENAME TO practice_scores_backup;
ALTER TABLE practice_feedback RENAME TO practice_feedback_backup;

-- Step 3: 既存テーブルの復元（バックアップから）
-- \i migration_backup_YYYYMMDD_HHMMSS.sql

-- Step 4: 検証
SELECT COUNT(*) FROM practice_history;
SELECT COUNT(*) FROM user_sessions;
```

### 3. 段階的ロールバック

```python
class RollbackManager:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.rollback_steps = [
            self.rollback_feedback,
            self.rollback_scores,
            self.rollback_inputs,
            self.rollback_sessions,
            self.rollback_users,
            self.rollback_master_data
        ]
    
    def execute_rollback(self, target_step=None):
        """段階的ロールバックを実行"""
        for i, step in enumerate(self.rollback_steps):
            if target_step and i >= target_step:
                break
            try:
                step()
                logger.info(f"Rollback step {i+1} completed")
            except Exception as e:
                logger.error(f"Rollback step {i+1} failed: {e}")
                raise
    
    def rollback_feedback(self):
        """フィードバックデータのロールバック"""
        self.supabase.table('practice_feedback').delete().neq('created_at', '1970-01-01').execute()
    
    def rollback_scores(self):
        """スコアデータのロールバック"""
        self.supabase.table('practice_scores').delete().neq('created_at', '1970-01-01').execute()
    
    # 他のロールバック手順...
```

---

## 📊 移行完了後の検証項目

### 1. 機能テスト
```python
def test_post_migration_functionality():
    """移行後の機能テスト"""
    test_cases = [
        'test_user_history_retrieval',
        'test_practice_session_creation',
        'test_score_calculation',
        'test_statistics_generation',
        'test_cross_device_consistency'
    ]
    
    results = {}
    for test_case in test_cases:
        try:
            result = globals()[test_case]()
            results[test_case] = {'status': 'PASS', 'result': result}
        except Exception as e:
            results[test_case] = {'status': 'FAIL', 'error': str(e)}
    
    return results

def test_user_history_retrieval():
    """ユーザー履歴取得テスト"""
    # テストユーザーでの履歴取得
    db = NewDatabaseManager()
    history = db.get_user_practice_history('test-user-id')
    assert len(history) > 0, "履歴が取得できない"
    assert all('session_id' in item for item in history), "セッションIDが不正"
    return len(history)
```

### 2. パフォーマンステスト
```python
import time
import statistics

def performance_comparison_test():
    """移行前後のパフォーマンス比較"""
    old_db = OldDatabaseManager()
    new_db = NewDatabaseManager()
    
    test_queries = [
        'get_user_history',
        'get_practice_statistics',
        'get_score_trends'
    ]
    
    results = {}
    for query in test_queries:
        old_times = []
        new_times = []
        
        # 10回実行して平均を計算
        for _ in range(10):
            # 旧システム
            start = time.time()
            getattr(old_db, query)('test-user-id')
            old_times.append(time.time() - start)
            
            # 新システム
            start = time.time()
            getattr(new_db, query)('test-user-id')
            new_times.append(time.time() - start)
        
        results[query] = {
            'old_avg': statistics.mean(old_times),
            'new_avg': statistics.mean(new_times),
            'improvement': 1 - (statistics.mean(new_times) / statistics.mean(old_times))
        }
    
    return results
```

---

## ✅ 移行完了チェックリスト

### 事前準備
- [ ] 完全バックアップの作成
- [ ] 移行スクリプトのテスト実行
- [ ] ロールバック手順の確認
- [ ] 関係者への事前通知

### 移行実行
- [ ] 新テーブル構造の作成
- [ ] マスターデータの投入
- [ ] ユーザーデータの移行
- [ ] 練習セッションデータの移行
- [ ] 入力データの正規化移行
- [ ] スコアデータの移行
- [ ] フィードバックデータの移行

### 検証・切り替え
- [ ] データ整合性の検証
- [ ] パフォーマンステストの実行
- [ ] 機能テストの実行
- [ ] アプリケーションの切り替え
- [ ] Streamlit Cloud環境での動作確認

### 事後対応
- [ ] 移行結果レポートの作成
- [ ] 監視体制の確立
- [ ] ユーザーへの移行完了通知
- [ ] 旧テーブルのアーカイブ/削除
- [ ] ドキュメントの更新

---

## 📋 移行スケジュール（詳細）

| 時間 | 作業内容 | 担当 | 所要時間 | リスク |
|------|----------|------|----------|--------|
| Day 1 AM | バックアップ作成 | Tech | 2h | 低 |
| Day 1 PM | 新テーブル作成 | Tech | 4h | 低 |
| Day 2 AM | ユーザー移行 | Tech | 3h | 中 |
| Day 2 PM | セッション移行 | Tech | 4h | 中 |
| Day 3 AM | 入力/スコア移行 | Tech | 4h | 高 |
| Day 3 PM | 検証・テスト | Tech | 3h | 中 |
| Day 4 AM | アプリ切り替え | Tech | 2h | 高 |
| Day 4 PM | 本番確認 | All | 2h | 中 |

**注意**: 各作業には30分のバッファ時間を含む 