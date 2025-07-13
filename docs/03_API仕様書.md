# API仕様書

## 📋 目次
1. [概要](#概要)
2. [認証・認可](#認証認可)
3. [エンドポイント一覧](#エンドポイント一覧)
4. [データ形式](#データ形式)
5. [エラーハンドリング](#エラーハンドリング)
6. [レート制限](#レート制限)
7. [実装例](#実装例)

---

## 🎯 概要

### API概要
医学部研修医採用試験対策アプリのREST API仕様です。ユーザー認証、練習セッション管理、履歴・分析データ取得を提供します。

### 基本情報
- **ベースURL**: `https://your-app.streamlit.app/api/v1`
- **認証方式**: Bearer Token (JWT)
- **データ形式**: JSON
- **文字エンコーディング**: UTF-8
- **タイムゾーン**: UTC

### 共通レスポンス形式

```json
{
  "success": true,
  "data": {
    // レスポンスデータ
  },
  "message": "操作が成功しました",
  "timestamp": "2024-12-01T10:00:00Z"
}
```

---

## 🔐 認証・認可

### 認証フロー

#### 1. ユーザー登録
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password123",
  "display_name": "ユーザー名",
  "first_name": "名",
  "last_name": "姓"
}
```

#### 2. ログイン
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password123"
}
```

#### 3. トークン更新
```http
POST /auth/refresh
Authorization: Bearer <refresh_token>
```

### 認証ヘッダー
```http
Authorization: Bearer <access_token>
```

### トークン情報
- **アクセストークン**: 有効期限1時間
- **リフレッシュトークン**: 有効期限7日
- **トークン形式**: JWT

---

## 📡 エンドポイント一覧

### 認証・ユーザー管理

#### ユーザー登録
```http
POST /auth/register
```

**リクエスト**:
```json
{
  "email": "user@example.com",
  "password": "secure_password123",
  "display_name": "ユーザー名",
  "first_name": "名",
  "last_name": "姓",
  "timezone": "Asia/Tokyo",
  "language": "ja"
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "email": "user@example.com",
    "display_name": "ユーザー名",
    "email_verified": false,
    "created_at": "2024-12-01T10:00:00Z"
  },
  "message": "ユーザー登録が完了しました"
}
```

#### ログイン
```http
POST /auth/login
```

**リクエスト**:
```json
{
  "email": "user@example.com",
  "password": "secure_password123"
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "access_token": "jwt_token",
    "refresh_token": "jwt_refresh_token",
    "expires_in": 3600,
    "user": {
      "user_id": "uuid",
      "email": "user@example.com",
      "display_name": "ユーザー名",
      "last_login": "2024-12-01T10:00:00Z"
    }
  },
  "message": "ログインに成功しました"
}
```

#### ログアウト
```http
POST /auth/logout
Authorization: Bearer <access_token>
```

#### パスワードリセット要求
```http
POST /auth/password-reset-request
```

**リクエスト**:
```json
{
  "email": "user@example.com"
}
```

#### パスワードリセット実行
```http
POST /auth/password-reset
```

**リクエスト**:
```json
{
  "token": "reset_token",
  "new_password": "new_secure_password123"
}
```

### ユーザープロフィール

#### プロフィール取得
```http
GET /users/profile
Authorization: Bearer <access_token>
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "email": "user@example.com",
    "display_name": "ユーザー名",
    "first_name": "名",
    "last_name": "姓",
    "avatar_url": "https://example.com/avatar.jpg",
    "bio": "自己紹介",
    "timezone": "Asia/Tokyo",
    "language": "ja",
    "email_verified": true,
    "account_status": "active",
    "created_at": "2024-12-01T10:00:00Z",
    "last_active": "2024-12-01T10:00:00Z"
  }
}
```

#### プロフィール更新
```http
PUT /users/profile
Authorization: Bearer <access_token>
```

**リクエスト**:
```json
{
  "display_name": "新しいユーザー名",
  "first_name": "新しい名",
  "last_name": "新しい姓",
  "bio": "新しい自己紹介"
}
```

### 練習セッション管理

#### 練習タイプ一覧取得
```http
GET /practice/types
Authorization: Bearer <access_token>
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "categories": [
      {
        "category_id": 1,
        "category_name": "exam_prep",
        "display_name": "採用試験系",
        "icon": "📄",
        "color": "#667eea",
        "types": [
          {
            "practice_type_id": 1,
            "type_name": "standard_exam",
            "display_name": "標準採用試験",
            "description": "医学論文のAbstract読解と意見陳述",
            "difficulty_level": 2,
            "estimated_duration_minutes": 60
          }
        ]
      }
    ]
  }
}
```

#### セッション開始
```http
POST /practice/sessions
Authorization: Bearer <access_token>
```

**リクエスト**:
```json
{
  "practice_type_id": 1,
  "theme": "循環器疾患の治療"
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "practice_type_id": 1,
    "theme": "循環器疾患の治療",
    "start_time": "2024-12-01T10:00:00Z",
    "status": "in_progress"
  }
}
```

#### セッション完了
```http
PUT /practice/sessions/{session_id}/complete
Authorization: Bearer <access_token>
```

**リクエスト**:
```json
{
  "inputs": [
    {
      "input_type": "translation",
      "content": "翻訳内容",
      "word_count": 150
    },
    {
      "input_type": "opinion",
      "content": "意見内容",
      "word_count": 200
    }
  ],
  "completion_percentage": 100.0
}
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "session_id": "uuid",
    "status": "completed",
    "scores": [
      {
        "score_category": "翻訳評価",
        "score_value": 8.5,
        "max_score": 10.0,
        "feedback": "翻訳は正確で、専門用語の使用も適切です"
      },
      {
        "score_category": "意見評価",
        "score_value": 7.0,
        "max_score": 10.0,
        "feedback": "論理的思考は良好ですが、より具体的な提案があると良いでしょう"
      }
    ],
    "overall_feedback": "総合的に良好な回答です。翻訳の精度をさらに向上させるとより良い結果が期待できます。"
  }
}
```

### 履歴・分析

#### 練習履歴取得
```http
GET /practice/history
Authorization: Bearer <access_token>
```

**クエリパラメータ**:
- `practice_type_id` (optional): 練習タイプID
- `limit` (optional): 取得件数 (default: 50)
- `offset` (optional): オフセット (default: 0)
- `status` (optional): セッション状態 (completed, abandoned)

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "sessions": [
      {
        "session_id": "uuid",
        "practice_type_id": 1,
        "practice_type_name": "標準採用試験",
        "theme": "循環器疾患の治療",
        "start_time": "2024-12-01T10:00:00Z",
        "end_time": "2024-12-01T11:00:00Z",
        "duration_seconds": 3600,
        "status": "completed",
        "completion_percentage": 100.0,
        "scores": [
          {
            "score_category": "翻訳評価",
            "score_value": 8.5,
            "max_score": 10.0
          }
        ],
        "overall_score": 7.75
      }
    ],
    "pagination": {
      "total": 100,
      "limit": 50,
      "offset": 0,
      "has_next": true
    }
  }
}
```

#### 統計データ取得
```http
GET /practice/statistics
Authorization: Bearer <access_token>
```

**クエリパラメータ**:
- `practice_type_id` (optional): 練習タイプID
- `days_back` (optional): 過去何日分 (default: 30)

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "overall": {
      "total_sessions": 150,
      "total_duration_hours": 75.5,
      "average_score": 7.8,
      "best_score": 9.5,
      "streak_days": 7
    },
    "by_type": [
      {
        "practice_type_id": 1,
        "practice_type_name": "標準採用試験",
        "total_sessions": 50,
        "average_score": 8.2,
        "best_score": 9.5
      }
    ],
    "trends": {
      "daily_scores": [
        {
          "date": "2024-12-01",
          "average_score": 8.0,
          "session_count": 3
        }
      ]
    }
  }
}
```

#### スコア推移取得
```http
GET /practice/trends
Authorization: Bearer <access_token>
```

**クエリパラメータ**:
- `practice_type_id` (optional): 練習タイプID
- `score_category` (optional): スコアカテゴリ
- `days_back` (optional): 過去何日分 (default: 30)

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "trends": [
      {
        "date": "2024-12-01",
        "scores": [
          {
            "score_category": "翻訳評価",
            "score_value": 8.5,
            "session_count": 2
          },
          {
            "score_category": "意見評価",
            "score_value": 7.0,
            "session_count": 2
          }
        ]
      }
    ],
    "improvement": {
      "overall": 0.5,
      "by_category": {
        "翻訳評価": 0.8,
        "意見評価": 0.3
      }
    }
  }
}
```

### 設定管理

#### ユーザー設定取得
```http
GET /users/settings
Authorization: Bearer <access_token>
```

**レスポンス**:
```json
{
  "success": true,
  "data": {
    "learning_goals": {
      "daily_practice_goal": 1,
      "weekly_practice_goal": 7,
      "target_score": 8.0
    },
    "notifications": {
      "email_notifications": true,
      "practice_reminders": true,
      "achievement_notifications": true
    },
    "preferences": {
      "preferred_difficulty": 2,
      "auto_save_enabled": true,
      "show_hints": true,
      "theme": "light"
    }
  }
}
```

#### ユーザー設定更新
```http
PUT /users/settings
Authorization: Bearer <access_token>
```

**リクエスト**:
```json
{
  "learning_goals": {
    "daily_practice_goal": 2,
    "target_score": 8.5
  },
  "notifications": {
    "practice_reminders": false
  },
  "preferences": {
    "theme": "dark"
  }
}
```

---

## 📊 データ形式

### 共通データ型

#### 日時形式
```json
{
  "timestamp": "2024-12-01T10:00:00Z"
}
```

#### エラー形式
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "入力データが無効です",
    "details": {
      "field": "email",
      "reason": "無効なメールアドレス形式です"
    }
  },
  "timestamp": "2024-12-01T10:00:00Z"
}
```

#### ページネーション形式
```json
{
  "pagination": {
    "total": 1000,
    "limit": 50,
    "offset": 0,
    "has_next": true,
    "has_prev": false
  }
}
```

### 練習セッション関連

#### セッション状態
```json
{
  "status": "in_progress" | "completed" | "abandoned" | "error"
}
```

#### 入力タイプ
```json
{
  "input_type": "translation" | "opinion" | "essay" | "answer" | "question"
}
```

#### スコアカテゴリ
```json
{
  "score_category": "翻訳評価" | "意見評価" | "臨床的正確性" | "実践的思考" | "包括性" | "論理構成"
}
```

---

## ⚠️ エラーハンドリング

### HTTPステータスコード

| コード | 説明 |
|--------|------|
| 200 | 成功 |
| 201 | 作成成功 |
| 400 | リクエストエラー |
| 401 | 認証エラー |
| 403 | 認可エラー |
| 404 | リソースが見つかりません |
| 422 | バリデーションエラー |
| 429 | レート制限超過 |
| 500 | サーバーエラー |

### エラーコード一覧

| コード | 説明 |
|--------|------|
| `AUTHENTICATION_FAILED` | 認証に失敗しました |
| `INVALID_TOKEN` | 無効なトークンです |
| `TOKEN_EXPIRED` | トークンの有効期限が切れています |
| `INSUFFICIENT_PERMISSIONS` | 権限が不足しています |
| `VALIDATION_ERROR` | 入力データが無効です |
| `RESOURCE_NOT_FOUND` | リソースが見つかりません |
| `RATE_LIMIT_EXCEEDED` | レート制限を超過しました |
| `INTERNAL_SERVER_ERROR` | 内部サーバーエラー |

### エラーレスポンス例

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "入力データが無効です",
    "details": [
      {
        "field": "email",
        "reason": "無効なメールアドレス形式です"
      },
      {
        "field": "password",
        "reason": "パスワードは8文字以上である必要があります"
      }
    ]
  },
  "timestamp": "2024-12-01T10:00:00Z"
}
```

---

## 🚦 レート制限

### 制限値

| エンドポイント | 制限 | 期間 |
|---------------|------|------|
| 認証関連 | 10回/分 | 1分 |
| 練習セッション作成 | 5回/分 | 1分 |
| 履歴取得 | 100回/分 | 1分 |
| 統計取得 | 30回/分 | 1分 |

### レート制限ヘッダー

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

### レート制限超過時のレスポンス

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "レート制限を超過しました",
    "retry_after": 60
  }
}
```

