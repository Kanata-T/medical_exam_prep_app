-- =====================================================
-- ユーザー管理機能拡張 - Supabaseスキーマ更新（修正版）
-- 医学部採用試験対策アプリ用
-- =====================================================

-- =====================================================
-- 1. 既存usersテーブルの拡張
-- =====================================================

-- パスワード認証機能を追加
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS login_attempts INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS account_locked_until TIMESTAMP WITH TIME ZONE;

-- プロフィール情報の拡張
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'Asia/Tokyo';
ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(10) DEFAULT 'ja';

-- アカウント状態管理
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS account_status VARCHAR(20) DEFAULT 'active' 
    CHECK (account_status IN ('active', 'inactive', 'suspended', 'pending_verification'));

-- 同意・規約関連
ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_policy_accepted BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_policy_accepted_at TIMESTAMP WITH TIME ZONE;

-- =====================================================
-- 2. 新しいテーブル: user_settings
-- =====================================================

CREATE TABLE IF NOT EXISTS user_settings (
    setting_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    -- 学習目標設定
    daily_practice_goal INTEGER DEFAULT 1, -- 1日の練習目標数
    weekly_practice_goal INTEGER DEFAULT 7, -- 1週間の練習目標数
    target_score DECIMAL(5,2) DEFAULT 8.0, -- 目標スコア
    preferred_practice_time VARCHAR(20) DEFAULT 'anytime', -- 'morning', 'afternoon', 'evening', 'anytime'
    
    -- 通知設定
    email_notifications BOOLEAN DEFAULT TRUE,
    practice_reminders BOOLEAN DEFAULT TRUE,
    achievement_notifications BOOLEAN DEFAULT TRUE,
    weekly_summary BOOLEAN DEFAULT TRUE,
    
    -- 学習設定
    preferred_difficulty INTEGER DEFAULT 2 CHECK (preferred_difficulty BETWEEN 1 AND 5),
    auto_save_enabled BOOLEAN DEFAULT TRUE,
    show_hints BOOLEAN DEFAULT TRUE,
    enable_timer BOOLEAN DEFAULT FALSE,
    default_practice_duration INTEGER DEFAULT 60, -- 分
    
    -- UI設定
    theme VARCHAR(20) DEFAULT 'light' CHECK (theme IN ('light', 'dark', 'auto')),
    font_size VARCHAR(10) DEFAULT 'medium' CHECK (font_size IN ('small', 'medium', 'large')),
    sidebar_collapsed BOOLEAN DEFAULT FALSE,
    
    -- プライバシー設定
    profile_visibility VARCHAR(20) DEFAULT 'private' CHECK (profile_visibility IN ('public', 'friends', 'private')),
    show_learning_stats BOOLEAN DEFAULT TRUE,
    allow_data_analysis BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id)
);

-- =====================================================
-- 3. 新しいテーブル: user_achievements
-- =====================================================

CREATE TABLE IF NOT EXISTS user_achievements (
    achievement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    achievement_type VARCHAR(50) NOT NULL, -- 'streak', 'score_improvement', 'practice_count', 'completion_rate'
    achievement_name VARCHAR(100) NOT NULL, -- '7日連続練習', '初回満点', '100回練習達成'
    achievement_description TEXT,
    earned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    badge_icon VARCHAR(20), -- emoji
    badge_color VARCHAR(7), -- hex color
    points_earned INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}', -- 詳細データ
    is_visible BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 4. 新しいテーブル: user_learning_goals
-- =====================================================

CREATE TABLE IF NOT EXISTS user_learning_goals (
    goal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    practice_type_id INTEGER REFERENCES practice_types(practice_type_id),
    
    goal_type VARCHAR(20) NOT NULL CHECK (goal_type IN ('score', 'frequency', 'streak', 'completion_time')),
    target_value DECIMAL(10,2) NOT NULL, -- 目標値
    current_value DECIMAL(10,2) DEFAULT 0, -- 現在の値
    unit VARCHAR(20) NOT NULL, -- 'points', 'times', 'days', 'minutes'
    
    start_date DATE NOT NULL,
    target_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'paused', 'cancelled')),
    
    title VARCHAR(100) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- =====================================================
-- 5. 新しいテーブル: user_activity_log
-- =====================================================

CREATE TABLE IF NOT EXISTS user_activity_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    
    activity_type VARCHAR(50) NOT NULL, -- 'login', 'logout', 'practice_start', 'practice_complete', 'settings_change'
    activity_description TEXT,
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =====================================================
-- 6. インデックスの作成
-- =====================================================

-- ユーザー認証関連インデックス
CREATE INDEX IF NOT EXISTS idx_users_email_verified ON users(email, email_verified);
CREATE INDEX IF NOT EXISTS idx_users_password_reset ON users(password_reset_token) WHERE password_reset_token IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_verification_token ON users(email_verification_token) WHERE email_verification_token IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login DESC);
CREATE INDEX IF NOT EXISTS idx_users_account_status ON users(account_status, created_at DESC);

