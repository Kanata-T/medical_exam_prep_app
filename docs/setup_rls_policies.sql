-- RLSポリシー設定スクリプト
-- 医療試験準備アプリの新しいデータベース設計用

-- ========================================
-- Row Level Securityの有効化
-- ========================================

-- ユーザー管理テーブル
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- 演習カテゴリー・タイプテーブル
ALTER TABLE exercise_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_types ENABLE ROW LEVEL SECURITY;

-- 演習セッション関連テーブル
ALTER TABLE exercise_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_feedback ENABLE ROW LEVEL SECURITY;

-- カテゴリー別履歴テーブル
ALTER TABLE category_keyword_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_paper_search_history ENABLE ROW LEVEL SECURITY;

-- ユーザー統計・ログテーブル
ALTER TABLE user_statistics ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_activity_log ENABLE ROW LEVEL SECURITY;

-- ========================================
-- ポリシーの作成
-- ========================================

-- ユーザー管理ポリシー
CREATE POLICY "Users can manage own data" ON users 
FOR ALL USING (auth.uid() = user_id);

-- 演習セッション管理ポリシー
CREATE POLICY "Users can manage own sessions" ON exercise_sessions 
FOR ALL USING (auth.uid() = user_id);

-- 演習入力管理ポリシー
CREATE POLICY "Users can manage own inputs" ON exercise_inputs 
FOR ALL USING (
    session_id IN (
        SELECT session_id 
        FROM exercise_sessions 
        WHERE user_id = auth.uid()
    )
);

-- 演習スコア管理ポリシー
CREATE POLICY "Users can manage own scores" ON exercise_scores 
FOR ALL USING (
    session_id IN (
        SELECT session_id 
        FROM exercise_sessions 
        WHERE user_id = auth.uid()
    )
);

-- 演習フィードバック管理ポリシー
CREATE POLICY "Users can manage own feedback" ON exercise_feedback 
FOR ALL USING (
    session_id IN (
        SELECT session_id 
        FROM exercise_sessions 
        WHERE user_id = auth.uid()
    )
);

-- カテゴリー別キーワード履歴管理ポリシー
CREATE POLICY "Users can manage own keyword history" ON category_keyword_history 
FOR ALL USING (auth.uid() = user_id);

-- カテゴリー別論文検索履歴管理ポリシー
CREATE POLICY "Users can manage own paper search history" ON category_paper_search_history 
FOR ALL USING (auth.uid() = user_id);

-- 一時的なユーザーID用の履歴ポリシー（開発用）
CREATE POLICY "Temporary users can manage keyword history" ON category_keyword_history 
FOR ALL USING (user_id::text LIKE 'temp_%');

CREATE POLICY "Temporary users can manage paper search history" ON category_paper_search_history 
FOR ALL USING (user_id::text LIKE 'temp_%');

-- ユーザー統計管理ポリシー
CREATE POLICY "Users can manage own statistics" ON user_statistics 
FOR ALL USING (auth.uid() = user_id);

-- ユーザーアクティビティログ管理ポリシー
CREATE POLICY "Users can manage own activity log" ON user_activity_log 
FOR ALL USING (auth.uid() = user_id);

-- 一時的なユーザーID用のアクティビティログポリシー（開発用）
CREATE POLICY "Temporary users can manage activity log" ON user_activity_log 
FOR ALL USING (user_id::text LIKE 'temp_%');

-- ========================================
-- 読み取り専用ポリシー（カテゴリーとタイプ）
-- ========================================

-- 演習カテゴリー読み取りポリシー
CREATE POLICY "Anyone can read categories" ON exercise_categories 
FOR SELECT USING (true);

-- 演習タイプ読み取りポリシー
CREATE POLICY "Anyone can read exercise types" ON exercise_types 
FOR SELECT USING (true);

-- ========================================
-- 匿名ユーザー対応ポリシー（開発用）
-- ========================================

-- 匿名ユーザー用のポリシー（開発・テスト用）
CREATE POLICY "Anonymous users can read categories" ON exercise_categories 
FOR SELECT USING (true);

CREATE POLICY "Anonymous users can read exercise types" ON exercise_types 
FOR SELECT USING (true);

-- 匿名ユーザー用のセッション作成ポリシー
CREATE POLICY "Anonymous users can create sessions" ON exercise_sessions 
FOR INSERT WITH CHECK (true);

CREATE POLICY "Anonymous users can manage own sessions" ON exercise_sessions 
FOR ALL USING (true);

-- 匿名ユーザー用の入力管理ポリシー
CREATE POLICY "Anonymous users can manage inputs" ON exercise_inputs 
FOR ALL USING (true);

-- 匿名ユーザー用のスコア管理ポリシー
CREATE POLICY "Anonymous users can manage scores" ON exercise_scores 
FOR ALL USING (true);

-- 匿名ユーザー用のフィードバック管理ポリシー
CREATE POLICY "Anonymous users can manage feedback" ON exercise_feedback 
FOR ALL USING (true);

-- ========================================
-- 確認クエリ
-- ========================================

-- ポリシーの確認
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
ORDER BY tablename, policyname;

-- RLSが有効なテーブルの確認
SELECT 
    schemaname,
    tablename,
    rowsecurity
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN (
    'users', 'exercise_categories', 'exercise_types', 'exercise_sessions',
    'exercise_inputs', 'exercise_scores', 'exercise_feedback',
    'category_keyword_history', 'category_paper_search_history',
    'user_statistics', 'user_activity_log'
)
ORDER BY tablename; 