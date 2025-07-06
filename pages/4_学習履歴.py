import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules.utils import load_history
import json

st.set_page_config(
    page_title="学習履歴",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto"
)

# カスタムCSS (他ページと統一)
st.markdown("""
<style>
    .main-header {
        font-weight: bold;
        color: #333;
        padding-bottom: 1rem;
        border-bottom: 2px solid #eee;
        margin-bottom: 2rem;
    }
    .stMetric {
        border-left: 4px solid #17a2b8;
        padding: 1rem;
        border-radius: 8px;
        background-color: #f0f8ff;
    }
</style>
""", unsafe_allow_html=True)

# タイトル
st.markdown('<h1 class="main-header">学習履歴</h1>', unsafe_allow_html=True)

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
        
        df_data.append({
            'date': date,
            'type': item_type,
            'has_scores': bool(item.get('scores'))
        })
        
        if isinstance(item.get('scores'), dict):
            for category, score in item['scores'].items():
                score_data.append({
                    'date': date,
                    'type': item_type,
                    'category': category,
                    'score': score
                })
    
    df_base = pd.DataFrame(df_data)
    df_scores = pd.DataFrame(score_data)
    
    return history_data, df_base, df_scores

history, df_base, df_scores = load_and_process_history()

if history is None:
    st.info("まだ学習履歴がありません。各対策ページで練習すると、結果がここに記録されます。")
    
    st.markdown("---")
    st.markdown("#### 練習ページへ移動")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("採用試験", use_container_width=True, type="primary"):
            st.switch_page("pages/1_📝_採用試験.py")
    with col2:
        if st.button("小論文対策", use_container_width=True):
            st.switch_page("pages/02_shoronbun.py")
    with col3:
        if st.button("面接対策", use_container_width=True):
            st.switch_page("pages/03_mensetsu.py")
    st.stop()

# サイドバー: フィルタリング
with st.sidebar:
    st.header("フィルター設定")
    
    date_range_option = st.selectbox(
        "期間",
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
    selected_types = st.multiselect("練習タイプ", available_types, default=available_types)
    
    if not df_scores.empty:
        score_min = int(df_scores['score'].min())
        score_max = int(df_scores['score'].max())
        score_range = st.slider(
            "スコア範囲",
            min_value=score_min,
            max_value=score_max,
            value=(score_min, score_max)
        )

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
st.markdown("### サマリー")
col1, col2, col3, col4 = st.columns(4)
total_practices = len(filtered_base)
days_active = filtered_base['date'].dt.date.nunique()

col1.metric("総練習回数", f"{total_practices} 回")
col4.metric("学習日数", f"{days_active} 日")

if not filtered_scores.empty:
    avg_score = filtered_scores['score'].mean()
    best_score = filtered_scores['score'].max()
    col2.metric("平均スコア", f"{avg_score:.1f} / 10")
    col3.metric("最高スコア", f"{best_score} / 10")
else:
    col2.metric("平均スコア", "N/A")
    col3.metric("最高スコア", "N/A")

# 詳細分析タブ
st.markdown("### 詳細分析")
tab1, tab2, tab3 = st.tabs(["スコア推移", "カテゴリ別分析", "学習パターン"])

with tab1:
    if not filtered_scores.empty and len(filtered_scores) > 1:
        fig = px.line(
            filtered_scores, 
            x='date', 
            y='score', 
            color='category',
            title='スコア推移',
            hover_data=['type']
        )
        fig.update_layout(xaxis_title='日付', yaxis_title='スコア', yaxis=dict(range=[0, 10.5]))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("スコア付きのデータが2件以上ある場合にスコア推移が表示されます。")

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
                name='平均スコア'
            ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
                title="カテゴリ別平均スコア"
            )
            st.plotly_chart(fig_radar, use_container_width=True)
        
        st.markdown("**カテゴリ別統計**")
        st.dataframe(category_stats, use_container_width=True)
    else:
        st.info("スコア付きのデータがないため、カテゴリ別分析は表示できません。")

with tab3:
    filtered_base_copy = filtered_base.copy()
    filtered_base_copy['weekday'] = filtered_base_copy['date'].dt.day_name()
    weekday_counts = filtered_base_copy['weekday'].value_counts()
    
    fig_weekday = px.bar(
        weekday_counts,
        title="曜日別練習回数",
        labels={'index': '曜日', 'value': '練習回数'}
    )
    st.plotly_chart(fig_weekday, use_container_width=True)

# 履歴詳細
st.markdown("### 練習履歴詳細")

# エクスポート
csv_data = filtered_scores.to_csv(index=False).encode('utf-8')
st.download_button(
    label="表示中のデータをCSVでダウンロード",
    data=csv_data,
    file_name=f"学習履歴_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
    use_container_width=True
)

# 履歴表示
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

    date_str = item_date.strftime('%Y/%m/%d %H:%M')
    item_type = item.get('type', '不明')
    
    with st.container(border=True):
        st.markdown(f"**{date_str} - {item_type}**")
        
        if scores:
            cols = st.columns(len(scores))
            for i, (category, score) in enumerate(scores.items()):
                cols[i].metric(label=category, value=f"{score}/10")
        
        with st.expander("AIフィードバックと回答内容を見る"):
            st.markdown("**AIフィードバック**")
            st.info(item.get('feedback', 'フィードバックがありません。'))
            
            st.markdown("**あなたの回答**")
            inputs = item.get('inputs', {})
            for key, value in inputs.items():
                if isinstance(value, str) and value.strip():
                    st.text_area(f"{key}", value, key=f"input_{item['date']}_{key}", disabled=True)
st.markdown("---")
# 他のページへのナビゲーション
st.markdown("#### 他のページへ移動")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("採用試験", use_container_width=True):
        st.switch_page("pages/1_📝_採用試験.py")
with col2:
    if st.button("小論文対策", use_container_width=True):
        st.switch_page("pages/02_shoronbun.py")
with col3:
    if st.button("面接対策", use_container_width=True):
        st.switch_page("pages/03_mensetsu.py")