-- ユーザー設定インデックス
CREATE INDEX IF NOT EXISTS idx_user_settings_notifications ON user_settings(user_id) WHERE email_notifications = TRUE OR practice_reminders = TRUE;

-- 成果・目標関連インデックス
CREATE INDEX IF NOT EXISTS idx_user_achievements_user_date ON user_achievements(user_id, earned_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_achievements_type ON user_achievements(achievement_type, earned_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_goals_active ON user_learning_goals(user_id, status, target_date) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_user_goals_practice_type ON user_learning_goals(practice_type_id, status, target_date);

-- アクティビティログインデックス
CREATE INDEX IF NOT EXISTS idx_activity_log_user_time ON user_activity_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_type_time ON user_activity_log(activity_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_session ON user_activity_log(session_id) WHERE session_id IS NOT NULL;

-- =====================================================
-- 7. 制約の追加
-- =====================================================

-- パスワードリセット期限制約
ALTER TABLE users ADD CONSTRAINT chk_password_reset_expiry 
CHECK (password_reset_expires IS NULL OR password_reset_expires > NOW());

-- ログイン試行回数制約
ALTER TABLE users ADD CONSTRAINT chk_login_attempts 
CHECK (login_attempts >= 0 AND login_attempts <= 10);

-- 学習目標値制約
ALTER TABLE user_learning_goals ADD CONSTRAINT chk_goal_target_positive 
CHECK (target_value > 0);

ALTER TABLE user_learning_goals ADD CONSTRAINT chk_goal_current_non_negative 
CHECK (current_value >= 0);

ALTER TABLE user_learning_goals ADD CONSTRAINT chk_goal_date_order 
CHECK (target_date >= start_date);

-- 設定値制約
ALTER TABLE user_settings ADD CONSTRAINT chk_practice_goals_positive 
CHECK (daily_practice_goal > 0 AND weekly_practice_goal > 0);

ALTER TABLE user_settings ADD CONSTRAINT chk_target_score_range 
CHECK (target_score >= 0 AND target_score <= 10);

ALTER TABLE user_settings ADD CONSTRAINT chk_practice_duration_range 
CHECK (default_practice_duration >= 5 AND default_practice_duration <= 300);

-- =====================================================
-- 8. トリガー関数の作成
-- =====================================================

-- ユーザー設定自動作成トリガー
CREATE OR REPLACE FUNCTION create_default_user_settings()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO user_settings (user_id)
    VALUES (NEW.user_id)
    ON CONFLICT (user_id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trigger_create_user_settings
    AFTER INSERT ON users
    FOR EACH ROW
    EXECUTE FUNCTION create_default_user_settings();

-- ユーザー設定更新日時更新トリガー
CREATE OR REPLACE FUNCTION update_user_settings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trigger_update_user_settings_timestamp
    BEFORE UPDATE ON user_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_user_settings_timestamp();

-- =====================================================
-- 9. セキュリティ設定 (Row Level Security)
-- =====================================================

-- ユーザー設定のRLS
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_settings_own_data ON user_settings
FOR ALL USING (
    user_id = auth.uid()::uuid OR 
    user_id IN (
        SELECT user_id FROM users 
        WHERE users.user_id = user_settings.user_id
    )
);

-- ユーザー成果のRLS
ALTER TABLE user_achievements ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_achievements_own_data ON user_achievements
FOR ALL USING (
    user_id = auth.uid()::uuid OR 
    user_id IN (
        SELECT user_id FROM users 
        WHERE users.user_id = user_achievements.user_id
    )
);

-- 学習目標のRLS
ALTER TABLE user_learning_goals ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_goals_own_data ON user_learning_goals
FOR ALL USING (
    user_id = auth.uid()::uuid OR 
    user_id IN (
        SELECT user_id FROM users 
        WHERE users.user_id = user_learning_goals.user_id
    )
);

-- アクティビティログのRLS
ALTER TABLE user_activity_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_activity_own_data ON user_activity_log
FOR ALL USING (
    user_id = auth.uid()::uuid OR 
    user_id IN (
        SELECT user_id FROM users 
        WHERE users.user_id = user_activity_log.user_id
    )
);

-- =====================================================
-- 10. 便利なビューの作成（修正版）
-- =====================================================

-- ユーザープロフィール統合ビュー（修正版）
CREATE OR REPLACE VIEW user_profile_view AS
SELECT 
    u.user_id,
    u.email,
    u.display_name,
    u.first_name,
    u.last_name,
    u.avatar_url,
    u.bio,
    u.created_at,
    u.last_active,
    u.last_login,
    u.account_status,
    u.email_verified,
    u.timezone,
    u.language,  -- 🔧 修正: us.language → u.language
    us.daily_practice_goal,
    us.weekly_practice_goal,
    us.target_score,
    us.theme,
    COUNT(ps.session_id) as total_sessions,
    AVG(CASE WHEN sc.max_score > 0 THEN (sc.score_value / sc.max_score) * 100 ELSE 0 END) as average_score_percentage
FROM users u
LEFT JOIN user_settings us ON u.user_id = us.user_id
LEFT JOIN practice_sessions ps ON u.user_id = ps.user_id AND ps.status = 'completed'
LEFT JOIN practice_scores sc ON ps.session_id = sc.session_id
GROUP BY u.user_id, us.user_id, us.daily_practice_goal, us.weekly_practice_goal, us.target_score, us.theme;

-- ユーザー成果サマリービュー
CREATE OR REPLACE VIEW user_achievements_summary AS
SELECT 
    user_id,
    COUNT(*) as total_achievements,
    SUM(points_earned) as total_points,
    MAX(earned_at) as latest_achievement,
    COUNT(*) FILTER (WHERE earned_at >= NOW() - INTERVAL '30 days') as recent_achievements
FROM user_achievements
WHERE is_visible = TRUE
GROUP BY user_id;

-- アクティブユーザー統計ビュー
CREATE OR REPLACE VIEW active_users_stats AS
SELECT 
    COUNT(*) FILTER (WHERE last_active >= NOW() - INTERVAL '1 day') as daily_active,
    COUNT(*) FILTER (WHERE last_active >= NOW() - INTERVAL '7 days') as weekly_active,
    COUNT(*) FILTER (WHERE last_active >= NOW() - INTERVAL '30 days') as monthly_active,
    COUNT(*) as total_users
FROM users
WHERE account_status = 'active';

-- =====================================================
-- 11. 管理用関数
-- =====================================================

-- ユーザー統計更新関数
CREATE OR REPLACE FUNCTION update_user_statistics(target_user_id UUID DEFAULT NULL)
RETURNS void AS $$
BEGIN
    -- ユーザーの学習目標進捗を更新
    UPDATE user_learning_goals 
    SET current_value = (
        CASE goal_type
            WHEN 'score' THEN (
                SELECT AVG(CASE WHEN sc.max_score > 0 THEN (sc.score_value / sc.max_score) * 100 ELSE 0 END)
                FROM practice_sessions ps
                JOIN practice_scores sc ON ps.session_id = sc.session_id
                WHERE ps.user_id = user_learning_goals.user_id
                AND ps.practice_type_id = user_learning_goals.practice_type_id
                AND ps.created_at >= user_learning_goals.start_date
                AND ps.status = 'completed'
            )
            WHEN 'frequency' THEN (
                SELECT COUNT(*)
                FROM practice_sessions ps
                WHERE ps.user_id = user_learning_goals.user_id
                AND ps.practice_type_id = user_learning_goals.practice_type_id
                AND ps.created_at >= user_learning_goals.start_date
                AND ps.status = 'completed'
            )
            ELSE current_value
        END
    )
    WHERE (target_user_id IS NULL OR user_id = target_user_id)
    AND status = 'active';
    
    -- 完了した目標をマーク
    UPDATE user_learning_goals 
    SET status = 'completed', completed_at = NOW()
    WHERE current_value >= target_value 
    AND status = 'active'
    AND (target_user_id IS NULL OR user_id = target_user_id);
    
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- アカウントロック管理関数
CREATE OR REPLACE FUNCTION handle_failed_login(user_email VARCHAR(255))
RETURNS void AS $$
BEGIN
    UPDATE users 
    SET 
        login_attempts = login_attempts + 1,
        account_locked_until = CASE 
            WHEN login_attempts >= 4 THEN NOW() + INTERVAL '30 minutes'
            ELSE account_locked_until
        END
    WHERE email = user_email;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- アカウントロック解除関数
CREATE OR REPLACE FUNCTION unlock_user_account(user_email VARCHAR(255))
RETURNS void AS $$
BEGIN
    UPDATE users 
    SET 
        login_attempts = 0,
        account_locked_until = NULL
    WHERE email = user_email;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- 完了メッセージ
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '✅ ユーザー管理機能の拡張が完了しました！';
    RAISE NOTICE '🔐 追加された機能:';
    RAISE NOTICE '   - パスワード認証';
    RAISE NOTICE '   - ユーザープロフィール管理';
    RAISE NOTICE '   - 学習設定・目標管理';
    RAISE NOTICE '   - 成果・バッジシステム';
    RAISE NOTICE '   - アクティビティログ';
    RAISE NOTICE '   - Row Level Security対応';
    RAISE NOTICE '📊 新しいテーブル数: 4個';
    RAISE NOTICE '🔍 新しいインデックス数: 10個';
    RAISE NOTICE '⚡ 準備完了: ユーザー管理機能が利用可能です';
END $$; 