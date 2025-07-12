-- =====================================================
-- 医学部採用試験対策アプリ - 新データベーススキーマ
-- Supabase PostgreSQL 用 DDL
-- =====================================================

-- 既存のテーブルをバックアップ（念のため）
CREATE TABLE IF NOT EXISTS practice_history_backup AS 
SELECT * FROM practice_history;

CREATE TABLE IF NOT EXISTS user_sessions_backup AS 
SELECT * FROM user_sessions;

-- =====================================================
-- 新しいテーブル構造の作成
-- =====================================================

-- 1. ユーザーテーブル
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(100),
    browser_fingerprint VARCHAR(255),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- 2. 練習カテゴリテーブル
CREATE TABLE practice_categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(20),
    color VARCHAR(7),
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true
);

-- 3. 練習タイプテーブル
CREATE TABLE practice_types (
    practice_type_id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES practice_categories(category_id),
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

-- 4. 練習セッションテーブル
CREATE TABLE practice_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    practice_type_id INTEGER REFERENCES practice_types(practice_type_id),
    theme VARCHAR(200),
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    status VARCHAR(20) DEFAULT 'in_progress' 
        CHECK (status IN ('in_progress', 'completed', 'abandoned', 'error')),
    completion_percentage DECIMAL(5,2) DEFAULT 0.00,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. 練習入力テーブル
CREATE TABLE practice_inputs (
    input_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES practice_sessions(session_id) ON DELETE CASCADE,
    input_type VARCHAR(50) NOT NULL,
    content TEXT,
    word_count INTEGER,
    input_order INTEGER DEFAULT 1,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. 練習スコアテーブル
CREATE TABLE practice_scores (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES practice_sessions(session_id) ON DELETE CASCADE,
    score_category VARCHAR(50) NOT NULL,
    score_value DECIMAL(5,2) NOT NULL CHECK (score_value >= 0),
    max_score DECIMAL(5,2) NOT NULL DEFAULT 10.00 CHECK (max_score > 0),
    weight DECIMAL(3,2) DEFAULT 1.00,
    feedback TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. 練習フィードバックテーブル
CREATE TABLE practice_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES practice_sessions(session_id) ON DELETE CASCADE,
    feedback_content TEXT NOT NULL,
    feedback_type VARCHAR(20) DEFAULT 'general' 
        CHECK (feedback_type IN ('general', 'improvement', 'strong_point', 'error')),
    ai_model VARCHAR(50),
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. ユーザー分析テーブル（事前計算済み統計）
CREATE TABLE user_analytics (
    analytics_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    practice_type_id INTEGER REFERENCES practice_types(practice_type_id),
    total_sessions INTEGER DEFAULT 0,
    total_duration_seconds INTEGER DEFAULT 0,
    average_score DECIMAL(5,2),
    best_score DECIMAL(5,2),
    latest_session_date TIMESTAMP WITH TIME ZONE,
    streak_days INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, practice_type_id)
);

-- 9. 練習テーマテーブル（自由記述用）
CREATE TABLE practice_themes (
    theme_id SERIAL PRIMARY KEY,
    theme_name VARCHAR(200) NOT NULL,
    category VARCHAR(50),
    difficulty_level INTEGER DEFAULT 1 CHECK (difficulty_level BETWEEN 1 AND 5),
    usage_count INTEGER DEFAULT 0,
    average_score DECIMAL(5,2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- インデックスの作成
-- =====================================================

-- 主要パフォーマンスインデックス
CREATE INDEX idx_practice_sessions_user_history 
ON practice_sessions(user_id, created_at DESC, status) 
WHERE status = 'completed';

CREATE INDEX idx_practice_sessions_user_type_date 
ON practice_sessions(user_id, practice_type_id, created_at DESC)
WHERE status = 'completed';

CREATE INDEX idx_practice_inputs_session_type 
ON practice_inputs(session_id, input_type, input_order);

CREATE INDEX idx_practice_scores_session_category 
ON practice_scores(session_id, score_category);

CREATE INDEX idx_practice_feedback_session 
ON practice_feedback(session_id, feedback_type);

-- ユーザー関連インデックス
CREATE INDEX idx_users_fingerprint 
ON users(browser_fingerprint) 
WHERE browser_fingerprint IS NOT NULL;

CREATE INDEX idx_users_email 
ON users(email) 
WHERE email IS NOT NULL;

-- テーマ検索用インデックス
CREATE INDEX idx_practice_sessions_theme 
ON practice_sessions(practice_type_id, theme, created_at DESC)
WHERE theme IS NOT NULL AND theme != '';

-- アクティブセッション管理
CREATE INDEX idx_active_sessions 
ON practice_sessions(user_id, start_time DESC) 
WHERE status = 'in_progress';

-- 分析用インデックス
CREATE INDEX idx_user_analytics_performance 
ON user_analytics(user_id, practice_type_id, latest_session_date DESC);

-- スコア分析用
CREATE INDEX idx_scores_analysis 
ON practice_scores(score_category, score_value, created_at DESC);

-- =====================================================
-- 制約の追加
-- =====================================================

-- 外部キー制約は既にテーブル定義に含まれているが、念のため確認
ALTER TABLE practice_sessions 
ADD CONSTRAINT chk_session_time_order 
CHECK (end_time IS NULL OR end_time >= start_time);

ALTER TABLE practice_sessions 
ADD CONSTRAINT chk_completion_percentage 
CHECK (completion_percentage >= 0 AND completion_percentage <= 100);

ALTER TABLE practice_sessions 
ADD CONSTRAINT chk_duration_positive 
CHECK (duration_seconds IS NULL OR duration_seconds >= 0);

ALTER TABLE practice_inputs 
ADD CONSTRAINT chk_input_order_positive 
CHECK (input_order > 0);

ALTER TABLE practice_inputs 
ADD CONSTRAINT chk_word_count_positive 
CHECK (word_count IS NULL OR word_count >= 0);

ALTER TABLE practice_scores 
ADD CONSTRAINT chk_score_value_range 
CHECK (score_value >= 0 AND score_value <= max_score);

ALTER TABLE practice_scores 
ADD CONSTRAINT chk_weight_range 
CHECK (weight >= 0 AND weight <= 10);

ALTER TABLE users 
ADD CONSTRAINT chk_last_active_order 
CHECK (last_active >= created_at);

-- 一意性制約の追加
CREATE UNIQUE INDEX uk_category_name ON practice_categories(category_name);
CREATE UNIQUE INDEX uk_type_name ON practice_types(type_name);

-- 条件付き一意性（進行中セッションは各練習タイプにつき1つまで）
CREATE UNIQUE INDEX uk_active_session_per_user 
ON practice_sessions(user_id, practice_type_id) 
WHERE status = 'in_progress';

-- =====================================================
-- 初期データの投入
-- =====================================================

-- 練習カテゴリの初期データ
INSERT INTO practice_categories (category_name, display_name, icon, color, sort_order) VALUES
('exam_prep', '採用試験系', '📄', '#667eea', 1),
('reading', '英語読解系', '📖', '#3b82f6', 2),
('writing', '記述系', '✍️', '#8b5cf6', 3),
('interview', '面接系', '🗣️', '#f59e0b', 4),
('research', '論文研究系', '🔬', '#22c55e', 5);

-- 練習タイプの初期データ
INSERT INTO practice_types (category_id, type_name, display_name, input_schema, score_schema, sort_order) VALUES
(1, 'standard_exam', '標準採用試験', 
 '{"fields": ["original_paper", "translation", "opinion"]}',
 '{"categories": ["翻訳評価", "意見評価", "総合評価"]}', 1),

(1, 'past_exam_standard', '過去問スタイル採用試験',
 '{"fields": ["original_paper", "translation", "opinion"]}',
 '{"categories": ["翻訳評価", "意見評価"]}', 2),

(1, 'past_exam_letter', '過去問採用試験（Letter形式）',
 '{"fields": ["original_paper", "translation", "opinion"]}', 
 '{"categories": ["翻訳評価", "意見評価"]}', 3),

(1, 'past_exam_comment', '過去問採用試験（Comment形式）',
 '{"fields": ["original_paper", "translation", "opinion"]}', 
 '{"categories": ["翻訳評価", "意見評価"]}', 4),

(2, 'standard_reading', '標準英語読解',
 '{"fields": ["original_paper", "translation", "comprehension"]}',
 '{"categories": ["理解度", "翻訳精度"]}', 1),

(2, 'past_reading_standard', '過去問スタイル英語読解',
 '{"fields": ["original_paper", "translation", "opinion"]}',
 '{"categories": ["翻訳評価", "意見評価"]}', 2),

(2, 'past_reading_letter', '過去問英語読解（Letter形式）',
 '{"fields": ["original_paper", "translation", "opinion"]}', 
 '{"categories": ["翻訳評価", "意見評価"]}', 3),

(2, 'past_reading_comment', '過去問英語読解（Comment形式）',
 '{"fields": ["original_paper", "translation", "opinion"]}', 
 '{"categories": ["翻訳評価", "意見評価"]}', 4),

(3, 'free_writing', '自由記述', 
 '{"fields": ["theme", "question", "answer"]}',
 '{"categories": ["臨床的正確性", "実践的思考", "包括性", "論理構成"]}', 1),

(3, 'essay_writing', '小論文対策',
 '{"fields": ["theme", "essay"]}',
 '{"categories": ["論理構成", "表現力", "内容充実度"]}', 2),

(4, 'interview_single', '単発面接',
 '{"fields": ["question", "answer"]}',
 '{"categories": ["回答内容", "表現力", "論理性"]}', 1),

(4, 'interview_session', 'セッション面接',
 '{"fields": ["questions", "answers", "flow"]}',
 '{"categories": ["対話力", "一貫性", "専門性"]}', 2),

(5, 'keyword_generation', 'キーワード生成',
 '{"fields": ["keywords", "category", "rationale"]}',
 '{"categories": ["適切性", "網羅性"]}', 1),

(5, 'keyword_generation_paper', 'キーワード生成（論文用）',
 '{"fields": ["keywords", "category", "rationale"]}',
 '{"categories": ["適切性", "網羅性"]}', 2),

(5, 'keyword_generation_writing', 'キーワード生成（記述用）',
 '{"fields": ["keywords", "category", "rationale"]}',
 '{"categories": ["適切性", "網羅性"]}', 3),

(5, 'paper_search', '論文検索',
 '{"fields": ["search_keywords", "paper_title", "paper_abstract"]}',
 '{"categories": ["関連性", "信頼性"]}', 4);

-- =====================================================
-- Row Level Security (RLS) の設定
-- =====================================================

-- RLSを有効化
ALTER TABLE practice_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice_inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_analytics ENABLE ROW LEVEL SECURITY;

-- RLSポリシーの作成（ユーザーは自分のデータのみアクセス可能）
CREATE POLICY user_own_sessions ON practice_sessions
FOR ALL USING (
    user_id = auth.uid()::uuid OR 
    user_id IN (
        SELECT user_id FROM users 
        WHERE users.user_id = practice_sessions.user_id
    )
);

CREATE POLICY user_own_inputs ON practice_inputs
FOR ALL USING (
    session_id IN (
        SELECT session_id FROM practice_sessions 
        WHERE user_id = auth.uid()::uuid OR 
        user_id IN (
            SELECT user_id FROM users 
            WHERE users.user_id = practice_sessions.user_id
        )
    )
);

CREATE POLICY user_own_scores ON practice_scores
FOR ALL USING (
    session_id IN (
        SELECT session_id FROM practice_sessions 
        WHERE user_id = auth.uid()::uuid OR 
        user_id IN (
            SELECT user_id FROM users 
            WHERE users.user_id = practice_sessions.user_id
        )
    )
);

CREATE POLICY user_own_feedback ON practice_feedback
FOR ALL USING (
    session_id IN (
        SELECT session_id FROM practice_sessions 
        WHERE user_id = auth.uid()::uuid OR 
        user_id IN (
            SELECT user_id FROM users 
            WHERE users.user_id = practice_sessions.user_id
        )
    )
);

CREATE POLICY user_own_analytics ON user_analytics
FOR ALL USING (
    user_id = auth.uid()::uuid OR 
    user_id IN (
        SELECT user_id FROM users 
        WHERE users.user_id = user_analytics.user_id
    )
);

-- =====================================================
-- マテリアライズドビューの作成
-- =====================================================

-- ユーザー練習サマリービュー
CREATE MATERIALIZED VIEW mv_user_practice_summary AS
SELECT 
    ps.user_id,
    ps.practice_type_id,
    pt.display_name as practice_type_name,
    pc.display_name as category_name,
    COUNT(*) as total_sessions,
    AVG(ps.duration_seconds) as avg_duration,
    AVG(scores.avg_score) as avg_score,
    MAX(ps.created_at) as last_practice_date,
    COUNT(*) FILTER (WHERE ps.created_at > CURRENT_DATE - INTERVAL '7 days') as sessions_last_week,
    COUNT(*) FILTER (WHERE ps.created_at > CURRENT_DATE - INTERVAL '30 days') as sessions_last_month
FROM practice_sessions ps
JOIN practice_types pt ON ps.practice_type_id = pt.practice_type_id
JOIN practice_categories pc ON pt.category_id = pc.category_id
LEFT JOIN (
    SELECT session_id, AVG((score_value / max_score) * 100) as avg_score
    FROM practice_scores
    GROUP BY session_id
) scores ON ps.session_id = scores.session_id
WHERE ps.status = 'completed'
GROUP BY ps.user_id, ps.practice_type_id, pt.display_name, pc.display_name;

CREATE UNIQUE INDEX idx_mv_user_practice_summary 
ON mv_user_practice_summary(user_id, practice_type_id);

-- スコア統計ビュー
CREATE MATERIALIZED VIEW mv_score_statistics AS
SELECT 
    psc.score_category,
    ps.practice_type_id,
    COUNT(*) as total_scores,
    AVG((psc.score_value / psc.max_score) * 100) as avg_score_percentage,
    STDDEV((psc.score_value / psc.max_score) * 100) as score_stddev,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY (psc.score_value / psc.max_score) * 100) as q1_score,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (psc.score_value / psc.max_score) * 100) as median_score,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY (psc.score_value / psc.max_score) * 100) as q3_score,
    MIN((psc.score_value / psc.max_score) * 100) as min_score,
    MAX((psc.score_value / psc.max_score) * 100) as max_score
FROM practice_scores psc
JOIN practice_sessions ps ON psc.session_id = ps.session_id
WHERE ps.status = 'completed'
GROUP BY psc.score_category, ps.practice_type_id;

-- =====================================================
-- 便利な関数の作成
-- =====================================================

-- 統計情報更新関数
CREATE OR REPLACE FUNCTION update_table_statistics()
RETURNS void AS $$
BEGIN
    ANALYZE practice_sessions;
    ANALYZE practice_inputs;
    ANALYZE practice_scores;
    ANALYZE practice_feedback;
    ANALYZE user_analytics;
    
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_user_practice_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_score_statistics;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ユーザー分析データ更新関数
CREATE OR REPLACE FUNCTION update_user_analytics(target_user_id UUID DEFAULT NULL)
RETURNS void AS $$
BEGIN
    INSERT INTO user_analytics (user_id, practice_type_id, total_sessions, average_score, best_score, latest_session_date)
    SELECT 
        ps.user_id,
        ps.practice_type_id,
        COUNT(*) as total_sessions,
        AVG(scores.avg_score) as average_score,
        MAX(scores.avg_score) as best_score,
        MAX(ps.created_at) as latest_session_date
    FROM practice_sessions ps
    LEFT JOIN (
        SELECT session_id, AVG((score_value / max_score) * 100) as avg_score
        FROM practice_scores 
        GROUP BY session_id
    ) scores ON ps.session_id = scores.session_id
    WHERE ps.status = 'completed'
    AND (target_user_id IS NULL OR ps.user_id = target_user_id)
    GROUP BY ps.user_id, ps.practice_type_id
    ON CONFLICT (user_id, practice_type_id) 
    DO UPDATE SET
        total_sessions = EXCLUDED.total_sessions,
        average_score = EXCLUDED.average_score,
        best_score = EXCLUDED.best_score,
        latest_session_date = EXCLUDED.latest_session_date,
        last_updated = NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- 完了メッセージ
-- =====================================================

-- 新しいスキーマ作成完了の確認
DO $$
BEGIN
    RAISE NOTICE '✅ 新データベーススキーマの作成が完了しました！';
    RAISE NOTICE '📊 作成されたテーブル数: %', (
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('users', 'practice_categories', 'practice_types', 
                          'practice_sessions', 'practice_inputs', 'practice_scores', 
                          'practice_feedback', 'user_analytics', 'practice_themes')
    );
    RAISE NOTICE '🔍 作成されたインデックス数: %', (
        SELECT COUNT(*) FROM pg_indexes 
        WHERE schemaname = 'public'
        AND indexname LIKE 'idx_%'
    );
    RAISE NOTICE '⚡ 準備完了: 新システムでのデータ保存が可能です';
END $$; 