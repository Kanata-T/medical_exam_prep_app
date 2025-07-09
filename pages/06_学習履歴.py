import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules.utils import load_history
import json

st.set_page_config(
    page_title="学習履歴",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="auto"
)

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

# データの読み込み
@st.cache_data(ttl=300)
def load_and_process_history():
    history_data = load_history()
    if not history_data:
        return None, pd.DataFrame(), pd.DataFrame()

    df_data = []
    score_data = []
    
    for item in history_data:
        date = pd.to_datetime(item['date'])
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
        
        if isinstance(item.get('scores'), dict):
            for category, score in item['scores'].items():
                score_data.append({
                    'date': date,
                    'type': item_type,
                    'category': category,
                    'score': score,
                    'duration_seconds': duration_seconds,
                    'duration_display': duration_display
                })
    
    df_base = pd.DataFrame(df_data)
    df_scores = pd.DataFrame(score_data)
    
    return history_data, df_base, df_scores

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
    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)
    st.markdown("### 🔍 フィルター設定")
    
    date_range_option = st.selectbox(
        "📅 期間",
        ["全期間", "過去7日間", "過去30日間", "過去90日間", "カスタム"],
    )
    
    today = datetime.now().date()
    min_date = df_base['date'].min().date()
    max_date = df_base['date'].max().date()

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

    available_types = df_base['type'].unique().tolist()
    selected_types = st.multiselect("📚 練習タイプ", available_types, default=available_types)
    
    if not df_scores.empty:
        score_min = int(df_scores['score'].min())
        score_max = int(df_scores['score'].max())
        score_range = st.slider(
            "📊 スコア範囲",
            min_value=score_min,
            max_value=score_max,
            value=(score_min, score_max)
        )
    
    st.markdown('</div>', unsafe_allow_html=True)

# データフィルタリング
base_mask_date = (df_base['date'].dt.date >= start_date) & (df_base['date'].dt.date <= end_date)
base_mask_type = df_base['type'].isin(selected_types)
filtered_base = df_base[base_mask_date & base_mask_type]

if not df_scores.empty:
    mask_date = (df_scores['date'].dt.date >= start_date) & (df_scores['date'].dt.date <= end_date)
    mask_type = df_scores['type'].isin(selected_types)
    mask_score = (df_scores['score'] >= score_range[0]) & (df_scores['score'] <= score_range[1]) if 'score_range' in locals() else pd.Series([True] * len(df_scores))
    filtered_scores = df_scores[mask_date & mask_type & mask_score]
else:
    filtered_scores = pd.DataFrame(columns=df_scores.columns)

# メイン画面
if filtered_base.empty:
    st.warning("選択されたフィルターに一致するデータがありません。")
    st.stop()

# サマリー統計
st.markdown('<div class="section-header">📈 学習サマリー</div>', unsafe_allow_html=True)
total_practices = len(filtered_base)
days_active = filtered_base['date'].dt.date.nunique()

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
    if not filtered_scores.empty:
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
    if not filtered_scores.empty:
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

# 詳細分析タブ
st.markdown('<div class="section-header">📊 詳細分析</div>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["📈 スコア推移", "🎯 カテゴリ別分析", "📅 学習パターン"])

with tab1:
    if not filtered_scores.empty and len(filtered_scores) > 1:
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

with tab2:
    if not filtered_scores.empty:
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

with tab3:
    # 曜日別練習回数
    filtered_base_copy = filtered_base.copy()
    filtered_base_copy['weekday'] = filtered_base_copy['date'].dt.day_name()
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
            x='date',
            y='duration_minutes',
            color='type',
            title='所要時間の推移',
            labels={'duration_minutes': '所要時間（分）', 'date': '日付'},
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

# 履歴詳細
st.markdown('<div class="section-header">📜 練習履歴詳細</div>', unsafe_allow_html=True)

# エクスポート
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

for item in reversed(history): # 新しい順に
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

    date_str = item_date.strftime('%Y/%m/%d')
    time_str = item_date.strftime('%H:%M')
    item_type = item.get('type', '不明')
    duration_display = item.get('duration_display', '未記録')
    
    # タイムラインアイテムの作成
    timeline_item_html = f'''
    <div class="timeline-item type-{item_type}">
        <div class="timeline-header">
            <h3 class="timeline-title">{item_type}
                <span class="timeline-badge badge-{item_type}">{item_type}</span>
            </h3>
            <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 0.25rem;">
                <div class="timeline-date">{date_str} {time_str}</div>
                <div style="font-size: 0.8rem; color: #6b7280; background: #f9fafb; padding: 0.125rem 0.5rem; border-radius: 12px;">
                    ⏱️ {duration_display}
                </div>
            </div>
        </div>
    '''
    
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
        for key, value in inputs.items():
            if isinstance(value, str) and value.strip():
                st.text_area(f"{key}", value, key=f"input_{item['date']}_{key}", disabled=True, height=100)

st.markdown('</div>', unsafe_allow_html=True)

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