---

## 💻 実装例

### Python (requests)

```python
import requests
import json

class MedicalExamAPI:
    def __init__(self, base_url, access_token=None):
        self.base_url = base_url
        self.access_token = access_token
        self.session = requests.Session()
        
        if access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            })
    
    def login(self, email, password):
        """ユーザーログイン"""
        response = self.session.post(
            f"{self.base_url}/auth/login",
            json={
                "email": email,
                "password": password
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data['data']['access_token']
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            return data['data']
        else:
            raise Exception(f"ログインに失敗しました: {response.text}")
    
    def get_practice_history(self, practice_type_id=None, limit=50, offset=0):
        """練習履歴を取得"""
        params = {
            'limit': limit,
            'offset': offset
        }
        if practice_type_id:
            params['practice_type_id'] = practice_type_id
        
        response = self.session.get(
            f"{self.base_url}/practice/history",
            params=params
        )
        
        if response.status_code == 200:
            return response.json()['data']
        else:
            raise Exception(f"履歴取得に失敗しました: {response.text}")
    
    def start_practice_session(self, practice_type_id, theme=None):
        """練習セッションを開始"""
        data = {
            "practice_type_id": practice_type_id
        }
        if theme:
            data["theme"] = theme
        
        response = self.session.post(
            f"{self.base_url}/practice/sessions",
            json=data
        )
        
        if response.status_code == 201:
            return response.json()['data']
        else:
            raise Exception(f"セッション開始に失敗しました: {response.text}")
    
    def complete_practice_session(self, session_id, inputs, completion_percentage=100.0):
        """練習セッションを完了"""
        data = {
            "inputs": inputs,
            "completion_percentage": completion_percentage
        }
        
        response = self.session.put(
            f"{self.base_url}/practice/sessions/{session_id}/complete",
            json=data
        )
        
        if response.status_code == 200:
            return response.json()['data']
        else:
            raise Exception(f"セッション完了に失敗しました: {response.text}")

# 使用例
api = MedicalExamAPI("https://your-app.streamlit.app/api/v1")

# ログイン
user_data = api.login("user@example.com", "password123")

# 練習履歴取得
history = api.get_practice_history(limit=10)

# セッション開始
session = api.start_practice_session(1, "循環器疾患の治療")

# セッション完了
result = api.complete_practice_session(
    session['session_id'],
    [
        {
            "input_type": "translation",
            "content": "翻訳内容",
            "word_count": 150
        },
        {
            "input_type": "opinion",
            "content": "意見内容",
            "word_count": 200
        }
    ]
)
```

