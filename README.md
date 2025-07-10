# 医学部採用試験対策アプリ

医学部採用試験の各種対策（採用試験、小論文、面接、自由記述、英語読解）を総合的にサポートするStreamlitアプリケーションです。

## 🌟 機能

- **📄 採用試験対策**: 論文検索、日本語訳、小論文作成
- **✍️ 小論文対策**: テーマ別小論文練習
- **🗣️ 面接対策**: AI面接練習
- **📝 自由記述対策**: 医学部頻出テーマでの記述練習（75テーマ収録）
- **📖 英語読解**: 医学系英語論文の読解練習
- **📚 学習履歴**: 進捗追跡と成績分析

## 🚀 セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/your-username/medical_exam_prep_app.git
cd medical_exam_prep_app
```

### 2. 依存関係のインストール

```bash
pip install uv
uv sync
```

### 3. APIキーの設定

#### Google AI APIキー
1. [Google AI Studio](https://aistudio.google.com/)でAPIキーを取得
2. 環境変数またはStreamlit secretsに設定：

**環境変数での設定:**
```bash
export GOOGLE_API_KEY="your-google-api-key"
```

**Streamlit secretsでの設定:**
`.streamlit/secrets.toml` ファイルを作成：
```toml
GOOGLE_API_KEY = "your-google-api-key"
```

### 4. データベース設定（Supabase - 推奨）

#### 4.1 Supabaseプロジェクトの作成

1. [Supabase](https://supabase.com/)でアカウント作成（無料）
2. 新しいプロジェクトを作成
3. プロジェクトの設定から以下の情報を取得：
   - `Project URL`
   - `Anon public` API key

#### 4.2 データベーステーブルの作成

SupabaseのSQL Editorで以下のSQLを実行：

```sql
-- セッション管理テーブル
CREATE TABLE user_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW()
);

-- 練習履歴テーブル
CREATE TABLE practice_history (
    id SERIAL PRIMARY KEY,
    session_id TEXT REFERENCES user_sessions(session_id),
    practice_type TEXT NOT NULL,
    practice_date TIMESTAMP NOT NULL,
    inputs JSONB NOT NULL,
    feedback TEXT,
    scores JSONB,
    duration_seconds INTEGER,
    duration_display TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- インデックス
CREATE INDEX idx_practice_history_session_type ON practice_history(session_id, practice_type);
CREATE INDEX idx_practice_history_date ON practice_history(practice_date DESC);
```

#### 4.3 Supabase認証情報の設定

**環境変数での設定:**
```bash
export SUPABASE_URL="https://your-project-id.supabase.co"
export SUPABASE_ANON_KEY="your-anon-key"
```

**Streamlit secretsでの設定:**
`.streamlit/secrets.toml` に追記：
```toml
SUPABASE_URL = "https://your-project-id.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
```

### 5. アプリケーションの起動

```bash
uv run streamlit run app.py
```

## 📊 データベース機能

### 履歴の永続化

- **Streamlit Cloud**: Supabaseデータベースで完全な永続化
- **ローカル実行**: Supabaseまたはローカルファイルに保存
- **オフライン**: セッション状態でのフォールバック機能

### セッション管理

- ユーザーごとに一意のセッションIDを生成
- 履歴データはセッションID別に分離
- アクティブ時間の自動追跡

### データエクスポート

- 履歴データのJSON形式でのダウンロード
- 学習進捗の外部バックアップ対応

## 🏗️ アーキテクチャ

```
medical_exam_prep_app/
├── app.py                      # メインアプリケーション
├── modules/
│   ├── database.py            # Supabaseデータベース管理
│   ├── utils.py               # 共通ユーティリティ
│   ├── medical_knowledge_checker.py  # 自由記述AI評価
│   ├── essay_scorer.py        # 小論文AI評価
│   ├── interview_prepper.py   # 面接AI対話
│   └── paper_finder.py        # 論文検索・分析
├── pages/
│   ├── 01_県総_採用試験.py     # 採用試験対策
│   ├── 02_小論文.py           # 小論文対策
│   ├── 03_面接.py             # 面接対策
│   ├── 04_自由記述.py          # 自由記述対策
│   ├── 05_英語読解.py          # 英語読解
│   └── 06_学習履歴.py          # 総合学習履歴
└── history/                   # ローカル履歴（フォールバック）
```

## 🎯 特徴

### 自由記述対策
- **75テーマ収録**: 循環器、内分泌、血液、呼吸器、消化器、外科、整形、産婦人科、小児、救急、麻酔
- **8つの問題形式**: 基本知識型、患者説明型、臨床評価型、鑑別診断型など
- **履歴追跡**: テーマ別学習履歴とスコア推移
- **重複回避**: 類似テーマの自動判定と回避

### AI評価システム
- **医学部採用試験基準**: 実際の採点基準に準拠
- **4観点評価**: 臨床的正確性、実践的思考、包括性、論理構成
- **ストリーミング表示**: リアルタイムフィードバック

## 🔧 トラブルシューティング

### データベース接続エラー
1. Supabase認証情報が正しく設定されているか確認
2. プロジェクトURLとAPIキーの有効性を確認
3. ネットワーク接続を確認

### フォールバック機能
- データベース接続に失敗した場合、自動的にセッション状態またはローカルファイルに保存
- アプリケーションは接続状況に関わらず動作継続

## 📄 ライセンス

MIT License

## 🤝 貢献

プルリクエストやイシューの報告を歓迎します。

## 📞 サポート

問題や質問がある場合は、GitHubのIssuesページでお知らせください。
