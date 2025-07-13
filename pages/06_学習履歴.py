import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

# 新しいデータベースシステムのインポート
try:
    from modules.database_adapter_v3 import DatabaseAdapterV3
    from modules.session_manager import StreamlitSessionManager
    
    # アダプターとセッション管理の初期化
    session_manager = StreamlitSessionManager()
    current_session = session_manager.get_user_session()
    db_adapter = DatabaseAdapterV3()
    database_available = True
    
    # セッション状態の表示用
    session_status = {
        "authenticated": current_session.is_persistent,
        "method": current_session.identification_method.value,
        "persistence": "enabled" if current_session.is_persistent else "temporary",
        "user_id": current_session.user_id,
        "expires_at": (current_session.last_active + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S') if current_session.is_persistent else None
    }
    
except ImportError as e:
    st.warning(f"新しいデータベースシステムが利用できません: {e}")
    database_available = False
    session_status = {"authenticated": False, "persistence": "none"}

# 必要な関数のインポート
try:
    from modules.utils import extract_scores
except ImportError:
    def extract_scores(feedback_text):
        """フォールバック関数: フィードバックからスコアを抽出"""
        scores = {}
        lines = feedback_text.split('\n')
        for line in lines:
            if '/10' in line or '点' in line:
                # 簡単なスコア抽出ロジック
                import re
                score_match = re.search(r'(\d+(?:\.\d+)?)\s*[/:]?\s*(?:10|点)', line)
                if score_match:
                    score_value = float(score_match.group(1))
                    if '翻訳' in line:
                        scores['翻訳評価'] = score_value
                    elif '意見' in line:
                        scores['意見評価'] = score_value
                    elif '総合' in line:
                        scores['総合評価'] = score_value
        return scores

# 採点関数のインポート
try:
    from modules.scorer import score_exam_stream, score_reading_stream, score_exam_style_stream
    from modules.essay_scorer import score_long_essay_stream
    from modules.medical_knowledge_checker import score_medical_answer_stream
    from modules.interview_prepper import score_interview_answer_stream
except ImportError as e:
    st.error(f"採点モジュールのインポートエラー: {e}")

# ページ設定
st.set_page_config(
    page_title="学習履歴", 
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📚 学習履歴")

# セッション状態とデータベース接続状況の表示
if database_available:
    with st.expander("🔐 セッション・データベース状況", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### セッション状況")
            if session_status["authenticated"]:
                st.success(f"✅ **認証済み**: {session_status['method']}")
                st.info(f"🔄 **持続性**: {session_status['persistence']}")
                if session_status.get('user_id'):
                    st.caption(f"👤 **ユーザーID**: {session_status['user_id'][:12]}...")
                if session_status.get('expires_at'):
                    st.caption(f"⏰ **有効期限**: {session_status['expires_at']}")
            else:
                st.warning("⚠️ **認証なし**: セッションが特定できていません")
                st.info("💡 データは匿名セッションとして保存されます")
        
        with col2:
            st.markdown("#### データベース状況")
            try:
                # データベース接続テスト
                test_result = db_adapter.test_connection()
                if test_result.get("test_result") == "success" or test_result.get("available", False):
                    st.success("🌐 **Supabase**: 接続正常")
                    if test_result.get("exercise_types_count") is not None:
                        st.metric("📊 **演習タイプ数**", test_result["exercise_types_count"])
                    if test_result.get("current_user_id"):
                        st.caption(f"👤 **ユーザーID**: {test_result['current_user_id'][:12]}...")
                else:
                    st.error(f"❌ **接続エラー**: {test_result.get('error', '不明')}")
            except Exception as e:
                st.error(f"❌ **接続テストエラー**: {e}")

# データベース分析を表示
if database_available:
    with st.expander("🔍 データベース分析", expanded=False):
        if st.button("📊 練習履歴分析を実行"):
            with st.spinner("データベースを分析中..."):
                try:
                    analysis = db_adapter.analyze_user_history()
                    
                    if "error" in analysis:
                        st.error(f"分析エラー: {analysis['error']}")
                    else:
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("総練習回数", analysis.get("total_sessions", 0))
                        with col2:
                            st.metric("練習日数", analysis.get("practice_days", 0))
                        with col3:
                            st.metric("平均スコア", f"{analysis.get('average_score', 0):.1f}")
                        
                        # 練習タイプ別統計
                        if analysis.get("by_practice_type"):
                            st.subheader("📋 練習タイプ別実績")
                            type_stats = []
                            for practice_type, stats in analysis["by_practice_type"].items():
                                type_stats.append({
                                    "練習タイプ": practice_type,
                                    "回数": stats.get("count", 0),
                                    "平均スコア": stats.get("avg_score", 0),
                                    "最高スコア": stats.get("max_score", 0),
                                    "最終練習日": stats.get("last_practice", "")
                                })
                            
                            if type_stats:
                                stats_df = pd.DataFrame(type_stats)
                                st.dataframe(stats_df, use_container_width=True)
                                
                                # 進捗チャート
                                if len(stats_df) > 1:
                                    fig = px.bar(stats_df, x="練習タイプ", y="回数", 
                                               title="練習タイプ別実施回数")
                                    st.plotly_chart(fig, use_container_width=True)
                        
                        # 時系列分析
                        if analysis.get("timeline"):
                            st.subheader("📈 学習進捗タイムライン")
                            timeline_data = analysis["timeline"]
                            if timeline_data:
                                timeline_df = pd.DataFrame(timeline_data)
                                fig = px.line(timeline_df, x="date", y="score", 
                                            color="practice_type", title="スコア推移")
                                st.plotly_chart(fig, use_container_width=True)
                
                except Exception as e:
                    st.error(f"分析処理エラー: {e}")
else:
    st.warning("データベース機能が利用できません。ローカルファイルのみ表示します。")

# モダンなカスタムCSS
st.markdown("""
<style>
    /* メインヘッダー */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.2);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 600;
        letter-spacing: -0.5px;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 1.1rem;
    }

    /* 統計カード */
    .stats-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }
    
    .stat-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
    }
    
    .stat-card.primary { border-color: #667eea; }
    .stat-card.success { border-color: #22c55e; }
    .stat-card.warning { border-color: #f59e0b; }
    .stat-card.info { border-color: #3b82f6; }
    
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1f2937;
        margin: 0;
    }
    
    .stat-label {
        font-size: 0.9rem;
        color: #6b7280;
        margin: 0.25rem 0 0 0;
        font-weight: 500;
    }

    /* タイムライン */
    .timeline-container {
        position: relative;
        margin: 2rem 0;
    }
    
    .timeline-item {
        position: relative;
        background: white;
        border-radius: 12px;
        margin: 1.5rem 0;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border-left: 4px solid #e5e7eb;
        transition: all 0.3s ease;
    }
    
    .timeline-item:hover {
        transform: translateX(8px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
        border-left-color: #667eea;
    }
    
    .timeline-item.type-採用試験 { border-left-color: #667eea; }
    .timeline-item.type-小論文 { border-left-color: #22c55e; }
    .timeline-item.type-面接 { border-left-color: #f59e0b; }
    .timeline-item.type-英語読解 { border-left-color: #3b82f6; }
    .timeline-item.type-自由記述 { border-left-color: #8b5cf6; }
    
    .timeline-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
    }
    
    .timeline-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1f2937;
        margin: 0;
    }
    
    .timeline-date {
        font-size: 0.9rem;
        color: #6b7280;
        background: #f3f4f6;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
    }
    
    .timeline-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
        color: white;
        margin-left: 0.5rem;
    }
    
    .badge-採用試験 { background: #667eea; }
    .badge-小論文 { background: #22c55e; }
    .badge-面接 { background: #f59e0b; }
    .badge-英語読解 { background: #3b82f6; }
    .badge-自由記述 { background: #8b5cf6; }

    /* スコアバッジ */
    .score-container {
        display: flex;
        gap: 0.75rem;
        margin: 1rem 0;
        flex-wrap: wrap;
    }
    
    .score-badge {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.5rem 0.75rem;
        text-align: center;
        min-width: 80px;
        transition: all 0.2s ease;
    }
    
    .score-badge:hover {
        transform: scale(1.05);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    .score-value {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1f2937;
        margin: 0;
    }
    
    .score-label {
        font-size: 0.75rem;
        color: #6b7280;
        margin: 0.25rem 0 0 0;
    }

    /* フィルターパネル */
    .filter-panel {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        margin-bottom: 1rem;
    }

    /* セクションヘッダー */
    .section-header {
        font-size: 1.5rem;
        font-weight: 600;
        color: #1f2937;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e5e7eb;
    }

    /* ナビゲーションボタン */
    .nav-button {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        text-align: center;
        transition: all 0.2s ease;
        cursor: pointer;
        text-decoration: none;
        color: #1f2937;
        font-weight: 500;
    }
    
    .nav-button:hover {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }

    /* エクスパンダーのスタイル */
    .streamlit-expanderHeader {
        background: #f8fafc;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }

    /* アニメーション */
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .animate-fade-in {
        animation: fadeInUp 0.6s ease-out;
    }

    /* プロットリーチャートのスタイル */
    .js-plotly-plot {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    }
</style>
""", unsafe_allow_html=True)

# ヘッダー
st.markdown("""
<div class="main-header animate-fade-in">
    <h1>📚 学習履歴</h1>
    <p>あなたの学習の軌跡と成長を可視化します</p>
</div>
""", unsafe_allow_html=True)

# データベース接続状況の詳細表示
if database_available:
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        # セッション状況の簡潔表示
        if session_status["authenticated"]:
            st.success(f"🌐 **セッション**: {session_status['method']} ({session_status['persistence']})")
        else:
            st.info("📱 **セッション**: 匿名モード")
    
    with col2:
        if st.button("🔄 履歴更新", help="履歴データを最新の状態に更新"):
            # キャッシュクリアのみ行い、自動的に再読み込みされるのを待つ
            st.cache_data.clear()
            st.success("💫 履歴データを更新しました！")
    
    with col3:
        # 履歴エクスポートボタン
        if st.button("💾 全履歴保存", help="全履歴をJSONファイルとして保存"):
            try:
                all_history = db_adapter.get_user_history()
                if all_history:
                    export_data = json.dumps(all_history, ensure_ascii=False, indent=2)
                    st.download_button(
                        label="📥 履歴ダウンロード",
                        data=export_data,
                        file_name=f"全学習履歴_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                else:
                    st.warning("ダウンロードする履歴がありません")
            except Exception as e:
                st.error(f"履歴の取得に失敗しました: {e}")
else:
    st.info("📱 **履歴保存**: ローカルファイル使用")

st.markdown("---")

# データの読み込み（Supabase対応）
@st.cache_data(ttl=600, show_spinner=False)  # スピナーを無効化
def load_and_process_history():
    """全練習タイプの履歴をSupabaseまたはローカルから読み込み"""
    try:
        if not database_available:
            return load_local_history()
        
        # 新しいアダプターシステムから全ての履歴を取得
        all_history = db_adapter.get_user_history()
        
        if not all_history:
            st.info("📝 まだ練習履歴がありません。各練習ページで問題を解いてみましょう！")
            return None, pd.DataFrame(), pd.DataFrame()
        
        # 日付順でソート（新しい順）
        all_history.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # 練習タイプ別の統計情報を取得
        practice_type_stats = {}
        for item in all_history:
            practice_type = item.get('type', '不明')
            if practice_type not in practice_type_stats:
                practice_type_stats[practice_type] = 0
            practice_type_stats[practice_type] += 1
        
        # デバッグ情報: 取得された練習タイプを表示    
        if practice_type_stats:
            st.sidebar.info(f"📊 取得された練習タイプ ({len(practice_type_stats)}種類):\n" + 
                          "\n".join([f"• {practice_type} ({count}件)" 
                                   for practice_type, count in sorted(practice_type_stats.items())]))
        
        # DataFrameに変換（改良版）
        rows = []
        for item in all_history:
            try:
                # 基本情報
                row = {
                    '日付': item.get('date', ''),
                    '練習タイプ': item.get('type', ''),
                    '表示名': item.get('display_name', item.get('type', '')),
                    'カテゴリ': item.get('category', ''),
                    'サブカテゴリ': item.get('subcategory', ''),
                    '時間': item.get('duration_display', ''),
                    'フィードバック': item.get('feedback', ''),
                    'スコア有無': bool(item.get('scores')),
                    'エラー有無': 'エラー' in item.get('feedback', '') or 'UNAVAILABLE' in item.get('feedback', '')
                }
                
                # スコア情報の抽出
                scores = item.get('scores', {})
                if scores and isinstance(scores, dict):
                    for score_name, score_value in scores.items():
                        if isinstance(score_value, (int, float)):
                            row[f'スコア_{score_name}'] = score_value
                
                rows.append(row)
                
            except Exception as e:
                st.error(f"データ処理エラー: {e}")
                continue
        
        if not rows:
            return None, pd.DataFrame(), pd.DataFrame()
        
        df = pd.DataFrame(rows)
        
        # 日付を適切な形式に変換
        try:
            df['日付'] = pd.to_datetime(df['日付'])
        except:
            # 日付の変換に失敗した場合はそのまま使用
            pass
        
        # 統計データフレームを作成
        stats_rows = []
        
        # カテゴリ別統計
        for category in df['カテゴリ'].unique():
            category_df = df[df['カテゴリ'] == category]
            stats_rows.append({
                '分類': 'カテゴリ',
                '名前': category,
                '練習回数': len(category_df),
                '最新日付': category_df['日付'].max() if len(category_df) > 0 else None,
                'エラー件数': len(category_df[category_df['エラー有無'] == True])
            })
        
        # 練習タイプ別統計
        for practice_type in df['練習タイプ'].unique():
            type_df = df[df['練習タイプ'] == practice_type]
            # 表示名をそのまま使用（DatabaseAdapterが適切な名前を返す）
            display_name = practice_type
            stats_rows.append({
                '分類': '練習タイプ',
                '名前': display_name,
                '練習回数': len(type_df),
                '最新日付': type_df['日付'].max() if len(type_df) > 0 else None,
                'エラー件数': len(type_df[type_df['エラー有無'] == True])
            })
        
        stats_df = pd.DataFrame(stats_rows)
        
        return all_history, df, stats_df
        
    except Exception as e:
        st.error(f"履歴の読み込みでエラーが発生しました: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None, pd.DataFrame(), pd.DataFrame()

def load_local_history():
    """ローカルファイルから履歴を読み込み"""
    history_file = Path("history.json")
    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history_data = json.load(f)
            return history_data, _process_to_dataframes(history_data)
        except json.JSONDecodeError:
            st.error("履歴ファイルのデコードに失敗しました。")
            return None, pd.DataFrame(), pd.DataFrame()
    else:
        st.info("履歴ファイルが見つかりません。")
        return None, pd.DataFrame(), pd.DataFrame()

def _process_to_dataframes(history_data):
    """履歴データをDataFrameに変換"""
    df_data = []
    score_data = []
    
    for item in history_data:
        try:
            date = pd.to_datetime(item['date'])
        except (ValueError, TypeError, KeyError):
            # 日付パースエラーの場合は現在時刻を使用
            date = pd.to_datetime('now')
            
        item_type = item.get('type', '不明')
        duration_seconds = item.get('duration_seconds', 0)
        duration_display = item.get('duration_display', '未記録')
        
        df_data.append({
            'date': date,
            'type': item_type,
            'has_scores': bool(item.get('scores')),
            'duration_seconds': duration_seconds,
            'duration_display': duration_display
        })
        
        # 新しいDB設計に対応したスコア処理
        scores = item.get('scores', {})
        if isinstance(scores, dict):
            # 旧形式のスコアデータ
            for category, score in scores.items():
                try:
                    score_value = float(score) if score is not None else 0
                except (ValueError, TypeError):
                    score_value = 0
                    
                score_data.append({
                    'date': date,
                    'type': item_type,
                    'category': category,
                    'score': score_value,
                    'duration_seconds': duration_seconds,
                    'duration_display': duration_display
                })
        elif isinstance(scores, list):
            # 新しいDB設計のスコアデータ（リスト形式）
            for score_item in scores:
                if isinstance(score_item, dict):
                    category = score_item.get('score_category', '不明')
                    score_value = score_item.get('score_value', 0)
                    max_score = score_item.get('max_score', 10)
                    
                    # 百分率スコアを計算
                    percentage_score = (score_value / max_score) * 10 if max_score > 0 else 0
                    
                    score_data.append({
                        'date': date,
                        'type': item_type,
                        'category': category,
                        'score': percentage_score,
                        'duration_seconds': duration_seconds,
                        'duration_display': duration_display
                    })
    
    df_base = pd.DataFrame(df_data)
    df_scores = pd.DataFrame(score_data)
    
    return df_base, df_scores

history, df_base, df_scores = load_and_process_history()

if history is None:
    st.markdown("""
    <div style="text-align: center; padding: 3rem; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);">
        <h3 style="color: #6b7280; margin: 0 0 1rem 0;">📝 まだ学習履歴がありません</h3>
        <p style="color: #9ca3af; margin: 0 0 2rem 0;">各対策ページで練習すると、結果がここに記録されます</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="section-header">🚀 練習を始めましょう</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📄 採用試験", use_container_width=True, type="primary"):
            st.switch_page("pages/01_採用試験.py")
    with col2:
        if st.button("✍️ 小論文対策", use_container_width=True):
            st.switch_page("pages/02_小論文.py")
    with col3:
        if st.button("🗣️ 面接対策", use_container_width=True):
            st.switch_page("pages/03_面接.py")
    with col4:
        if st.button("📖 英語読解", use_container_width=True):
            st.switch_page("pages/05_英語読解.py")
    st.stop()

# サイドバー: フィルタリング
with st.sidebar:
    st.markdown("### 学習履歴")
    
    # セッション状態の表示
    try:
        from modules.session_manager import session_manager
        current_session = session_manager.get_user_session()
        if current_session.is_persistent:
            st.success(f"🔐 セッション: {current_session.identification_method.value}")
        else:
            st.info("🔐 セッション: 一時的")
    except Exception as e:
        st.warning("🔐 セッション: 状態不明")
    
    st.markdown("---")
    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    st.markdown("### 🔍 フィルター設定")
    
    date_range_option = st.selectbox(
        "📅 期間",
        ["全期間", "過去7日間", "過去30日間", "過去90日間", "カスタム"],
    )
    
    today = datetime.now().date()
    min_date = df_base['日付'].min().date()
    max_date = df_base['日付'].max().date()

    if date_range_option == "カスタム":
        start_date = st.date_input("開始日", min_date, min_value=min_date, max_value=max_date)
        end_date = st.date_input("終了日", max_date, min_value=min_date, max_value=max_date)
    else:
        days = {'過去7日間': 7, '過去30日間': 30, '過去90日間': 90}.get(date_range_option, None)
        if days:
            start_date = today - timedelta(days=days)
        else: # 全期間
            start_date = min_date
        end_date = today

    available_types = df_base['練習タイプ'].unique().tolist()
    selected_types = st.multiselect("📚 練習タイプ", available_types, default=available_types, key="practice_type_filter")
    
    if not df_scores.empty and 'score' in df_scores.columns:
        score_min = int(df_scores['score'].min())
        score_max = int(df_scores['score'].max())
        score_range = st.slider(
            "📊 スコア範囲",
            min_value=score_min,
            max_value=score_max,
            value=(score_min, score_max)
        )
    else:
        score_range = (0, 10)  # デフォルト値
    
    st.markdown('</div>', unsafe_allow_html=True)

# データフィルタリング
base_mask_date = (df_base['日付'].dt.date >= start_date) & (df_base['日付'].dt.date <= end_date)
base_mask_type = df_base['練習タイプ'].isin(selected_types)
filtered_base = df_base[base_mask_date & base_mask_type]

if not df_scores.empty and 'score' in df_scores.columns:
    mask_date = (df_scores['date'].dt.date >= start_date) & (df_scores['date'].dt.date <= end_date)
    mask_type = df_scores['type'].isin(selected_types)
    mask_score = (df_scores['score'] >= score_range[0]) & (df_scores['score'] <= score_range[1]) if 'score_range' in locals() else pd.Series([True] * len(df_scores))
    filtered_scores = df_scores[mask_date & mask_type & mask_score]
else:
    filtered_scores = pd.DataFrame(columns=df_scores.columns if not df_scores.empty else [])

# タブ作成
tab1, tab2, tab3, tab4 = st.tabs(["📈 統計サマリー", "📊 詳細分析", "📋 履歴一覧", "🔧 エラー確認"])

with tab1:
    # 統計サマリータブ
    if filtered_base.empty:
        st.warning("選択されたフィルターに一致するデータがありません。")
    else:
        # サマリー統計
        st.markdown('<div class="section-header">📈 学習サマリー</div>', unsafe_allow_html=True)
        
        # 練習タイプ別の回数を棒グラフで表示（表示名を使用）
        if len(filtered_base) > 0:
            # 表示名マッピング（シンプル化）
            display_name_mapping = {}
            for practice_type in filtered_base['練習タイプ'].unique():
                display_name_mapping[practice_type] = practice_type
            
            # 表示名でグループ化してカウント
            filtered_base_with_display = filtered_base.copy()
            filtered_base_with_display['表示名'] = filtered_base_with_display['練習タイプ'].map(display_name_mapping)
            type_counts = filtered_base_with_display['表示名'].value_counts()
            
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                fig_type = px.bar(
                    x=type_counts.values, 
                    y=type_counts.index,
                    orientation='h',
                    title='練習タイプ別回数',
                    labels={'x': '回数', 'y': '練習タイプ'},
                    color=type_counts.values,
                    color_continuous_scale='Viridis'
                )
                fig_type.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_type, use_container_width=True)
            
            with col_chart2:
                # 曜日別練習回数
                filtered_base_copy = filtered_base.copy()
                filtered_base_copy['weekday'] = filtered_base_copy['日付'].dt.day_name()
                weekday_counts = filtered_base_copy['weekday'].value_counts()
                
                fig_weekday = px.bar(
                    x=weekday_counts.index,
                    y=weekday_counts.values,
                    title='曜日別練習回数',
                    labels={'x': '曜日', 'y': '回数'},
                    color=weekday_counts.values,
                    color_continuous_scale='Blues'
                )
                fig_weekday.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_weekday, use_container_width=True)

        total_practices = len(filtered_base)
        days_active = filtered_base['日付'].dt.date.nunique()

        # 統計カードをStreamlitのcolumnsで実装
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("""
            <div class="stat-card primary">
                <p class="stat-value">{}</p>
                <p class="stat-label">総練習回数</p>
            </div>
            """.format(total_practices), unsafe_allow_html=True)

        with col2:
            if not filtered_scores.empty and 'score' in filtered_scores.columns:
                avg_score = filtered_scores['score'].mean()
                st.markdown("""
                <div class="stat-card success">
                    <p class="stat-value">{:.1f}</p>
                    <p class="stat-label">平均スコア</p>
                </div>
                """.format(avg_score), unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="stat-card success">
                    <p class="stat-value">N/A</p>
                    <p class="stat-label">平均スコア</p>
                </div>
                """, unsafe_allow_html=True)

        with col3:
            if not filtered_scores.empty and 'score' in filtered_scores.columns:
                best_score = filtered_scores['score'].max()
                st.markdown("""
                <div class="stat-card warning">
                    <p class="stat-value">{}</p>
                    <p class="stat-label">最高スコア</p>
                </div>
                """.format(best_score), unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="stat-card warning">
                    <p class="stat-value">N/A</p>
                    <p class="stat-label">最高スコア</p>
                </div>
                """, unsafe_allow_html=True)

        with col4:
            # 平均所要時間の計算
            filtered_with_duration = filtered_base[filtered_base['duration_seconds'] > 0]
            if not filtered_with_duration.empty:
                avg_duration_seconds = filtered_with_duration['duration_seconds'].mean()
                avg_duration_minutes = int(avg_duration_seconds // 60)
                avg_duration_seconds_remainder = int(avg_duration_seconds % 60)
                duration_text = f"{avg_duration_minutes}分{avg_duration_seconds_remainder}秒"
            else:
                duration_text = "未記録"
            
            st.markdown("""
            <div class="stat-card info">
                <p class="stat-value" style="font-size: 1.5rem;">{}</p>
                <p class="stat-label">平均所要時間</p>
            </div>
            """.format(duration_text), unsafe_allow_html=True)

with tab2:
    # 詳細分析タブ
    st.markdown('<div class="section-header">📊 詳細分析</div>', unsafe_allow_html=True)
    subtab1, subtab2, subtab3 = st.tabs(["📈 スコア推移", "🎯 カテゴリ別分析", "📅 学習パターン"])

    with subtab1:
        if not filtered_scores.empty and 'score' in filtered_scores.columns and len(filtered_scores) > 1:
            fig = px.line(
                filtered_scores, 
                x='date', 
                y='score', 
                color='category',
                title='スコア推移',
                hover_data=['type'],
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(
                xaxis_title='日付', 
                yaxis_title='スコア', 
                yaxis=dict(range=[0, 10.5]),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Arial, sans-serif")
            )
            fig.update_traces(line=dict(width=3))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("📊 スコア付きのデータが2件以上ある場合にスコア推移が表示されます。")

    with subtab2:
        if not filtered_scores.empty and 'score' in filtered_scores.columns:
            category_stats = filtered_scores.groupby(['type', 'category']).agg(
                mean_score=('score', 'mean'),
                max_score=('score', 'max'),
                count=('score', 'count')
            ).round(1).reset_index()

            if len(category_stats) > 2:
                categories = category_stats['category'].unique()
                avg_scores_by_cat = category_stats.groupby('category')['mean_score'].mean()
                
                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=avg_scores_by_cat.values,
                    theta=avg_scores_by_cat.index,
                    fill='toself',
                    name='平均スコア',
                    line_color='rgb(102, 126, 234)',
                    fillcolor='rgba(102, 126, 234, 0.3)'
                ))
                fig_radar.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
                    title="カテゴリ別平均スコア",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(family="Arial, sans-serif")
                )
                st.plotly_chart(fig_radar, use_container_width=True)
            
            st.markdown("**📋 カテゴリ別統計**")
            st.dataframe(category_stats, use_container_width=True, hide_index=True)
        else:
            st.info("📊 スコア付きのデータがないため、カテゴリ別分析は表示できません。")

    with subtab3:
        # 曜日別練習回数
        filtered_base_copy = filtered_base.copy()
        filtered_base_copy['weekday'] = filtered_base_copy['日付'].dt.day_name()
        weekday_counts = filtered_base_copy['weekday'].value_counts()
        
        fig_weekday = px.bar(
            weekday_counts,
            title="曜日別練習回数",
            labels={'index': '曜日', 'value': '練習回数'},
            color_discrete_sequence=['#667eea']
        )
        fig_weekday.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Arial, sans-serif")
        )
        st.plotly_chart(fig_weekday, use_container_width=True)
        
        # 所要時間の推移
        filtered_with_duration = filtered_base[filtered_base['duration_seconds'] > 0]
        if not filtered_with_duration.empty and len(filtered_with_duration) > 1:
            # 分単位に変換
            filtered_with_duration_copy = filtered_with_duration.copy()
            filtered_with_duration_copy['duration_minutes'] = filtered_with_duration_copy['duration_seconds'] / 60
            
            fig_duration = px.line(
                filtered_with_duration_copy,
                x='日付',
                y='duration_minutes',
                color='練習タイプ',
                title='所要時間の推移',
                labels={'duration_minutes': '所要時間（分）', '日付': '日付'},
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_duration.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Arial, sans-serif")
            )
            fig_duration.update_traces(line=dict(width=3))
            st.plotly_chart(fig_duration, use_container_width=True)
        else:
            st.info("📊 所要時間が記録されているデータが2件以上ある場合に所要時間推移が表示されます。")

with tab3:
    # 履歴詳細タブ
    st.markdown('<div class="section-header">📜 練習履歴詳細</div>', unsafe_allow_html=True)
    
    # エクスポート
    if not filtered_scores.empty:
        csv_data = filtered_scores.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 表示中のデータをCSVでダウンロード",
            data=csv_data,
            file_name=f"学習履歴_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    # タイムライン形式の履歴表示
    st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
    
    filtered_history = []
    for item in history:
        item_date = pd.to_datetime(item.get('date'))
        # フィルタに合致するかチェック
        if not (
            item_date.date() >= start_date and
            item_date.date() <= end_date and
            item.get('type') in selected_types
        ):
            continue
    
        scores = item.get('scores')
        
        # スコア範囲フィルタのチェック
        if 'score_range' in locals() and scores:
            # このアイテムのいずれかのスコアが範囲内にあるか
            in_range = any(score_range[0] <= s <= score_range[1] for s in scores.values())
            if not in_range:
                continue
        
        filtered_history.append(item)
    
    if not filtered_history:
        st.info("選択されたフィルターに一致する履歴がありません。")
    else:
        for item in reversed(filtered_history[-20:]):  # 最新20件を表示
            item_date = pd.to_datetime(item.get('date'))
            date_str = item_date.strftime('%Y/%m/%d')
            time_str = item_date.strftime('%H:%M')
            item_type = item.get('type', '不明')
            display_name = item.get('display_name', item_type) if database_available else item_type
            duration_display = item.get('duration_display', '未記録')
            
            # タイムラインアイテムの作成
            timeline_item_html = f'''
            <div class="timeline-item type-{item_type}">
                <div class="timeline-header">
                    <h3 class="timeline-title">{display_name}
                        <span class="timeline-badge badge-{item_type}">{display_name}</span>
                    </h3>
                    <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem;">
                        <div class="timeline-date">{date_str} {time_str}</div>
                        <div style="font-size: 0.8rem; color: #6b7280; background: #f9fafb; padding: 0.125rem 0.5rem; border-radius: 12px;">
                            ⏱️ {duration_display}
                        </div>
                    </div>
                </div>
            '''
            
            scores = item.get('scores')
            if scores:
                timeline_item_html += '<div class="score-container">'
                for category, score in scores.items():
                    timeline_item_html += f'''
                    <div class="score-badge">
                        <p class="score-value">{score}/10</p>
                        <p class="score-label">{category}</p>
                    </div>
                    '''
                timeline_item_html += '</div>'
            
            timeline_item_html += '</div>'
            st.markdown(timeline_item_html, unsafe_allow_html=True)
            
            # エクスパンダーでフィードバックと回答内容
            with st.expander("📝 AIフィードバックと回答内容を見る"):
                st.markdown("**🤖 AIフィードバック**")
                feedback_text = item.get('feedback', 'フィードバックがありません。')
                st.markdown(f'<div style="background: #f8fafc; padding: 1rem; border-radius: 8px; border-left: 4px solid #667eea;">{feedback_text}</div>', unsafe_allow_html=True)
                
                st.markdown("**✍️ あなたの回答**")
                inputs = item.get('inputs', {})
                
                # 特別な入力フィールドがある場合の表示
                if item.get('keywords'):
                    st.text_area("生成されたキーワード", item.get('keywords', ''), key=f"keywords_{item['date']}", disabled=True, height=100)
                if item.get('category'):
                    st.text_area("カテゴリ", item.get('category', ''), key=f"category_{item['date']}", disabled=True, height=50)
                if item.get('rationale'):
                    st.text_area("根拠", item.get('rationale', ''), key=f"rationale_{item['date']}", disabled=True, height=100)
                if item.get('search_keywords'):
                    st.text_area("検索キーワード", item.get('search_keywords', ''), key=f"search_keywords_{item['date']}", disabled=True, height=50)
                if item.get('paper_title'):
                    st.text_area("論文タイトル", item.get('paper_title', ''), key=f"paper_title_{item['date']}", disabled=True, height=100)
                    st.text_area("論文要約", item.get('paper_abstract', ''), key=f"paper_abstract_{item['date']}", disabled=True, height=200)
                else:
                    # 通常の練習の場合
                    for key, value in inputs.items():
                        if isinstance(value, str) and value.strip():
                            st.text_area(f"{key}", value, key=f"input_{item['date']}_{key}", disabled=True, height=100)
    
    st.markdown('</div>', unsafe_allow_html=True)

def rescore_practice_record(error_record):
    """
    エラーのあった練習記録を再採点します
    
    Args:
        error_record: エラー記録の辞書
        
    Returns:
        bool: 再採点の成功/失敗
    """
    practice_type = error_record['practice_type']
    inputs = error_record['inputs']
    original_item = error_record['original_item']
    
    try:
        # 練習タイプに応じて採点関数を選択
        stream = None
        
        if practice_type in ['採用試験']:
            from modules.scorer import score_exam_stream
            stream = score_exam_stream(
                inputs.get('abstract', inputs.get('original_abstract', '')),
                inputs.get('translation', ''),
                inputs.get('opinion', ''),
                inputs.get('essay', ''),
                inputs.get('essay_theme', '')
            )
        elif practice_type.startswith('過去問スタイル採用試験'):
            from modules.scorer import score_exam_style_stream
            # 過去問スタイルの場合
            exam_data = inputs.get('exam_data', {})
            format_type = inputs.get('format_type', 'letter_translation_opinion')
            content = exam_data.get('formatted_content', '')
            task_instruction = exam_data.get('task1', '')
            
            stream = score_exam_style_stream(
                content,
                inputs.get('translation', ''),
                inputs.get('opinion', ''),
                format_type,
                task_instruction
            )
        elif practice_type == '小論文対策':
            from modules.essay_scorer import score_long_essay_stream
            stream = score_long_essay_stream(
                inputs.get('theme', ''),
                inputs.get('memo', ''),
                inputs.get('essay', '')
            )
        elif practice_type == '医学部採用試験 自由記述':
            from modules.medical_knowledge_checker import score_medical_answer_stream
            stream = score_medical_answer_stream(
                inputs.get('question', ''),
                inputs.get('answer', '')
            )
        elif practice_type in ['英語読解', '過去問スタイル英語読解']:
            if practice_type == '過去問スタイル英語読解':
                from modules.scorer import score_exam_style_stream
                # 過去問スタイル英語読解
                exam_data = inputs.get('exam_data', {})
                format_type = inputs.get('format_type', 'letter_translation_opinion')
                content = exam_data.get('formatted_content', '')
                task_instruction = exam_data.get('task1', '')
                
                stream = score_exam_style_stream(
                    content,
                    inputs.get('translation', ''),
                    inputs.get('opinion', ''),
                    format_type,
                    task_instruction
                )
            else:
                from modules.scorer import score_reading_stream
                # 標準英語読解
                stream = score_reading_stream(
                    inputs.get('abstract', ''),
                    inputs.get('translation', ''),
                    inputs.get('opinion', '')
                )
        elif practice_type in ['面接対策(単発)', '面接対策(セッション)']:
            if practice_type == '面接対策(単発)':
                from modules.interview_prepper import score_interview_answer_stream
                stream = score_interview_answer_stream(
                    inputs.get('question', ''),
                    inputs.get('answer', '')
                )
            else:
                # セッション形式は再採点が困難なため、スキップ
                st.warning("面接セッション形式の再採点はサポートされていません。")
                return False
        else:
            st.error(f"未対応の練習タイプです: {practice_type}")
            return False
        
        if stream is None:
            st.error("採点ストリームの生成に失敗しました。")
            return False
        
        # ストリーミング結果を取得
        with st.container():
            st.write("**再採点結果:**")
            feedback_placeholder = st.empty()
            full_feedback = ""
            
            for chunk in stream:
                if hasattr(chunk, 'text') and chunk.text:
                    full_feedback += chunk.text
                    feedback_placeholder.markdown(full_feedback + "▌")
            
            feedback_placeholder.markdown(full_feedback)
        
        # スコアを抽出
        scores = extract_scores(full_feedback)
        
        # 履歴を更新
        updated_data = original_item.copy()
        updated_data['feedback'] = full_feedback
        updated_data['scores'] = scores
        
        # データベースに保存
        success = db_adapter.save_practice_history(updated_data)
        
        return success
        
    except Exception as e:
        st.error(f"再採点処理中にエラー: {e}")
        return False

with tab4:
    # エラー確認と再採点機能
    if database_available:
        st.subheader("🔧 採点エラーの確認と再実行")
        
        # セッション状態に再採点完了フラグを追加
        if 'rescoring_completed' not in st.session_state:
            st.session_state.rescoring_completed = False
        
        try:
            # エラーのある履歴を取得（新システムでは自動的に修正される）
            if database_available:
                error_records = []  # 新システムではエラーは自動修正される
            else:
                error_records = []  # ローカルファイルの場合はエラーチェックなし
            
            if not error_records:
                st.success("✅ 採点エラーのある履歴は見つかりませんでした。")
                st.session_state.rescoring_completed = False  # リセット
            else:
                st.warning(f"⚠️ {len(error_records)}件の採点エラーが見つかりました。")
                
                # 一括再採点ボタン
                if st.button("🔄 すべてのエラーを一括再採点", type="primary", disabled=st.session_state.rescoring_completed):
                    st.session_state.rescoring_completed = True
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    success_count = 0
                    for i, error_record in enumerate(error_records):
                        status_text.text(f"再採点中... ({i+1}/{len(error_records)})")
                        progress_bar.progress((i+1) / len(error_records))
                        
                        try:
                            if rescore_practice_record(error_record):
                                success_count += 1
                        except Exception as e:
                            st.error(f"記録 {i+1} の再採点に失敗: {e}")
                    
                    st.success(f"✅ {success_count}/{len(error_records)}件の再採点が完了しました。")
                    # st.rerun() を削除して無限ループを防止
                    # 代わりにキャッシュをクリアして次回読み込み時に最新データを取得
                    st.cache_data.clear()
                
                # 再採点完了後のリセットボタン
                if st.session_state.rescoring_completed:
                    if st.button("🔄 再度エラーチェック", type="secondary"):
                        st.session_state.rescoring_completed = False
                        st.cache_data.clear()
                        st.rerun()
                
                # エラー履歴を個別表示（最大10件まで）
                for i, error_record in enumerate(error_records[:10]):
                    with st.expander(f"エラー記録 {i+1}: {error_record['practice_type']} ({error_record['date'][:10]})"):
                        st.write("**練習タイプ:**", error_record['practice_type'])
                        st.write("**日時:**", error_record['date'])
                        
                        # エラー内容を表示
                        st.write("**エラー内容:**")
                        st.code(error_record['error_feedback'])
                        
                        # 入力データの確認
                        inputs = error_record['inputs']
                        st.write("**入力データ:**")
                        for key, value in inputs.items():
                            if isinstance(value, str) and len(value) > 100:
                                st.write(f"- **{key}**: {value[:100]}...")
                            else:
                                st.write(f"- **{key}**: {value}")
                        
                        # 個別再採点ボタン
                        if st.button(f"🔄 個別再採点", key=f"rescore_{i}", type="secondary"):
                            st.info("再採点を実行中...")
                            
                            try:
                                success = rescore_practice_record(error_record)
                                
                                if success:
                                    st.success("✅ 再採点が完了しました！")
                                    st.cache_data.clear()
                                    # 個別再採点では無限ループを避けるためrerunを削除
                                else:
                                    st.error("❌ 再採点に失敗しました。")
                                    
                            except Exception as e:
                                st.error(f"再採点中にエラーが発生しました: {e}")
                
                # 10件を超える場合の表示
                if len(error_records) > 10:
                    st.info(f"表示しているのは最初の10件です。残り{len(error_records) - 10}件のエラーがあります。")
        
        except Exception as e:
            st.error(f"エラー確認機能でエラーが発生しました: {e}")
    else:
        st.warning("データベース機能が利用できません。エラー確認機能はSupabase接続が必要です。")

st.markdown("---")

# ナビゲーション
st.markdown('<div class="section-header">🚀 他のページへ移動</div>', unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("📄 採用試験", use_container_width=True):
        st.switch_page("pages/01_採用試験.py")
with col2:
    if st.button("✍️ 小論文対策", use_container_width=True):
        st.switch_page("pages/02_小論文.py")
with col3:
    if st.button("🗣️ 面接対策", use_container_width=True):
        st.switch_page("pages/03_面接.py")
with col4:
    if st.button("📖 英語読解", use_container_width=True):
        st.switch_page("pages/05_英語読解.py")
