-- 演習カテゴリー別キーワード生成・論文検索管理データベーススキーマ（修正版）
-- 採用試験(1)、小論文(2)、面接(3)、自由記述(4)、英語読解(5)の5カテゴリーで管理
-- 現状のSupabaseに完全に新しいスキーマを作成

-- ========================================
-- 1. ユーザー管理テーブル
-- ========================================

-- ユーザーテーブル（認証・基本情報）
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    browser_fingerprint VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    password_reset_token VARCHAR(255),
    password_reset_expires TIMESTAMP WITH TIME ZONE,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    avatar_url TEXT,
    bio TEXT,
    timezone VARCHAR(50) DEFAULT 'Asia/Tokyo',
    language VARCHAR(10) DEFAULT 'ja',
    email_verified BOOLEAN DEFAULT FALSE,
    email_verification_token VARCHAR(255),
    account_status VARCHAR(20) DEFAULT 'active' 
        CHECK (account_status IN ('active', 'inactive', 'suspended', 'pending_verification')),
    terms_accepted BOOLEAN DEFAULT FALSE,
    terms_accepted_at TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE,
    login_attempts INTEGER DEFAULT 0,
    account_locked_until TIMESTAMP WITH TIME ZONE,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- ========================================
-- 2. 演習カテゴリーテーブル（1-5で管理）
-- ========================================

