import streamlit as st
import time
from datetime import datetime, timedelta
from modules.paper_finder import (find_medical_paper, generate_essay_theme, get_sample_keywords,
                                get_keyword_history, clear_keyword_history, get_available_fields,
                                format_paper_as_exam, get_past_exam_patterns)
from modules.scorer import score_exam_stream, get_score_distribution, score_exam_style_stream
from modules.utils import (handle_submission, reset_session_state, 
                          check_api_configuration, show_api_setup_guide,
                          extract_scores, save_history, format_history_for_download,
                          restore_exam_session, auto_save_session)
from modules.database_adapter_v3 import DatabaseAdapterV3
from modules.session_manager import StreamlitSessionManager
import os

st.set_page_config(
    page_title="医学部採用試験シミュレーター",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# セッション管理の初期化（最重要：ページ読み込み時に必ず実行）
if 'session_initialized' not in st.session_state:
    try:
        session_manager = StreamlitSessionManager()
        current_session = session_manager.get_user_session()
        st.session_state.session_manager = session_manager
        st.session_state.current_session = current_session
        st.session_state.session_initialized = True
        
        # デバッグ情報をコンパクトに表示
        session_info = f"🔐 {current_session.identification_method.value}"
        if current_session.is_authenticated:
            session_info = f"✅ {session_info} (認証済み)"
        
    except Exception as e:
        st.session_state.session_initialized = False

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #4a5568 0%, #2d3748 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .status-box {
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        border-left: 5px solid;
    }
    .status-success { border-color: #28a745; background-color: #d4edda; }
    .status-warning { border-color: #ffc107; background-color: #fff3cd; }
    .status-error { border-color: #dc3545; background-color: #f8d7da; }
    .status-info { border-color: #17a2b8; background-color: #d1ecf1; }
    
    .fixed-timer {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        background-color: rgba(255, 255, 255, 0.9);
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1000;
        backdrop-filter: blur(5px);
        border-top: 4px solid #4a5568;
    }
    .fixed-timer-content {
        text-align: center;
    }
    .fixed-timer-content .time-label {
        font-size: 0.9em;
        color: #4a5568;
        margin-bottom: 0.25rem;
    }
    .fixed-timer-content .time-value {
        font-size: 1.5em;
        font-weight: bold;
        color: #2d3748;
    }
    
    .task-card {
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        background-color: #ffffff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .abstract-container {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 5px;
        height: 100%;
        white-space: pre-wrap;
        font-family: 'serif';
        line-height: 1.6;
    }
</style>
""", unsafe_allow_html=True)

# タイトル
st.markdown("""
<div class="main-header">
    <h1>医学部研修医採用試験シミュレーター</h1>
    <p>実際の採用試験に近い形式で、医学論文の読解・日本語訳・小論文の練習ができます</p>
</div>
""", unsafe_allow_html=True)

# セッション状態の初期化
session_vars = {
    'start_time': 0,
    'paper_data': None,
    'essay_theme': "",
    'exam_completed': False,
    'exam_results': None,
    'exam_step': 'setup',  # setup, running, scoring, completed
    'time_extended': False,
    'exam_style_enabled': False,  # 過去問スタイル出題の有効化
    'exam_format_type': 'letter_translation_opinion',  # 出題形式
    'exam_formatted_data': None,  # 過去問スタイルに変換されたデータ
}

# タイマー用のプレースホルダー
timer_placeholder = st.empty()

# セッション復元を試行
session_restored = False
if 'session_initialized' not in st.session_state:
    session_restored = restore_exam_session()
    st.session_state.session_initialized = True
    
    if session_restored:
        st.success("前回のセッションを復元しました。試験を継続できます。")

# セッション変数の初期化（復元されなかった場合のみ）
for var, default in session_vars.items():
    if var not in st.session_state:
        st.session_state[var] = default

# セッション自動保存（変更があった場合のみ）
auto_save_session()

# API設定確認
api_ok, api_message = check_api_configuration()
if not api_ok:
    st.markdown(f"""
    <div class="status-box status-error">
        <h4>API設定エラー</h4>
        <p>{api_message}</p>
    </div>
    """, unsafe_allow_html=True)
    show_api_setup_guide()
    st.stop()

# 採点完了後の結果表示
if st.session_state.exam_completed and st.session_state.exam_results:
    timer_placeholder.empty()
    st.markdown('<div class="status-box status-success">', unsafe_allow_html=True)
    st.markdown("### 採点完了！")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 結果表示
    st.markdown("### 採点結果")
    st.markdown(st.session_state.exam_results)
    
    # アクションボタン
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("再度挑戦する", type="primary", use_container_width=True):
            for var in session_vars:
                st.session_state[var] = session_vars[var]
            st.rerun()
    
    with col2:
        if st.button("学習履歴を見る", use_container_width=True):
            st.switch_page("pages/04_学習履歴.py")
    
    with col3:
        if st.button("小論文対策へ", use_container_width=True):
            st.switch_page("pages/02_小論文.py")
    
    st.stop()

# プログレスインジケーター
progress_steps = {
    'setup': '🔧 セットアップ',
    'running': '📝 試験実施中',
    'scoring': '⚖️ AI採点中',
    'completed': '✅ 完了'
}

# セットアップフェーズ
if st.session_state.exam_step == 'setup':
    timer_placeholder.empty()
    st.markdown('<div class="task-card">', unsafe_allow_html=True)
    st.markdown("### 論文検索設定")
    
    # 過去のキーワード履歴とAI生成の説明
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("🤖 AIによる自動キーワード生成について", expanded=False):
            st.markdown("""
            **AIによる自動生成の特徴:**
            - 医師国家試験の出題範囲内から選択
            - 臨床的に重要度の高い分野を優先
            - 最新の医学研究動向を反映
            - PubMedで高品質な論文が見つかりやすいキーワード
            - **過去5回とは異なる分野から自動選択**
            - **過去に生成されたキーワードとの重複を回避**
            
            **参考：従来のサンプルキーワード**
            """)
            sample_keywords = get_sample_keywords()
            cols = st.columns(2)
            for i, keyword in enumerate(sample_keywords):
                with cols[i % 2]:
                    if st.button(keyword, key=f"sample_{i}", use_container_width=True):
                        st.session_state.search_keywords = keyword
                        st.rerun()
    
    with col2:
        with st.expander("📊 過去のキーワード履歴", expanded=False):
            keyword_history = get_keyword_history()
            if keyword_history:
                st.markdown(f"**総履歴数**: {len(keyword_history)}件")
                st.markdown("**最近生成されたキーワード（最新5件）:**")
                st.caption("⚠️ 次回の自動生成時、これらのキーワードと類似したものは避けられます")
                
                recent_history = keyword_history[-5:]
                for i, item in enumerate(reversed(recent_history), 1):
                    category = item.get('category', '不明')
                    keywords = item.get('keywords', '不明')
                    rationale = item.get('rationale', '')
                    st.markdown(f"{i}. **{category}**: `{keywords}`")
                    if rationale and i <= 3:  # 最新3件のみ理由も表示
                        st.caption(f"   理由: {rationale}")
                
                # 過去のキーワードのリストを表示
                past_keywords = [item.get('keywords', '') for item in recent_history if item.get('keywords')]
                if past_keywords:
                    st.markdown("**回避対象キーワード:**")
                    st.code(', '.join([f'"{kw}"' for kw in past_keywords]), language=None)
                
                st.markdown("---")
                available_fields = get_available_fields()
                if available_fields:
                    st.markdown("**次回利用可能な分野:**")
                    st.markdown(", ".join(available_fields))
                else:
                    st.markdown("**全分野が利用可能**（履歴がリセットされました）")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("履歴をクリア", key="clear_history"):
                        clear_keyword_history()
                        st.success("履歴をクリアしました")
                        st.rerun()
                with col2:
                    if st.button("全履歴を表示", key="show_all_history"):
                        st.json(keyword_history)
            else:
                st.info("まだキーワード生成履歴がありません。")
    
    # キーワード入力
    keywords = st.text_input(
        "検索したい論文のキーワードを入力してください（空白の場合はAIが自動選択）",
        value=st.session_state.get('search_keywords', ''),
        placeholder="例: diabetes mellitus, hypertension, COVID-19",
        help="医学論文のPubMed検索に使用するキーワードを英語で入力してください。空白の場合、AIが医師国家試験範囲内から臨床的に重要なキーワードを自動選択します。"
    )
    
    # 過去問スタイル出題設定
    st.markdown("---")
    st.markdown("### 🎯 英語読解出題形式設定")
    
    # 過去問スタイル有効化チェックボックス
    exam_style_enabled = st.checkbox(
        "英語読解を過去問スタイルで出題する",
        value=st.session_state.get('exam_style_enabled', False),
        help="論文を県総採用試験の過去問と同様の形式に変換して出題します（小論文は通常通り）"
    )
    st.session_state.exam_style_enabled = exam_style_enabled
    
    if exam_style_enabled:
        col1, col2 = st.columns(2)
        
        with col1:
            # 出題形式選択
            format_options = {
                "letter_translation_opinion": "Letter形式（翻訳 + 意見）",
                "paper_comment_translation_opinion": "論文コメント形式（コメント翻訳 + 意見）"
            }
            
            selected_format = st.selectbox(
                "英語読解の出題形式を選択",
                options=list(format_options.keys()),
                format_func=lambda x: format_options[x],
                index=0 if st.session_state.get('exam_format_type', 'letter_translation_opinion') == 'letter_translation_opinion' else 1,
                help="英語読解部分の過去問形式を選択してください"
            )
            st.session_state.exam_format_type = selected_format
        
        with col2:
            # 過去問例の表示
            with st.expander("📝 過去問例を見る", expanded=False):
                past_patterns = get_past_exam_patterns()
                for i, pattern in enumerate(past_patterns[:2], 1):  # 最初の2つを表示
                    st.markdown(f"**過去問例{i}**: {pattern['topic']}")
                    if pattern['type'] == 'letter_translation_opinion':
                        st.caption(f"形式: {pattern['task1']} / {pattern['task2']}")
                        st.code(pattern['content'][:200] + "...", language=None)
                    else:
                        st.caption(f"形式: {pattern['task1']}")
                        if isinstance(pattern['content'], dict):
                            st.text(pattern['content']['paper_summary'][:100] + "...")
                            st.code(pattern['content']['comment'][:200] + "...", language=None)
                    st.markdown("---")
        
        # 過去問スタイル説明
        st.info(f"""
        **選択中の形式**: {format_options[selected_format]}
        
        📋 **この形式での英語読解**:
        {"- 論文のAbstractを翻訳する課題" if selected_format == 'letter_translation_opinion' else "- 論文に対するコメントを翻訳する課題"}
        {"- 論文の内容について意見を述べる課題" if selected_format == 'letter_translation_opinion' else "- コメントについて意見を述べる課題"}
        
        📝 **小論文**: 通常の形式で出題されます
        
        ⚠️ **注意**: 過去問スタイルを有効にすると、AIが論文を県総採用試験の形式に変換します（変換時間: 追加で約30秒）
        """)
    else:
        st.info("""
        **標準形式**: 論文のAbstractを直接翻訳・考察する形式 + 小論文で出題されます
        """)
    
    st.markdown("---")
    
    # 試験開始ボタン
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("試験開始（60分）", type="primary", use_container_width=True):
            loading_message = "論文とテーマを準備中..."
            estimated_time = 30
            
            if not keywords.strip():
                estimated_time += 45  # AI自動選択時間
                loading_message += "（AIがキーワードを自動選択中"
            else:
                loading_message += "（論文検索中"
            
            if exam_style_enabled:
                estimated_time += 30  # 過去問変換時間
                loading_message += " + 過去問スタイル変換"
            
            loading_message += f"...約{estimated_time}秒）"
                
            with st.spinner(loading_message):
                # 論文検索
                paper_result = find_medical_paper(keywords, "medical_exam")
                if 'error' in paper_result:
                    st.error(f"論文検索エラー: {paper_result['error']}")
                    st.stop()
                
                # 過去問スタイル変換（有効な場合）
                if exam_style_enabled:
                    st.info("論文を過去問スタイルに変換中...")
                    exam_result = format_paper_as_exam(paper_result, st.session_state.exam_format_type)
                    if 'error' in exam_result:
                        st.error(f"過去問変換エラー: {exam_result['error']}")
                        st.warning("標準形式で継続します。")
                        st.session_state.exam_formatted_data = None
                    else:
                        st.session_state.exam_formatted_data = exam_result
                        st.success("過去問スタイルへの変換が完了しました！")
                else:
                    st.session_state.exam_formatted_data = None
                
                # テーマ生成
                theme_result = generate_essay_theme()
                if 'error' in theme_result:
                    st.error(f"テーマ生成エラー: {theme_result['error']}")
                    st.stop()
                
                # セッション状態更新
                st.session_state.paper_data = paper_result
                st.session_state.essay_theme = theme_result['theme']
                st.session_state.start_time = time.time()
                st.session_state.exam_step = 'running'
                st.session_state.search_keywords = paper_result.get('keywords_used', keywords)
                
            success_msg = "準備完了！試験を開始します。"
            if not keywords.strip():
                selected_keywords = paper_result.get('keywords_used', '')
                selected_category = paper_result.get('category', '')
                if selected_category:
                    success_msg += f"\n**選択された分野**: {selected_category}"
                success_msg += f"\n**キーワード**: `{selected_keywords}`"
            
            format_options = {
                "letter_translation_opinion": "Letter形式（翻訳 + 意見）",
                "paper_comment_translation_opinion": "論文コメント形式（コメント翻訳 + 意見）"
            }
            
            if exam_style_enabled and st.session_state.exam_formatted_data:
                success_msg += f"\n**英語読解形式**: 過去問スタイル（{format_options[st.session_state.exam_format_type]}）"
            else:
                success_msg += f"\n**英語読解形式**: 標準形式"
            success_msg += f"\n**小論文**: 通常形式"
            
            st.success(success_msg)
            time.sleep(1)
            st.rerun()
    
    with col2:
        st.markdown("#### 試験概要")
        st.markdown("""
        - **制限時間**: 60分
        - **課題数**: 3課題
        - **自動採点**: AI採点
        """)
    
    st.markdown('</div>', unsafe_allow_html=True)

# 試験実施フェーズ
elif st.session_state.exam_step == 'running':
    # 時間管理
    elapsed_time = time.time() - st.session_state.start_time
    remaining_time = 3600 - elapsed_time  # 60分 = 3600秒
    
    if remaining_time > 0:
        # タイマー表示
        minutes = int(remaining_time // 60)
        seconds = int(remaining_time % 60)
        
        if remaining_time < 300:  # 残り5分以下
            timer_color = "#dc3545"  # 赤
        elif remaining_time < 900:  # 残り15分以下
            timer_color = "#ffc107"  # 黄
        else:
            timer_color = "#28a745"  # 緑
        
        timer_placeholder.markdown(f"""
        <div class="fixed-timer">
            <div class="fixed-timer-content">
                <div class="time-label">残り時間</div>
                <div class="time-value" style="color: {timer_color};">{minutes:02d}:{seconds:02d}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 時間延長オプション（残り5分以下）
        if remaining_time < 300 and not st.session_state.time_extended:
            if st.button("時間延長（+15分）", type="secondary"):
                st.session_state.start_time -= 900  # 15分延長
                st.session_state.time_extended = True
                st.success("15分延長されました！")
                st.rerun()
        
        # 過去問スタイル vs 標準形式の判定
        is_exam_style = st.session_state.get('exam_style_enabled', False) and st.session_state.get('exam_formatted_data')
        exam_data = st.session_state.get('exam_formatted_data', {})
        format_type = st.session_state.get('exam_format_type', 'letter_translation_opinion')
        
        # 出題形式の表示
        if is_exam_style:
            format_names = {
                "letter_translation_opinion": "Letter形式（翻訳 + 意見）",
                "paper_comment_translation_opinion": "論文コメント形式（コメント翻訳 + 意見）"
            }
            st.info(f"🎯 **英語読解：過去問スタイル出題**: {format_names.get(format_type, '不明')}")
        
        # 課題1: 英語読解
        st.markdown('<div class="task-card">', unsafe_allow_html=True)
        
        if is_exam_style:
            # 過去問スタイルの表示
            if format_type == "letter_translation_opinion":
                st.markdown("### 課題1: Letter翻訳")
                task1_instruction = exam_data.get('task1', '以下のletterを日本語訳しなさい (A4を1枚)')
            else:  # paper_comment_translation_opinion
                st.markdown("### 課題1: コメント翻訳・意見")
                task1_instruction = exam_data.get('task1', '（１）和訳して、（２）そのコメントについて、皆さんの意見を書きなさい。')
            
            st.markdown(f"**課題**: {task1_instruction}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 📄 出題内容")
                
                if format_type == "letter_translation_opinion":
                    # Letter形式: Abstractをそのまま表示
                    content_text = exam_data.get('formatted_content', '')
                    st.markdown(f'<div class="abstract-container">{content_text}</div>', unsafe_allow_html=True)
                else:
                    # コメント形式: 論文概要 + コメント
                    content = exam_data.get('formatted_content', {})
                    if isinstance(content, dict):
                        paper_summary = content.get('paper_summary', '')
                        comment_text = content.get('comment', '')
                        
                        st.markdown("##### 📋 論文概要")
                        st.markdown(paper_summary)
                        st.markdown("##### 💬 コメント")
                        st.markdown(f'<div class="abstract-container">{comment_text}</div>', unsafe_allow_html=True)
                    else:
                        st.error("コメント形式のデータが正しく取得できませんでした。")
                
                # 論文の基本情報（参考として表示）
                with st.expander("📚 元論文情報（参考）", expanded=False):
                    paper_title = st.session_state.paper_data.get('title', '(タイトル不明)')
                    st.markdown(f"**タイトル**: {paper_title}")
                    study_type = st.session_state.paper_data.get('study_type', '不明')
                    st.markdown(f"**研究種別**: {study_type}")
                    keywords_used = st.session_state.paper_data.get('keywords_used', '')
                    if keywords_used:
                        st.markdown(f"**検索キーワード**: `{keywords_used}`")
            
            with col2:
                if format_type == "letter_translation_opinion":
                    # Letter形式: 翻訳のみ
                    st.markdown("#### 日本語訳")
                    translation = st.text_area(
                        "上記のletterを正確で自然な日本語に翻訳してください。",
                        height=800,
                        key="translation",
                        label_visibility="collapsed",
                        help="専門用語を正確に訳し、自然で読みやすい日本語にしてください"
                    )
                    st.caption(f"入力文字数: {len(translation)}文字")
                else:
                    # コメント形式: 翻訳 + 意見を同じエリアで
                    st.markdown("#### 回答（翻訳 + 意見）")
                    translation = st.text_area(
                        "（１）コメントを和訳し、（２）そのコメントについてあなたの意見を述べてください。",
                        height=800,
                        key="translation",
                        label_visibility="collapsed",
                        help="コメントの翻訳と意見を分けて記述してください"
                    )
                    st.caption(f"入力文字数: {len(translation)}文字")
        
        else:
            # 標準形式の表示
            st.markdown("### 課題1: Abstract読解・翻訳・考察")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 📄 論文情報")
                if st.session_state.paper_data and 'abstract' in st.session_state.paper_data:
                    # 論文タイトル
                    paper_title = st.session_state.paper_data.get('title', '(タイトル不明)')
                    st.markdown("##### 📋 タイトル")
                    st.markdown(f"**{paper_title}**")
                    
                    # 研究種別とキーワード情報
                    col_info1, col_info2 = st.columns(2)
                    with col_info1:
                        study_type = st.session_state.paper_data.get('study_type', '不明')
                        st.markdown(f"**研究種別:** {study_type}")
                    with col_info2:
                        relevance = st.session_state.paper_data.get('relevance_score', 'N/A')
                        st.markdown(f"**関連度:** {relevance}/10")
                    
                    keywords_used = st.session_state.paper_data.get('keywords_used', '')
                    if keywords_used:
                        st.markdown(f"**検索キーワード:** `{keywords_used}`")
                    
                    st.markdown("---")
                    
                    # Abstract
                    st.markdown("##### 📖 Abstract")
                    abstract_text = st.session_state.paper_data['abstract']
                    st.markdown(f'<div class="abstract-container">{abstract_text}</div>', unsafe_allow_html=True)
                    
                    # 引用情報（取得元リンク）
                    citations = st.session_state.paper_data.get('citations', [])
                    if citations:
                        st.markdown("##### 📚 取得元")
                        for i, citation in enumerate(citations, 1):
                            title = citation.get('title', 'No Title')
                            uri = citation.get('uri', '#')
                            if 'pubmed' in uri.lower():
                                st.markdown(f"{i}. [{title}]({uri}) 🔗")
                        st.caption("※ PubMedの論文ページで詳細を確認できます")
                    else:
                        st.info("取得元情報が取得できませんでした。")

            with col2:
                st.markdown("#### 日本語訳")
                translation = st.text_area(
                    "上記のAbstractを正確で自然な日本語に翻訳してください。",
                    height=800,
                    key="translation",
                    label_visibility="collapsed",
                    help="専門用語を正確に訳し、自然で読みやすい日本語にしてください"
                )
                st.caption(f"入力文字数: {len(translation)}文字")
        
        st.markdown("</div>", unsafe_allow_html=True) # task-card end

        # 意見・考察（Letter形式または標準形式の場合のみ）
        if not is_exam_style or format_type == "letter_translation_opinion":
            st.markdown('<div class="task-card">', unsafe_allow_html=True)
            if is_exam_style:
                st.markdown("### 課題1続き: Letterについての意見")
                task2_instruction = exam_data.get('task2', 'このletterを読んで、あなたの意見を述べなさい (A4を1枚)')
                st.markdown(f"**課題**: {task2_instruction}")
                opinion_prompt = "このletterの内容について、あなたの意見や考察を述べてください。"
            else:
                st.markdown("#### Abstractを読んでの意見・考察")
                opinion_prompt = "このAbstractの内容について、あなたの意見や考察を述べてください。"
            
            opinion = st.text_area(
                opinion_prompt,
                height=600,
                key="opinion",
                label_visibility="collapsed",
                help="論文の内容を理解した上で、独自の視点や洞察を含めた意見を記述してください"
            )
            st.caption(f"入力文字数: {len(opinion)}文字")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            # コメント形式の場合は意見も課題1に含まれるため、課題1で完結
            opinion = ""  # 空の意見として扱う

        # 課題2: 小論文
        st.markdown('<div class="task-card">', unsafe_allow_html=True)
        st.markdown("### 課題2: 小論文")
        
        if st.session_state.essay_theme:
            st.markdown(f"**テーマ:** {st.session_state.essay_theme}")
            
            essay = st.text_area(
                "上記のテーマについて、あなたの意見を600字程度で論述してください。",
                height=400,
                key="essay",
                label_visibility="collapsed",
                help="構成を意識し、具体例や根拠を含めて論理的に記述してください"
            )
            
            col1, col2 = st.columns([4, 1])
            with col1:
                st.caption(f"入力文字数: {len(essay)}文字")
                target_ratio = len(essay) / 600
                st.progress(min(target_ratio, 1.0))
            with col2:
                if essay and 500 <= len(essay) <= 700:
                    st.success("適切な分量")
                elif essay and 300 <= len(essay) < 500:
                    st.warning("やや短い")
                elif essay and len(essay) > 700:
                    st.warning("やや長い")
                else:
                    st.error("不足")

        st.markdown('</div>', unsafe_allow_html=True)
        
        # 提出ボタン
        col1, col2 = st.columns([3, 1])
        with col1:
            # 入力チェック（過去問形式に対応）
            if is_exam_style and format_type == "paper_comment_translation_opinion":
                # コメント形式: 翻訳+意見+小論文
                can_submit = (
                    translation and len(translation.strip()) >= 100 and
                    essay and len(essay.strip()) >= 100
                )
                submit_help = "コメント翻訳+意見（100文字以上）と小論文（100文字以上）を入力してください。"
            else:
                # Letter形式または標準形式: 翻訳+意見+小論文
                can_submit = (
                    translation and len(translation.strip()) >= 30 and
                    opinion and len(opinion.strip()) >= 50 and
                    essay and len(essay.strip()) >= 100
                )
                submit_help = "翻訳（30文字以上）、意見（50文字以上）、小論文（100文字以上）を入力してください。"
            
            if st.button("提出して採点する", type="primary", use_container_width=True, disabled=not can_submit):
                if not can_submit:
                    st.error(f"入力が不足しています。{submit_help}")
                else:
                    # 採点フェーズへ移行
                    st.session_state.exam_step = 'scoring'
                    
                    # 提出データの準備（過去問スタイルに対応）
                    if is_exam_style:
                        submitted_data = {
                            'translation': translation,
                            'opinion': opinion if format_type == "letter_translation_opinion" else "",
                            'essay': essay,
                            'keywords': st.session_state.get('search_keywords', ''),
                            'exam_style': True,
                            'format_type': format_type,
                            'exam_data': exam_data,
                            'original_abstract': st.session_state.paper_data['abstract'],
                            'citations': st.session_state.paper_data.get('citations', [])
                        }
                        
                        # コメント形式の場合、translationに翻訳と意見の両方が含まれる
                        if format_type == "paper_comment_translation_opinion":
                            submitted_data['comment_response'] = translation  # 翻訳と意見の統合回答
                    else:
                        submitted_data = {
                            'translation': translation,
                            'opinion': opinion,
                            'essay': essay,
                            'keywords': st.session_state.get('search_keywords', ''),
                            'exam_style': False,
                            'abstract': st.session_state.paper_data['abstract'],
                            'citations': st.session_state.paper_data.get('citations', [])
                        }
                    
                    st.session_state.submitted_data = submitted_data
                    st.rerun()
        
        with col2:
            if not can_submit:
                st.warning("入力不足")
                if is_exam_style and format_type == "paper_comment_translation_opinion":
                    st.caption("翻訳+意見100文字+ & 小論文100文字+")
                else:
                    st.caption("翻訳30文字+ & 意見50文字+ & 小論文100文字+")
            else:
                st.success("提出準備完了")
    
    else:
        # 時間切れ
        timer_placeholder.empty()
        st.markdown("""
        <div class="status-box status-error">
            <h4>時間切れ</h4>
            <p>試験時間が終了しました。新しい試験を開始してください。</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("新しい試験を開始", type="primary"):
            for var in session_vars:
                st.session_state[var] = session_vars[var]
            st.rerun()

# 採点フェーズ
elif st.session_state.exam_step == 'scoring':
    timer_placeholder.empty()
    st.markdown("""
    <div class="status-box status-info">
        <h4>AI採点中</h4>
        <p>提出された回答をAIが採点しています。しばらくお待ちください...</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 採点実行（過去問スタイルに対応）
    submitted = st.session_state.submitted_data
    
    if submitted.get('exam_style', False):
        # 過去問スタイルの場合は、英語読解と小論文を分けて採点
        exam_data = submitted.get('exam_data', {})
        format_type = submitted.get('format_type', 'letter_translation_opinion')
        
        st.markdown("#### 英語読解部分の採点（過去問スタイル）")
        if format_type == "letter_translation_opinion":
            content = exam_data.get('formatted_content', '')
            task_instruction = f"{exam_data.get('task1', '')} / {exam_data.get('task2', '')}"
            reading_stream = score_exam_style_stream(
                content,
                submitted['translation'],
                submitted['opinion'],
                format_type,
                task_instruction
            )
        else:  # paper_comment_translation_opinion
            content = exam_data.get('formatted_content', {})
            task_instruction = exam_data.get('task1', '')
            reading_stream = score_exam_style_stream(
                content,
                submitted.get('comment_response', submitted['translation']),
                "",  # 意見はcomment_responseに含まれている
                format_type,
                task_instruction
            )
        
        # 英語読解部分の採点結果を表示
        reading_feedback_placeholder = st.empty()
        reading_feedback = ""
        
        reading_progress = st.progress(0)
        reading_status = st.empty()
        
        try:
            chunk_count = 0
            for chunk in reading_stream:
                chunk_count += 1
                if hasattr(chunk, 'text') and chunk.text:
                    reading_feedback += chunk.text
                    reading_feedback_placeholder.markdown(reading_feedback + "▌")
                    
                    progress = min(chunk_count / 30, 1.0)
                    reading_progress.progress(progress)
                    reading_status.text(f"英語読解採点中... ({chunk_count} chunks)")
            
            reading_feedback_placeholder.markdown(reading_feedback)
            reading_progress.progress(1.0)
            reading_status.text("英語読解採点完了")
            
        except Exception as e:
            st.error(f"英語読解採点中にエラー: {e}")
            reading_feedback = f"英語読解採点エラー: {e}"
        
        # 小論文部分の採点（簡易版）
        st.markdown("#### 小論文部分の採点（通常形式）")
        
        essay_feedback_placeholder = st.empty()
        essay_feedback = ""
        
        essay_progress = st.progress(0)
        essay_status = st.empty()
        
        try:
            # 小論文の簡易評価を生成
            import google.genai as genai
            client = genai.Client()
            
            essay_prompt = f"""小論文の採点者として、以下の小論文を採点してください。

テーマ: {st.session_state.essay_theme}

小論文:
{submitted['essay']}

以下の観点で10点満点で評価してください：
1. 構成力 (4点): 序論・本論・結論の明確性
2. 内容の充実度 (4点): 具体例や根拠の提示
3. 文章技術 (2点): 表現力と文法の正確性

スコア:
```json
{{"小論文": [1-10の整数]}}
```

## 小論文の評価

**良い点:**
- [具体的な良い点を記述]

**改善点:**
- [具体的な改善点を記述]

**学習アドバイス**
[今後の学習に向けた具体的なアドバイス]"""

            response = client.models.generate_content(
                model='gemini-2.5-pro',
                contents=essay_prompt
            )
            
            if response and response.text:
                essay_feedback = response.text
            else:
                essay_feedback = "小論文の採点結果を取得できませんでした。"
            
            # プログレスバーを段階的に更新
            for i in range(1, 26):
                essay_progress.progress(i / 25)
                essay_status.text(f"小論文採点中... ({i}/25)")
                time.sleep(0.1)
            
            essay_feedback_placeholder.markdown(essay_feedback)
            essay_progress.progress(1.0)
            essay_status.text("小論文採点完了")
            
            # 統合フィードバック
            full_feedback = f"""# 採用試験総合採点結果

## 英語読解（過去問スタイル）
{reading_feedback}

---

## 小論文
{essay_feedback}

---

## 総評
過去問スタイルでの英語読解と小論文の採点が完了しました。
各分野の詳細なフィードバックを参考に、今後の学習に活かしてください。
"""
            
        except Exception as e:
            st.error(f"小論文採点中にエラー: {e}")
            full_feedback = f"""# 採用試験採点結果

## 英語読解（過去問スタイル）
{reading_feedback}

---

## 小論文採点エラー
{e}
"""
        
        # フィードバックを統合してストリーミング風に表示
        class FeedbackStream:
            def __init__(self, feedback):
                self.feedback = feedback
                self.chunks = [feedback[i:i+50] for i in range(0, len(feedback), 50)]
                self.index = 0
            
            def __iter__(self):
                return self
            
            def __next__(self):
                if self.index >= len(self.chunks):
                    raise StopIteration
                chunk = type('Chunk', (), {'text': self.chunks[self.index]})()
                self.index += 1
                return chunk
        
        stream = FeedbackStream(full_feedback)
        
    else:
        # 標準形式の採点
        abstract = submitted.get('abstract', submitted.get('original_abstract', ''))
        stream = score_exam_stream(
            abstract,
            submitted['translation'],
            submitted['opinion'],
            submitted['essay'],
            st.session_state.essay_theme
        )
    
    # 採点結果表示
    st.markdown("### 採点結果")
    feedback_placeholder = st.empty()
    full_feedback = ""
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        chunk_count = 0
        for chunk in stream:
            chunk_count += 1
            if hasattr(chunk, 'text') and chunk.text:
                full_feedback += chunk.text
                feedback_placeholder.markdown(full_feedback + "▌")
                
                # プログレスバー更新（概算）
                progress = min(chunk_count / 50, 1.0)
                progress_bar.progress(progress)
                status_text.text(f"採点中... ({chunk_count} chunks processed)")
            else:
                status_text.text("応答形式が予期しない形式です。")
        
        # 採点完了
        feedback_placeholder.markdown(full_feedback)
        progress_bar.progress(1.0)
        status_text.text("採点完了")
        
        # 履歴保存（過去問スタイル対応）
        scores = extract_scores(full_feedback)
        
        # 所要時間の計算
        completion_time = time.time()
        duration_seconds = completion_time - st.session_state.start_time
        duration_minutes = int(duration_seconds // 60)
        duration_seconds_remainder = int(duration_seconds % 60)
        
        if submitted.get('exam_style', False):
            exam_type = "medical_exam_comprehensive"
            format_names = {
                "letter_translation_opinion": "medical_exam_letter_style",
                "paper_comment_translation_opinion": "medical_exam_comment_style"
            }
            format_type = submitted.get('format_type', 'letter_translation_opinion')
            if format_type in format_names:
                exam_type = format_names[format_type]
        else:
            exam_type = "medical_exam_comprehensive"
        
        history_data = {
            "type": exam_type,
            "date": datetime.now().isoformat(),
            "duration_seconds": duration_seconds,
            "duration_display": f"{duration_minutes}分{duration_seconds_remainder}秒",
            "inputs": {
                **submitted,
                "essay_theme": st.session_state.essay_theme
            },
            "feedback": full_feedback,
            "scores": scores
        }
        
        filename = save_history(history_data)
        if filename:
            st.success("結果を学習履歴に保存しました。")
            download_content = format_history_for_download(history_data)
            st.download_button(
                label="結果をテキストファイルでダウンロード",
                data=download_content,
                file_name=f"result_{os.path.splitext(os.path.basename(filename))[0]}.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        # セッション状態更新
        st.session_state.exam_completed = True
        st.session_state.exam_results = full_feedback
        st.session_state.exam_step = 'completed'
        
        # 完了ページへリダイレクト
        time.sleep(2)
        st.rerun()
        
    except Exception as e:
        st.error(f"採点処理中にエラーが発生しました: {e}")
        if full_feedback:
            st.info("部分的なフィードバック:")
            st.markdown(full_feedback)
        
        # エラー時の再挑戦ボタン
        if st.button("最初からやり直す", type="primary"):
            for var in session_vars:
                st.session_state[var] = session_vars[var]
            st.rerun()

# サイドバー情報
with st.sidebar:
    st.markdown("### 試験情報")
    
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
    
    if st.session_state.exam_step != 'setup':
        st.markdown(f"**現在のステップ:** {progress_steps.get(st.session_state.exam_step, 'N/A')}")
        
        if st.session_state.start_time > 0:
            elapsed = time.time() - st.session_state.start_time
            st.markdown(f"**経過時間:** {int(elapsed // 60)}分{int(elapsed % 60)}秒")
    
    st.markdown("### ヒント")
    st.markdown("""
    - **日本語訳**: 正確性と自然さのバランスを重視
    - **意見**: 論理的で独創的な視点を含める
    - **小論文**: 構成を意識し、具体例で補強
    - **時間配分**: 翻訳15分、意見20分、小論文25分を目安に
    """)
    
    if st.button("最初からやり直す", use_container_width=True):
        for var in session_vars:
            st.session_state[var] = session_vars[var]
        st.rerun()
