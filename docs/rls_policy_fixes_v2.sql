-- RLSポリシー修正スクリプト v2
-- 登録済みユーザーのアクティビティログ記録対応

-- ========================================
-- 既存ポリシーの確認
-- ========================================

-- 現在のポリシーを確認
SELECT 
    schemaname, 
    tablename, 
    policyname, 
    permissive, 
    roles, 
    cmd, 
    qual 
FROM pg_policies 
WHERE schemaname = 'public'
AND tablename = 'user_activity_log'
ORDER BY policyname;

-- ========================================
-- 既存ポリシーの削除（user_activity_log）
-- ========================================

-- 既存のuser_activity_logポリシーを削除
DROP POLICY IF EXISTS "Users can manage own activity log" ON user_activity_log;
DROP POLICY IF EXISTS "Temporary users can manage activity log" ON user_activity_log;

-- ========================================
-- 新しいポリシーの作成（user_activity_log）
-- ========================================

-- アプリケーション管理ユーザー用のポリシー（UUID形式のユーザーID）
CREATE POLICY "Application users can manage activity log" ON user_activity_log 
FOR ALL USING (
    -- UUID形式のユーザーID（登録済みユーザー）
    (user_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    OR
    -- 一時的なユーザーID
    (user_id::text LIKE 'temp_%')
);

-- ========================================
-- 他のテーブルも同様に修正
-- ========================================

-- exercise_sessions
DROP POLICY IF EXISTS "Users can manage own sessions" ON exercise_sessions;
DROP POLICY IF EXISTS "Temporary users can manage sessions" ON exercise_sessions;

CREATE POLICY "Application users can manage sessions" ON exercise_sessions 
FOR ALL USING (
    (user_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    OR
    (user_id::text LIKE 'temp_%')
);

-- exercise_inputs
DROP POLICY IF EXISTS "Users can manage own inputs" ON exercise_inputs;
DROP POLICY IF EXISTS "Temporary users can manage inputs" ON exercise_inputs;

CREATE POLICY "Application users can manage inputs" ON exercise_inputs 
FOR ALL USING (
    session_id IN (
        SELECT session_id 
        FROM exercise_sessions 
        WHERE (user_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
        OR (user_id::text LIKE 'temp_%')
    )
);

-- exercise_scores
DROP POLICY IF EXISTS "Users can manage own scores" ON exercise_scores;
DROP POLICY IF EXISTS "Temporary users can manage scores" ON exercise_scores;

CREATE POLICY "Application users can manage scores" ON exercise_scores 
FOR ALL USING (
    session_id IN (
        SELECT session_id 
        FROM exercise_sessions 
        WHERE (user_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
        OR (user_id::text LIKE 'temp_%')
    )
);

-- exercise_feedback
DROP POLICY IF EXISTS "Users can manage own feedback" ON exercise_feedback;
DROP POLICY IF EXISTS "Temporary users can manage feedback" ON exercise_feedback;

CREATE POLICY "Application users can manage feedback" ON exercise_feedback 
FOR ALL USING (
    session_id IN (
        SELECT session_id 
        FROM exercise_sessions 
        WHERE (user_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
        OR (user_id::text LIKE 'temp_%')
    )
);

-- category_keyword_history
DROP POLICY IF EXISTS "Users can manage own keyword history" ON category_keyword_history;
DROP POLICY IF EXISTS "Temporary users can manage keyword history" ON category_keyword_history;

CREATE POLICY "Application users can manage keyword history" ON category_keyword_history 
FOR ALL USING (
    (user_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    OR
    (user_id::text LIKE 'temp_%')
);

-- category_paper_search_history
DROP POLICY IF EXISTS "Users can manage own paper search history" ON category_paper_search_history;
DROP POLICY IF EXISTS "Temporary users can manage paper search history" ON category_paper_search_history;

CREATE POLICY "Application users can manage paper search history" ON category_paper_search_history 
FOR ALL USING (
    (user_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    OR
    (user_id::text LIKE 'temp_%')
);

-- user_statistics
DROP POLICY IF EXISTS "Users can manage own statistics" ON user_statistics;
DROP POLICY IF EXISTS "Temporary users can manage statistics" ON user_statistics;

CREATE POLICY "Application users can manage statistics" ON user_statistics 
FOR ALL USING (
    (user_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    OR
    (user_id::text LIKE 'temp_%')
);

-- ========================================
-- 確認クエリ
-- ========================================

-- 修正後のポリシーを確認
SELECT 
    schemaname, 
    tablename, 
    policyname, 
    permissive, 
    roles, 
    cmd, 
    qual 
FROM pg_policies 
WHERE schemaname = 'public'
AND tablename IN (
    'user_activity_log', 'category_keyword_history', 'category_paper_search_history',
    'exercise_sessions', 'exercise_inputs', 'exercise_scores', 'exercise_feedback',
    'user_statistics'
)
ORDER BY tablename, policyname;

-- ========================================
-- アプリケーションユーザーポリシーの確認
-- ========================================

-- アプリケーション管理ユーザー用のポリシーのみを確認
SELECT 
    tablename, 
    policyname, 
    qual 
FROM pg_policies 
WHERE schemaname = 'public'
AND policyname LIKE '%Application%'
ORDER BY tablename, policyname; 