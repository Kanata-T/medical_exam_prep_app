# 技術仕様書：データベースリファクタリング

## 📋 目次
1. [現在の技術的問題](#現在の技術的問題)
2. [新データベーススキーマ詳細](#新データベーススキーマ詳細)
3. [インデックス戦略](#インデックス戦略)
4. [Streamlit Cloud対応](#streamlit-cloud対応)
5. [パフォーマンス最適化](#パフォーマンス最適化)
6. [セキュリティ設計](#セキュリティ設計)

---

## 🚨 現在の技術的問題

### 1. Streamlit Cloud履歴表示問題の詳細調査

**根本原因**:
```python
# 現在のコード（modules/database.py:119-130）
def get_session_id(self) -> str:
    if 'db_session_id' not in st.session_state:
        st.session_state.db_session_id = str(uuid.uuid4())
        # 新しいセッションIDが毎回生成される
```

**問題点**:
- Streamlit Cloudでは、ページ再読み込み時に`st.session_state`がリセットされる
- ユーザーが同じブラウザからアクセスしても、毎回異なる`session_id`が生成
- 結果として、過去の学習履歴が追跡できない

**技術的詳細**:
```
Streamlit Cloud環境:
- セッション持続時間: ~10分（アイドル時）
- st.session_state寿命: ページリロードまで
- Cookie利用制限: 第三者Cookieの制約
```

### 2. 現在のテーブル設計の技術的問題

**practice_history テーブル**:
```sql
-- 現在の構造（問題あり）
practice_type    TEXT    -- 例: "過去問スタイル採用試験 - Letter形式（翻訳 + 意見）"
inputs          JSONB   -- 構造化されていない異なる形式が混在
scores          JSONB   -- スコア項目が一定していない

-- 実際のデータ例
{
  "practice_type": "過去問スタイル採用試験 - Letter形式（翻訳 + 意見）",
  "inputs": {
    "original_paper": "...",
    "translation": "...",
    "opinion": "..."
  },
  "scores": {
    "翻訳評価": 8.5,
    "意見評価": 7.0
  }
}
```

**パフォーマンス問題**:
- JSONB列での複雑なクエリ（WHERE, ORDER BY）
- インデックスが効かない検索条件
- 文字列比較による練習タイプフィルタリング

---

## 🏗️ 新データベーススキーマ詳細

### 1. 完全なDDL定義

```sql
-- ===== CORE TABLES =====

-- Users table
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(100),
    browser_fingerprint VARCHAR(255), -- Streamlit Cloud用識別子
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- Practice categories
CREATE TABLE practice_categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(20),
    color VARCHAR(7), -- HEXカラーコード
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true
);

-- Practice types  
CREATE TABLE practice_types (
    practice_type_id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES practice_categories(category_id),
    type_name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(150) NOT NULL,
    description TEXT,
    input_schema JSONB DEFAULT '{}', -- 入力フィールドの定義
    score_schema JSONB DEFAULT '{}', -- スコア項目の定義
    difficulty_level INTEGER DEFAULT 1 CHECK (difficulty_level BETWEEN 1 AND 5),
    estimated_duration_minutes INTEGER DEFAULT 30,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Practice sessions
CREATE TABLE practice_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id),
    practice_type_id INTEGER REFERENCES practice_types(practice_type_id),
    theme VARCHAR(200), -- 練習テーマ（自由記述用など）
    start_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    status VARCHAR(20) DEFAULT 'in_progress' 
        CHECK (status IN ('in_progress', 'completed', 'abandoned', 'error')),
    completion_percentage DECIMAL(5,2) DEFAULT 0.00,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Practice inputs (normalized)
CREATE TABLE practice_inputs (
    input_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES practice_sessions(session_id) ON DELETE CASCADE,
    input_type VARCHAR(50) NOT NULL, -- 'question', 'answer', 'translation', 'opinion'
    content TEXT,
    word_count INTEGER, -- 文字数/単語数
    input_order INTEGER DEFAULT 1, -- 複数入力がある場合の順序
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Practice scores (normalized)
CREATE TABLE practice_scores (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES practice_sessions(session_id) ON DELETE CASCADE,
    score_category VARCHAR(50) NOT NULL, -- '臨床的正確性', '実践的思考', '包括性', '論理構成'
    score_value DECIMAL(5,2) NOT NULL CHECK (score_value >= 0),
    max_score DECIMAL(5,2) NOT NULL DEFAULT 10.00 CHECK (max_score > 0),
    score_percentage AS (score_value / max_score * 100) STORED,
    weight DECIMAL(3,2) DEFAULT 1.00, -- 重み付け
    feedback TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Practice feedback
CREATE TABLE practice_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES practice_sessions(session_id) ON DELETE CASCADE,
    feedback_content TEXT NOT NULL,
    feedback_type VARCHAR(20) DEFAULT 'general' 
        CHECK (feedback_type IN ('general', 'improvement', 'strong_point', 'error')),
    ai_model VARCHAR(50), -- 'gemini-pro', 'gpt-4' など
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== OPTIMIZATION TABLES =====

-- User analytics (pre-computed stats)
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

-- Practice themes (for free writing)
CREATE TABLE practice_themes (
    theme_id SERIAL PRIMARY KEY,
    theme_name VARCHAR(200) NOT NULL,
    category VARCHAR(50), -- '循環器', '呼吸器' など
    difficulty_level INTEGER DEFAULT 1 CHECK (difficulty_level BETWEEN 1 AND 5),
    usage_count INTEGER DEFAULT 0,
    average_score DECIMAL(5,2),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 2. 初期データ投入

```sql
-- Practice categories
INSERT INTO practice_categories (category_name, display_name, icon, color, sort_order) VALUES
('exam_prep', '採用試験系', '📄', '#667eea', 1),
('reading', '英語読解系', '📖', '#3b82f6', 2),
('writing', '記述系', '✍️', '#8b5cf6', 3),
('interview', '面接系', '🗣️', '#f59e0b', 4),
('research', '論文研究系', '🔬', '#22c55e', 5);

-- Practice types
INSERT INTO practice_types (category_id, type_name, display_name, input_schema, score_schema, sort_order) VALUES
(1, 'standard_exam', '標準採用試験', 
 '{"fields": ["original_paper", "translation", "opinion"]}',
 '{"categories": ["翻訳評価", "意見評価", "総合評価"]}', 1),
(1, 'past_exam_letter', '過去問採用試験（Letter形式）',
 '{"fields": ["original_paper", "translation", "opinion"]}', 
 '{"categories": ["翻訳評価", "意見評価"]}', 2),
(3, 'free_writing', '自由記述', 
 '{"fields": ["theme", "question", "answer"]}',
 '{"categories": ["臨床的正確性", "実践的思考", "包括性", "論理構成"]}', 1),
(3, 'essay_writing', '小論文対策',
 '{"fields": ["theme", "essay"]}',
 '{"categories": ["論理構成", "表現力", "内容充実度"]}', 2);
```

---

## 🔍 インデックス戦略

### 1. パフォーマンス重視インデックス

```sql
-- ===== PRIMARY PERFORMANCE INDEXES =====

-- User session lookup (most frequent query)
CREATE INDEX idx_practice_sessions_user_type_date 
ON practice_sessions(user_id, practice_type_id, created_at DESC);

-- Session details lookup
CREATE INDEX idx_practice_sessions_status_date 
ON practice_sessions(status, created_at DESC) 
WHERE status = 'completed';

-- Score analytics
CREATE INDEX idx_practice_scores_session_category 
ON practice_scores(session_id, score_category);

-- Input content search
CREATE INDEX idx_practice_inputs_type_session 
ON practice_inputs(input_type, session_id);

-- ===== ANALYTICS INDEXES =====

-- User performance tracking
CREATE INDEX idx_user_analytics_user_latest 
ON user_analytics(user_id, latest_session_date DESC);

-- Theme popularity
CREATE INDEX idx_practice_themes_usage 
ON practice_themes(usage_count DESC, average_score DESC);

-- ===== FULL-TEXT SEARCH INDEXES =====

-- Feedback content search (PostgreSQL specific)
CREATE INDEX idx_feedback_content_fts 
ON practice_feedback USING gin(to_tsvector('japanese', feedback_content));

-- Input content search
CREATE INDEX idx_input_content_fts 
ON practice_inputs USING gin(to_tsvector('japanese', content));

-- ===== PARTIAL INDEXES =====

-- Active sessions only
CREATE INDEX idx_active_sessions 
ON practice_sessions(user_id, start_time DESC) 
WHERE status = 'in_progress';

-- Recent completed sessions (last 30 days)
CREATE INDEX idx_recent_completed_sessions 
ON practice_sessions(user_id, practice_type_id, end_time DESC) 
WHERE status = 'completed' 
AND end_time > NOW() - INTERVAL '30 days';
```

### 2. パーティショニング戦略

```sql
-- Practice sessions partitioning by month (for large datasets)
CREATE TABLE practice_sessions (
    -- ... columns as above
) PARTITION BY RANGE (created_at);

-- Create partitions for each month
CREATE TABLE practice_sessions_2024_01 
PARTITION OF practice_sessions 
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Auto-partition creation function
CREATE OR REPLACE FUNCTION create_monthly_partition(table_name text, start_date date)
RETURNS void AS $$
DECLARE
    partition_name text;
    end_date date;
BEGIN
    partition_name := table_name || '_' || to_char(start_date, 'YYYY_MM');
    end_date := start_date + interval '1 month';
    
    EXECUTE format('CREATE TABLE %I PARTITION OF %I 
                    FOR VALUES FROM (%L) TO (%L)',
                   partition_name, table_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;
```

---

## 🌐 Streamlit Cloud対応

### 1. ユーザー識別戦略

**Option A: Browser Fingerprinting (推奨)**
```python
import hashlib
import streamlit as st

def get_browser_fingerprint():
    """ブラウザフィンガープリントを生成"""
    # Streamlit環境の情報を組み合わせ
    components = [
        st.session_state.get('session_id', ''),
        # その他利用可能な情報を組み合わせ
    ]
    
    fingerprint_string = '|'.join(str(c) for c in components)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]

def get_or_create_user():
    """ユーザーを取得または作成"""
    fingerprint = get_browser_fingerprint()
    
    # データベースでユーザーを検索
    user = db.get_user_by_fingerprint(fingerprint)
    if not user:
        user = db.create_user(browser_fingerprint=fingerprint)
    
    return user
```

**Option B: Simple Session Persistence**
```python
def get_persistent_user_id():
    """永続的なユーザーIDを取得"""
    # URL パラメータからuser_idを取得（初回アクセス時に生成）
    user_id = st.experimental_get_query_params().get('user_id', [None])[0]
    
    if not user_id:
        user_id = str(uuid.uuid4())
        # URLにuser_idを追加（リダイレクト）
        st.experimental_set_query_params(user_id=user_id)
        st.experimental_rerun()
    
    return user_id
```

**Option C: Email-based Simple Auth**
```python
def get_user_by_email():
    """メールベースの簡単認証"""
    if 'user_email' not in st.session_state:
        email = st.text_input("学習履歴を保存するためのメールアドレス（任意）:")
        if email:
            st.session_state.user_email = email
            st.experimental_rerun()
        return None
    
    return db.get_or_create_user_by_email(st.session_state.user_email)
```

### 2. セッション永続化メカニズム

```python
class PersistentSessionManager:
    def __init__(self):
        self.session_key = self._get_session_key()
        
    def _get_session_key(self):
        """セッションキーを取得または生成"""
        # 複数の方法を試行
        methods = [
            self._get_from_url_params,
            self._get_from_browser_fingerprint,
            self._get_from_local_storage,  # JavaScript経由
            self._generate_new_session
        ]
        
        for method in methods:
            try:
                key = method()
                if key:
                    return key
            except Exception:
                continue
                
        return self._generate_new_session()
    
    def save_session_data(self, data):
        """セッションデータをデータベースに永続化"""
        db.save_session_data(self.session_key, data)
    
    def load_session_data(self):
        """永続化されたセッションデータを読み込み"""
        return db.load_session_data(self.session_key)
```

---

## ⚡ パフォーマンス最適化

### 1. クエリ最適化戦略

```sql
-- ===== OPTIMIZED QUERIES =====

-- User history with aggregated scores (避けるべき: N+1クエリ)
WITH session_scores AS (
    SELECT 
        ps.session_id,
        ps.user_id,
        ps.practice_type_id,
        ps.theme,
        ps.created_at,
        ps.duration_seconds,
        AVG(sc.score_percentage) as avg_score,
        COUNT(sc.score_id) as score_count
    FROM practice_sessions ps
    LEFT JOIN practice_scores sc ON ps.session_id = sc.session_id
    WHERE ps.user_id = $1 
    AND ps.status = 'completed'
    GROUP BY ps.session_id, ps.user_id, ps.practice_type_id, ps.theme, ps.created_at, ps.duration_seconds
)
SELECT 
    ss.*,
    pt.display_name,
    pc.display_name as category_name
FROM session_scores ss
JOIN practice_types pt ON ss.practice_type_id = pt.practice_type_id
JOIN practice_categories pc ON pt.category_id = pc.category_id
ORDER BY ss.created_at DESC
LIMIT 50;

-- User analytics pre-computation (定期実行)
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
    SELECT session_id, AVG(score_percentage) as avg_score
    FROM practice_scores 
    GROUP BY session_id
) scores ON ps.session_id = scores.session_id
WHERE ps.status = 'completed'
GROUP BY ps.user_id, ps.practice_type_id
ON CONFLICT (user_id, practice_type_id) 
DO UPDATE SET
    total_sessions = EXCLUDED.total_sessions,
    average_score = EXCLUDED.average_score,
    best_score = EXCLUDED.best_score,
    latest_session_date = EXCLUDED.latest_session_date,
    last_updated = NOW();
```

### 2. アプリケーションレベル最適化

```python
class OptimizedDatabaseManager:
    def __init__(self):
        self.connection_pool = self._create_connection_pool()
        self.cache = TTLCache(maxsize=1000, ttl=300)  # 5分キャッシュ
    
    @lru_cache(maxsize=100)
    def get_practice_types(self):
        """練習タイプをキャッシュ"""
        # 変更頻度が低いデータはキャッシュ
        pass
    
    async def get_user_history_batch(self, user_id: str, practice_types: List[str]):
        """バッチクエリで複数タイプの履歴を一度に取得"""
        # 複数のAPIリクエストを1つのクエリにまとめる
        pass
    
    def get_user_statistics(self, user_id: str):
        """事前計算された統計データを取得"""
        cache_key = f"user_stats_{user_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        stats = self._compute_user_statistics(user_id)
        self.cache[cache_key] = stats
        return stats
```

---

## 🔒 セキュリティ設計

### 1. Row Level Security (RLS)

```sql
-- Enable RLS on all user-related tables
ALTER TABLE practice_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice_inputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE practice_feedback ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY user_own_sessions ON practice_sessions
FOR ALL USING (user_id = current_setting('app.current_user_id')::uuid);

CREATE POLICY user_own_inputs ON practice_inputs
FOR ALL USING (
    session_id IN (
        SELECT session_id FROM practice_sessions 
        WHERE user_id = current_setting('app.current_user_id')::uuid
    )
);

-- Similar policies for scores and feedback...
```

### 2. データプライバシー

```sql
-- Personal data anonymization function
CREATE OR REPLACE FUNCTION anonymize_user_data(target_user_id UUID)
RETURNS void AS $$
BEGIN
    -- Remove personal identifiers but keep analytics data
    UPDATE users 
    SET email = NULL, 
        display_name = 'Anonymized User',
        browser_fingerprint = 'ANONYMIZED'
    WHERE user_id = target_user_id;
    
    -- Clear content but keep metadata for analytics
    UPDATE practice_inputs 
    SET content = '[ANONYMIZED]'
    WHERE session_id IN (
        SELECT session_id FROM practice_sessions WHERE user_id = target_user_id
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### 3. API レート制限

```python
from functools import wraps
import time

def rate_limit(calls_per_minute=60):
    def decorator(func):
        calls = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id') or args[0] if args else 'anonymous'
            now = time.time()
            
            # Clean old entries
            calls[user_id] = [call_time for call_time in calls.get(user_id, []) 
                            if now - call_time < 60]
            
            if len(calls.get(user_id, [])) >= calls_per_minute:
                raise Exception("Rate limit exceeded")
            
            calls.setdefault(user_id, []).append(now)
            return func(*args, **kwargs)
        
        return wrapper
    return decorator

class SecureDatabaseManager:
    @rate_limit(calls_per_minute=100)
    def save_practice_history(self, user_id: str, data: dict):
        # Validate input data
        self._validate_practice_data(data)
        # Save with proper sanitization
        pass
    
    def _validate_practice_data(self, data: dict):
        """入力データの検証とサニタイゼーション"""
        # SQL injection prevention
        # XSS prevention  
        # Data size limits
        pass
```

---

## 📈 監視・ログ戦略

### 1. パフォーマンス監視

```sql
-- Query performance monitoring view
CREATE VIEW slow_queries AS
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    rows
FROM pg_stat_statements 
WHERE mean_time > 100  -- 100ms以上のクエリ
ORDER BY mean_time DESC;

-- Database connection monitoring
CREATE VIEW connection_stats AS
SELECT 
    state,
    COUNT(*) as connection_count,
    AVG(EXTRACT(EPOCH FROM (now() - query_start))) as avg_duration
FROM pg_stat_activity 
WHERE datname = current_database()
GROUP BY state;
```

### 2. アプリケーションログ

```python
import structlog
import time

logger = structlog.get_logger()

class MonitoredDatabaseManager:
    def save_practice_history(self, user_id: str, data: dict):
        start_time = time.time()
        try:
            result = self._save_practice_history_impl(user_id, data)
            
            logger.info("practice_history_saved",
                       user_id=user_id,
                       practice_type=data.get('type'),
                       duration_ms=(time.time() - start_time) * 1000,
                       success=True)
            return result
            
        except Exception as e:
            logger.error("practice_history_save_failed",
                        user_id=user_id,
                        error=str(e),
                        duration_ms=(time.time() - start_time) * 1000)
            raise
```

---

## 🔄 次のステップ

1. **詳細実装計画の策定**
2. **マイグレーションスクリプトの作成**
3. **新DatabaseManagerの実装開始**
4. **Streamlit Cloud環境でのテスト実施** 