-- 演習カテゴリーテーブル
CREATE TABLE exercise_categories (
    category_id INTEGER PRIMARY KEY CHECK (category_id BETWEEN 1 AND 5),
    category_name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(20),
    color VARCHAR(7),
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- 3. 演習タイプテーブル（カテゴリー別）
-- ========================================

-- 演習タイプテーブル
CREATE TABLE exercise_types (
    exercise_type_id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES exercise_categories(category_id),
    type_name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(150) NOT NULL,
    description TEXT,
    input_schema JSONB DEFAULT '{}',
    score_schema JSONB DEFAULT '{}',
    difficulty_level INTEGER DEFAULT 1 CHECK (difficulty_level BETWEEN 1 AND 5),
    estimated_duration_minutes INTEGER DEFAULT 30,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- 4. 演習セッション管理
-- ========================================

-- 演習セッションテーブル
CREATE TABLE exercise_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    exercise_type_id INTEGER NOT NULL REFERENCES exercise_types(exercise_type_id),
    theme VARCHAR(200),
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    status VARCHAR(20) DEFAULT 'in_progress' 
        CHECK (status IN ('in_progress', 'completed', 'abandoned', 'error')),
    completion_percentage DECIMAL(5,2) DEFAULT 0.00,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- 5. 演習入力・回答データ
-- ========================================

-- 演習入力テーブル
CREATE TABLE exercise_inputs (
    input_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES exercise_sessions(session_id) ON DELETE CASCADE,
    input_type VARCHAR(50) NOT NULL, -- 'original_paper', 'translation', 'opinion', 'theme', 'question', 'answer' など
    content TEXT NOT NULL,
    word_count INTEGER DEFAULT 0,
    input_order INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- 6. LLM添削・評価結果
-- ========================================

-- LLM評価スコアテーブル
CREATE TABLE exercise_scores (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES exercise_sessions(session_id) ON DELETE CASCADE,
    score_category VARCHAR(50) NOT NULL, -- '翻訳評価', '意見評価', '総合評価', '理解度', '翻訳精度' など
    score_value DECIMAL(5,2) NOT NULL CHECK (score_value >= 0),
    max_score DECIMAL(5,2) NOT NULL DEFAULT 10.00 CHECK (max_score > 0),
    weight DECIMAL(3,2) DEFAULT 1.00,
    feedback TEXT,
    ai_model VARCHAR(50),
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- LLM添削フィードバックテーブル
CREATE TABLE exercise_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES exercise_sessions(session_id) ON DELETE CASCADE,
    feedback_content TEXT NOT NULL,
    feedback_type VARCHAR(20) DEFAULT 'general' 
        CHECK (feedback_type IN ('general', 'improvement', 'strong_point', 'error', 'correction')),
    ai_model VARCHAR(50),
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- 7. カテゴリー別キーワード生成履歴
-- ========================================

-- カテゴリー別キーワード生成履歴テーブル
CREATE TABLE category_keyword_history (
    keyword_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES exercise_categories(category_id),
    session_id UUID REFERENCES exercise_sessions(session_id) ON DELETE CASCADE,
    input_text TEXT NOT NULL,
    generated_keywords TEXT[] NOT NULL,
    category VARCHAR(100), -- キーワードのカテゴリ
    rationale TEXT, -- 生成理由
    ai_model VARCHAR(50),
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- 8. カテゴリー別論文検索履歴
-- ========================================

-- カテゴリー別論文検索履歴テーブル
CREATE TABLE category_paper_search_history (
    search_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES exercise_categories(category_id),
    session_id UUID REFERENCES exercise_sessions(session_id) ON DELETE CASCADE,
    search_query TEXT NOT NULL,
    search_keywords TEXT[],
    search_results JSONB NOT NULL,
    selected_papers JSONB,
    purpose TEXT, -- 検索目的
    ai_model VARCHAR(50),
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- 9. ユーザー統計・分析
-- ========================================

-- ユーザー統計テーブル
CREATE TABLE user_statistics (
    stat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES exercise_categories(category_id),
    total_sessions INTEGER DEFAULT 0,
    total_duration_seconds INTEGER DEFAULT 0,
    average_score DECIMAL(5,2),
    best_score DECIMAL(5,2),
    latest_session_date TIMESTAMP WITH TIME ZONE,
    streak_days INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, category_id)
);

-- ========================================
-- 10. アクティビティログ
-- ========================================

-- ユーザーアクティビティログテーブル
CREATE TABLE user_activity_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    activity_type VARCHAR(50) NOT NULL,
    activity_description TEXT,
    session_id UUID REFERENCES exercise_sessions(session_id),
    category_id INTEGER REFERENCES exercise_categories(category_id),
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ========================================
-- 11. インデックス作成
-- ========================================

-- ユーザー関連インデックス
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX idx_users_browser_fingerprint ON users(browser_fingerprint) WHERE browser_fingerprint IS NOT NULL;
CREATE INDEX idx_users_active ON users(is_active, last_active DESC);

-- 演習セッション関連インデックス
CREATE INDEX idx_exercise_sessions_user_history 
ON exercise_sessions(user_id, created_at DESC, status) 
INCLUDE (exercise_type_id, theme, duration_seconds);

CREATE INDEX idx_exercise_sessions_type_history 
ON exercise_sessions(exercise_type_id, user_id, created_at DESC) 
INCLUDE (status, completion_percentage);

-- 演習入力関連インデックス
CREATE INDEX idx_exercise_inputs_session 
ON exercise_inputs(session_id, input_order) 
INCLUDE (input_type, content);

-- スコア・フィードバック関連インデックス
CREATE INDEX idx_exercise_scores_session 
ON exercise_scores(session_id, score_category) 
INCLUDE (score_value, created_at);

CREATE INDEX idx_exercise_feedback_session 
ON exercise_feedback(session_id, feedback_type) 
INCLUDE (created_at);

-- カテゴリー別キーワード・論文検索履歴インデックス
CREATE INDEX idx_category_keyword_user_category 
ON category_keyword_history(user_id, category_id, created_at DESC);

CREATE INDEX idx_category_paper_search_user_category 
ON category_paper_search_history(user_id, category_id, created_at DESC);

-- ユーザー統計関連インデックス
CREATE INDEX idx_user_statistics_user_category 
ON user_statistics(user_id, category_id);

-- アクティビティログ関連インデックス
CREATE INDEX idx_user_activity_log_user_time 
ON user_activity_log(user_id, created_at DESC);

CREATE INDEX idx_user_activity_log_category 
ON user_activity_log(category_id, created_at DESC);

-- 演習タイプ関連インデックス
CREATE INDEX idx_exercise_types_category 
ON exercise_types(category_id, sort_order);

-- ========================================
-- 12. トリガー・関数
-- ========================================

-- ユーザーの最終アクティブ時間更新関数
CREATE OR REPLACE FUNCTION update_user_last_active()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE users 
    SET last_active = NOW() 
    WHERE user_id = NEW.user_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ユーザー最終アクティブ時間更新トリガー
CREATE TRIGGER trigger_update_user_last_active
    AFTER INSERT OR UPDATE ON exercise_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_user_last_active();

-- ユーザー統計更新関数
CREATE OR REPLACE FUNCTION update_user_statistics()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_statistics (user_id, category_id, total_sessions, 
                               total_duration_seconds, average_score, best_score, 
                               latest_session_date, last_updated)
    VALUES (NEW.user_id, 
            (SELECT category_id FROM exercise_types WHERE exercise_type_id = NEW.exercise_type_id), 
            1, 
            COALESCE(NEW.duration_seconds, 0), NULL, NULL, 
            NEW.start_time, NOW())
    ON CONFLICT (user_id, category_id) 
    DO UPDATE SET
        total_sessions = user_statistics.total_sessions + 1,
        total_duration_seconds = user_statistics.total_duration_seconds + COALESCE(NEW.duration_seconds, 0),
        latest_session_date = GREATEST(user_statistics.latest_session_date, NEW.start_time),
        last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ユーザー統計更新トリガー
CREATE TRIGGER trigger_update_user_statistics
    AFTER INSERT ON exercise_sessions
    FOR EACH ROW
    WHEN (NEW.status = 'completed')
    EXECUTE FUNCTION update_user_statistics();

-- ========================================
-- 13. ビュー作成
-- ========================================

-- 演習セッション詳細ビュー
CREATE OR REPLACE VIEW exercise_session_details AS
SELECT 
    es.session_id,
    es.user_id,
    u.display_name,
    ec.category_id,
    ec.display_name as category_name,
    et.exercise_type_id,
    et.display_name as exercise_type_name,
    es.theme,
    es.start_time,
    es.end_time,
    es.duration_seconds,
    es.status,
    es.completion_percentage,
    es.created_at
FROM exercise_sessions es
JOIN users u ON es.user_id = u.user_id
JOIN exercise_types et ON es.exercise_type_id = et.exercise_type_id
JOIN exercise_categories ec ON et.category_id = ec.category_id;

-- カテゴリー別統計ビュー
CREATE OR REPLACE VIEW category_statistics AS
SELECT 
    us.user_id,
    u.display_name,
    us.category_id,
    ec.display_name as category_name,
    us.total_sessions,
    us.total_duration_seconds,
    us.average_score,
    us.best_score,
    us.latest_session_date,
    us.streak_days,
    us.last_updated
FROM user_statistics us
JOIN users u ON us.user_id = u.user_id
JOIN exercise_categories ec ON us.category_id = ec.category_id;

-- ========================================
-- 14. RLSポリシー（セキュリティ）
-- ========================================

-- RLS有効化
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_keyword_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_paper_search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_statistics ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_activity_log ENABLE ROW LEVEL SECURITY;

-- ユーザー自身のデータのみアクセス可能
CREATE POLICY "Users can view own data" ON users FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can update own data" ON users FOR UPDATE USING (auth.uid() = user_id);

-- 演習カテゴリー・タイプは全ユーザーが閲覧可能
CREATE POLICY "Anyone can view exercise categories" ON exercise_categories FOR SELECT USING (true);
CREATE POLICY "Anyone can view exercise types" ON exercise_types FOR SELECT USING (true);

-- 演習セッション関連
CREATE POLICY "Users can manage own sessions" ON exercise_sessions FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own inputs" ON exercise_inputs FOR ALL USING (
    session_id IN (SELECT session_id FROM exercise_sessions WHERE user_id = auth.uid())
);
CREATE POLICY "Users can manage own scores" ON exercise_scores FOR ALL USING (
    session_id IN (SELECT session_id FROM exercise_sessions WHERE user_id = auth.uid())
);
CREATE POLICY "Users can manage own feedback" ON exercise_feedback FOR ALL USING (
    session_id IN (SELECT session_id FROM exercise_sessions WHERE user_id = auth.uid())
);

-- カテゴリー別履歴
CREATE POLICY "Users can manage own keyword history" ON category_keyword_history FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users can manage own paper search history" ON category_paper_search_history FOR ALL USING (auth.uid() = user_id);

-- ユーザー統計・アクティビティログ
CREATE POLICY "Users can view own statistics" ON user_statistics FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can view own activity log" ON user_activity_log FOR SELECT USING (auth.uid() = user_id);

-- ========================================
-- 15. 初期データ挿入
-- ========================================

-- 演習カテゴリーの初期データ（1-5で管理）
INSERT INTO exercise_categories (category_id, category_name, display_name, description, icon, color, sort_order) VALUES
(1, 'adoption_exam', '採用試験', '医師採用試験対策の演習', '📋', '#3B82F6', 1),
(2, 'essay_writing', '小論文', '小論文対策の演習', '✍️', '#10B981', 2),
(3, 'interview', '面接', '面接対策の演習', '🎤', '#F59E0B', 3),
(4, 'free_writing', '自由記述', '自由記述問題の演習', '📝', '#8B5CF6', 4),
(5, 'english_reading', '英語読解', '医学英語読解の演習', '📖', '#EF4444', 5);

-- 演習タイプの初期データ（各カテゴリーに対して必要に応じて追加）
INSERT INTO exercise_types (category_id, type_name, display_name, description, difficulty_level, estimated_duration_minutes, sort_order) VALUES
-- 採用試験系 (category_id = 1)
(1, 'prefecture_adoption', '県総採用試験', '県立病院採用試験対策', 3, 45, 1),
(1, 'keyword_generation_adoption', '採用試験用キーワード生成', '採用試験対策用キーワード生成', 2, 15, 2),
(1, 'paper_search_adoption', '採用試験用論文検索', '採用試験対策用論文検索', 2, 20, 3),

-- 小論文系 (category_id = 2)
(2, 'essay_practice', '小論文練習', '小論文対策の演習', 3, 60, 1),
(2, 'keyword_generation_essay', '小論文用キーワード生成', '小論文対策用キーワード生成', 2, 15, 2),
(2, 'paper_search_essay', '小論文用論文検索', '小論文対策用論文検索', 2, 20, 3),

-- 面接系 (category_id = 3)
(3, 'interview_prep', '面接準備', '医師面接対策', 3, 40, 1),
(3, 'keyword_generation_interview', '面接用キーワード生成', '面接対策用キーワード生成', 2, 15, 2),
(3, 'paper_search_interview', '面接用論文検索', '面接対策用論文検索', 2, 20, 3),

-- 自由記述系 (category_id = 4)
(4, 'free_writing_practice', '自由記述練習', '医療現場での自由記述問題', 4, 60, 1),
(4, 'keyword_generation_free', '自由記述用キーワード生成', '自由記述対策用キーワード生成', 2, 15, 2),
(4, 'paper_search_free', '自由記述用論文検索', '自由記述対策用論文検索', 2, 20, 3),

-- 英語読解系 (category_id = 5)
(5, 'english_reading_practice', '英語読解練習', '医学論文の英語読解', 2, 30, 1),
(5, 'keyword_generation_english', '英語読解用キーワード生成', '英語読解対策用キーワード生成', 2, 15, 2),
(5, 'paper_search_english', '英語読解用論文検索', '英語読解対策用論文検索', 2, 20, 3);

-- ========================================
-- 16. コメント
-- ========================================

COMMENT ON TABLE exercise_categories IS '演習カテゴリーテーブル（1-5で管理）';
COMMENT ON TABLE exercise_types IS '演習タイプテーブル（カテゴリー別に管理）';
COMMENT ON TABLE category_keyword_history IS 'カテゴリー別キーワード生成履歴';
COMMENT ON TABLE category_paper_search_history IS 'カテゴリー別論文検索履歴';

COMMENT ON COLUMN exercise_categories.category_id IS 'カテゴリーID（1:採用試験、2:小論文、3:面接、4:自由記述、5:英語読解）';
COMMENT ON COLUMN category_keyword_history.category_id IS 'どの演習カテゴリーからのキーワード生成か';
COMMENT ON COLUMN category_paper_search_history.category_id IS 'どの演習カテゴリーからの論文検索か';

-- ========================================
-- 17. 確認クエリ
-- ========================================

-- 作成されたカテゴリーを確認
SELECT category_id, category_name, display_name FROM exercise_categories ORDER BY category_id;

-- 作成された演習タイプを確認
SELECT et.exercise_type_id, et.type_name, et.display_name, ec.display_name as category_name
FROM exercise_types et
JOIN exercise_categories ec ON et.category_id = ec.category_id
ORDER BY et.category_id, et.sort_order; 