### JavaScript (fetch)

```javascript
class MedicalExamAPI {
    constructor(baseUrl, accessToken = null) {
        this.baseUrl = baseUrl;
        this.accessToken = accessToken;
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        if (this.accessToken) {
            config.headers['Authorization'] = `Bearer ${this.accessToken}`;
        }
        
        const response = await fetch(url, config);
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error?.message || 'APIリクエストに失敗しました');
        }
        
        return response.json();
    }
    
    async login(email, password) {
        const data = await this.request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });
        
        this.accessToken = data.data.access_token;
        return data.data;
    }
    
    async getPracticeHistory(practiceTypeId = null, limit = 50, offset = 0) {
        const params = new URLSearchParams({
            limit: limit.toString(),
            offset: offset.toString()
        });
        
        if (practiceTypeId) {
            params.append('practice_type_id', practiceTypeId.toString());
        }
        
        const data = await this.request(`/practice/history?${params}`);
        return data.data;
    }
    
    async startPracticeSession(practiceTypeId, theme = null) {
        const body = { practice_type_id: practiceTypeId };
        if (theme) body.theme = theme;
        
        const data = await this.request('/practice/sessions', {
            method: 'POST',
            body: JSON.stringify(body)
        });
        
        return data.data;
    }
    
    async completePracticeSession(sessionId, inputs, completionPercentage = 100.0) {
        const data = await this.request(`/practice/sessions/${sessionId}/complete`, {
            method: 'PUT',
            body: JSON.stringify({
                inputs,
                completion_percentage: completionPercentage
            })
        });
        
        return data.data;
    }
}

// 使用例
const api = new MedicalExamAPI('https://your-app.streamlit.app/api/v1');

// ログイン
const userData = await api.login('user@example.com', 'password123');

// 練習履歴取得
const history = await api.getPracticeHistory(null, 10);

// セッション開始
const session = await api.startPracticeSession(1, '循環器疾患の治療');

// セッション完了
const result = await api.completePracticeSession(
    session.session_id,
    [
        {
            input_type: 'translation',
            content: '翻訳内容',
            word_count: 150
        },
        {
            input_type: 'opinion',
            content: '意見内容',
            word_count: 200
        }
    ]
);
```

---

*このドキュメントは継続的に更新されます。最新版はGitHubリポジトリで確認してください。* 