import streamlit as st
import time
from datetime import datetime, timedelta
from modules.paper_finder import (find_medical_paper, get_sample_keywords,
                                get_keyword_history, clear_keyword_history, get_available_fields,
                                format_paper_as_exam, get_past_exam_patterns)
from modules.scorer import score_reading_stream, get_reading_score_distribution, score_exam_style_stream
from modules.utils import (handle_submission, reset_session_state, 
                          check_api_configuration, show_api_setup_guide,
                          extract_scores, save_history, format_history_for_download,
                          restore_exam_session, auto_save_session)
from modules.database_adapter_v3 import DatabaseAdapterV3
from modules.session_manager import StreamlitSessionManager
import os

st.set_page_config(
    page_title="医学英語読解練習",
    page_icon="📖",
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
        background: linear-gradient(90deg, #2e7d32 0%, #388e3c 100%);
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

    .progress-indicator {
        display: flex;
        justify-content: space-between;
        margin: 1rem 0;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 10px;
    }
    
    .progress-step {
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 0.5rem;
        border-radius: 5px;
        min-width: 120px;
    }
    
    .progress-step.active {
        background-color: #e3f2fd;
        border: 2px solid #2196f3;
    }
    
    .progress-step.completed {
        background-color: #e8f5e8;
        border: 2px solid #4caf50;
    }
</style>
""", unsafe_allow_html=True)

# タイトル
st.markdown("""
<div class="main-header">
    <h1>医学英語読解練習</h1>
    <p>医学論文のAbstractを正確に翻訳し、内容について深く考察する練習ができます</p>
</div>
""", unsafe_allow_html=True)

# セッション状態の初期化
session_vars = {
    'paper_data': None,
    'reading_completed': False,
    'reading_results': None,
    'reading_step': 'setup',  # setup, reading, scoring, completed
    'exam_style_enabled': False,  # 過去問スタイル出題の有効化
    'exam_format_type': 'letter_translation_opinion',  # 出題形式
    'exam_formatted_data': None,  # 過去問スタイルに変換されたデータ
    'reading_start_time': 0,  # 読解練習開始時間
}

# セッション復元を試行
session_restored = False
if 'reading_session_initialized' not in st.session_state:
    session_restored = restore_exam_session()
    st.session_state.reading_session_initialized = True
    
    if session_restored:
        st.success("前回のセッションを復元しました。読解練習を継続できます。")

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
if st.session_state.reading_completed and st.session_state.reading_results:
    st.markdown('<div class="status-box status-success">', unsafe_allow_html=True)
    st.markdown("### 採点完了！")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 結果表示
    st.markdown("### 採点結果")
    st.markdown(st.session_state.reading_results)
    
    # アクションボタン
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("再度挑戦する", type="primary", use_container_width=True):
            for var in session_vars:
                st.session_state[var] = session_vars[var]
            st.rerun()
    
    with col2:
        if st.button("学習履歴を見る", use_container_width=True):
            st.switch_page("pages/05_学習履歴.py")
    
    with col3:
        if st.button("採用試験に挑戦", use_container_width=True):
            st.switch_page("pages/01_採用試験.py")
    
    st.stop()

# プログレスインジケーター
progress_steps = {
    'setup': '🔧 論文選択',
    'reading': '📖 読解・翻訳',
    'scoring': '⚖️ AI採点中',
    'completed': '✅ 完了'
}

st.markdown('<div class="progress-indicator">', unsafe_allow_html=True)
for step_key, step_name in progress_steps.items():
    step_class = ""
    if step_key == st.session_state.reading_step:
        step_class = "active"
    elif (step_key == 'setup' and st.session_state.reading_step in ['reading', 'scoring', 'completed']) or \
         (step_key == 'reading' and st.session_state.reading_step in ['scoring', 'completed']) or \
         (step_key == 'scoring' and st.session_state.reading_step == 'completed'):
        step_class = "completed"
    
    st.markdown(f'<div class="progress-step {step_class}"><strong>{step_name}</strong></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# セットアップフェーズ
if st.session_state.reading_step == 'setup':
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
                        st.session_state.reading_keywords = keyword
                        st.rerun()
    
    with col2:
        with st.expander("📊 過去のキーワード履歴", expanded=False):
            keyword_history = get_keyword_history()
            if keyword_history:
                st.markdown(f"**総履歴数**: {len(keyword_history)}件")
                st.markdown("**最近生成されたキーワード（最新5件）:**")
                st.caption("⚠️ 次回の自動生成時、これらのキーワードと類似したものは避けられます")
                
                recent_history = keyword_history[:5]  # 最新5件（既にソート済み）
                for i, item in enumerate(recent_history, 1):
                    category = item.get('category', '不明')
                    keywords = item.get('keywords', '不明')
                    rationale = item.get('rationale', '')
                    date = item.get('date', '')
                    purpose = item.get('purpose', '')
                    ai_model = item.get('ai_model', '')
                    
                    # 日付のフォーマット
                    formatted_date = ""
                    if date:
                        try:
                            # ISO形式の日付をパースしてフォーマット
                            from datetime import datetime
                            date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                            formatted_date = date_obj.strftime('%m/%d %H:%M')
                        except:
                            formatted_date = date[:10] if len(date) >= 10 else date
                    
                    # カテゴリー名の取得
                    category_name = category
                    if category and category.isdigit():
                        # カテゴリーIDの場合は名前を取得
                        try:
                            from modules.database_v3 import db_manager_v3
                            categories = db_manager_v3.get_all_categories()
                            for cat in categories:
                                if str(cat.get('category_id', '')) == category:
                                    category_name = cat.get('display_name', category)
                                    break
                        except:
                            category_name = f"カテゴリー{category}"
                    
                    # 表示内容
                    st.markdown(f"{i}. **{category_name}**: `{keywords}`")
                    if formatted_date:
                        st.caption(f"   日時: {formatted_date}")
                    if purpose and purpose != 'paper_search':
                        st.caption(f"   目的: {purpose}")
                    if ai_model:
                        st.caption(f"   AI: {ai_model}")
                    if rationale and i <= 3:  # 最新3件のみ理由も表示
                        st.caption(f"   理由: {rationale}")
                    st.markdown("---")
                
                # 過去のキーワードのリストを表示
                past_keywords = [item.get('keywords', '') for item in recent_history if item.get('keywords')]
                if past_keywords:
                    st.markdown("**回避対象キーワード:**")
                    st.code(', '.join([f'"{kw}"' for kw in past_keywords]), language=None)
                
                # 分野使用頻度の表示
                try:
                    from modules.paper_finder import get_keyword_history_with_details
                    detailed_history = get_keyword_history_with_details(limit=20)
                    if detailed_history:
                        category_usage = {}
                        for item in detailed_history:
                            category_id = item.get('category_id', '')
                            if category_id:
                                category_usage[category_id] = category_usage.get(category_id, 0) + 1
                        
                        if category_usage:
                            st.markdown("**分野使用頻度:**")
                            for category_id, count in sorted(category_usage.items(), key=lambda x: x[1], reverse=True)[:5]:
                                try:
                                    from modules.database_v3 import db_manager_v3
                                    categories = db_manager_v3.get_all_categories()
                                    category_name = f"カテゴリー{category_id}"
                                    for cat in categories:
                                        if str(cat.get('category_id', '')) == str(category_id):
                                            category_name = cat.get('display_name', f"カテゴリー{category_id}")
                                            break
                                    st.caption(f"  {category_name}: {count}回")
                                except:
                                    st.caption(f"  カテゴリー{category_id}: {count}回")
                except Exception as e:
                    st.caption(f"分野使用頻度の取得に失敗: {e}")
                
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
        value=st.session_state.get('reading_keywords', ''),
        placeholder="例: diabetes mellitus, hypertension, COVID-19",
        help="医学論文のPubMed検索に使用するキーワードを英語で入力してください。空白の場合、AIが医師国家試験範囲内から臨床的に重要なキーワードを自動選択します。"
    )
    
    # 過去問スタイル出題設定
    st.markdown("---")
    st.markdown("### 🎯 出題形式設定")
    
    # 過去問スタイル有効化チェックボックス
    exam_style_enabled = st.checkbox(
        "過去問スタイルで出題する",
        value=st.session_state.get('exam_style_enabled', False),
        help="論文を県総採用試験の過去問と同様の形式に変換して出題します"
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
                "出題形式を選択",
                options=list(format_options.keys()),
                format_func=lambda x: format_options[x],
                index=0 if st.session_state.get('exam_format_type', 'letter_translation_opinion') == 'letter_translation_opinion' else 1,
                help="過去問の出題形式を選択してください"
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
        
        📋 **この形式での出題内容**:
        {"- 論文のAbstractを翻訳する課題" if selected_format == 'letter_translation_opinion' else "- 論文に対するコメントを翻訳する課題"}
        {"- 論文の内容について意見を述べる課題" if selected_format == 'letter_translation_opinion' else "- コメントについて意見を述べる課題"}
        
        ⚠️ **注意**: 過去問スタイルを有効にすると、AIが論文を県総採用試験の形式に変換します（変換時間: 追加で約30秒）
        """)
    else:
        st.info("""
        **標準形式**: 論文のAbstractを直接翻訳・考察する形式で出題されます
        """)
    
    st.markdown("---")
    
    # 読解練習開始ボタン
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("読解練習開始", type="primary", use_container_width=True):
            loading_message = "論文を準備中..."
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
                paper_result = find_medical_paper(keywords, "english_reading")
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
                
                # セッション状態更新
                st.session_state.paper_data = paper_result
                st.session_state.reading_step = 'reading'
                st.session_state.reading_keywords = paper_result.get('keywords_used', keywords)
                st.session_state.reading_start_time = time.time()  # 開始時間を記録
                
            success_msg = "準備完了！読解練習を開始します。"
            if not keywords.strip():
                selected_keywords = paper_result.get('keywords_used', '')
                selected_category = paper_result.get('category', '')
                if selected_category:
                    success_msg += f"\n**選択された分野**: {selected_category}"
                success_msg += f"\n**キーワード**: `{selected_keywords}`"
            
            if exam_style_enabled and st.session_state.exam_formatted_data:
                success_msg += f"\n**出題形式**: 過去問スタイル（{format_options[st.session_state.exam_format_type]}）"
            else:
                success_msg += f"\n**出題形式**: 標準形式"
            
            st.success(success_msg)
            time.sleep(1)
            st.rerun()
    
    with col2:
        st.markdown("#### 練習概要")
        st.markdown("""
        - **課題数**: 2課題
        - **制限時間**: なし
        - **自動採点**: AI採点
        """)
    
    st.markdown('</div>', unsafe_allow_html=True)

# 読解練習フェーズ
elif st.session_state.reading_step == 'reading':
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
        st.info(f"🎯 **過去問スタイル出題**: {format_names.get(format_type, '不明')}")
    
    # 課題1: 翻訳
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
        st.markdown("### 課題1: Abstract読解・翻訳")
        
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

    # 課題2: 意見・考察（Letter形式または標準形式の場合のみ）
    if not is_exam_style or format_type == "letter_translation_opinion":
        st.markdown('<div class="task-card">', unsafe_allow_html=True)
        if is_exam_style:
            st.markdown("### 課題2: Letterについての意見")
            task2_instruction = exam_data.get('task2', 'このletterを読んで、あなたの意見を述べなさい (A4を1枚)')
            st.markdown(f"**課題**: {task2_instruction}")
            opinion_prompt = "このletterの内容について、あなたの意見や考察を述べてください。"
        else:
            st.markdown("### 課題2: Abstractについての意見・考察")
            opinion_prompt = "このAbstractの内容について、あなたの意見や考察を述べてください。"
        
        opinion = st.text_area(
            opinion_prompt,
            height=600,
            key="opinion",
            label_visibility="collapsed",
            help="論文の内容を理解した上で、独自の視点や洞察を含めた意見を記述してください"
        )
    else:
        # コメント形式の場合は意見も課題1に含まれるため、課題2は設定しない
        opinion = ""  # 空の意見として扱う
        
        col1, col2 = st.columns([4, 1])
        with col1:
            st.caption(f"入力文字数: {len(opinion)}文字")
            if opinion and len(opinion) >= 50:
                target_ratio = len(opinion) / 300  # 300文字を目安とした進捗
                st.progress(min(target_ratio, 1.0))
        with col2:
            if opinion and len(opinion) >= 200:
                st.success("充分")
            elif opinion and len(opinion) >= 100:
                st.warning("やや少ない")
            elif opinion and len(opinion) >= 50:
                st.info("最低限")
            else:
                st.error("不足")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # 提出ボタン
    col1, col2 = st.columns([3, 1])
    with col1:
        # 入力チェック（過去問形式に対応）
        if is_exam_style and format_type == "paper_comment_translation_opinion":
            # コメント形式: 翻訳のみで判定（意見も同じテキストエリアに含まれる）
            can_submit = translation and len(translation.strip()) >= 100
            submit_help = "コメントの翻訳と意見を合わせて100文字以上入力してください。"
        else:
            # Letter形式または標準形式: 翻訳 + 意見の両方が必要
            can_submit = (
                translation and len(translation.strip()) >= 30 and
                opinion and len(opinion.strip()) >= 50
            )
            submit_help = "翻訳（30文字以上）と意見（50文字以上）の両方を入力してください。"
        
        if st.button("提出して採点する", type="primary", use_container_width=True, disabled=not can_submit):
            if not can_submit:
                st.error(f"入力が不足しています。{submit_help}")
            else:
                # 採点フェーズへ移行
                st.session_state.reading_step = 'scoring'
                
                # 提出データの準備（過去問スタイルに対応）
                if is_exam_style:
                    submitted_data = {
                        'translation': translation,
                        'opinion': opinion if format_type == "letter_translation_opinion" else "",
                        'keywords': st.session_state.get('reading_keywords', ''),
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
                        'keywords': st.session_state.get('reading_keywords', ''),
                        'exam_style': False,
                        'abstract': st.session_state.paper_data['abstract'],
                        'citations': st.session_state.paper_data.get('citations', [])
                    }
                
                st.session_state.submitted_reading_data = submitted_data
                st.rerun()
    
    with col2:
        if not can_submit:
            st.warning("入力不足")
            if is_exam_style and format_type == "paper_comment_translation_opinion":
                st.caption("翻訳+意見で100文字以上")
            else:
                st.caption("翻訳30文字+ & 意見50文字+")
        else:
            st.success("提出準備完了")

# 採点フェーズ
elif st.session_state.reading_step == 'scoring':
    st.markdown("""
    <div class="status-box status-info">
        <h4>AI採点中</h4>
        <p>提出された回答をAIが採点しています。しばらくお待ちください...</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 採点実行（過去問スタイルに対応）
    submitted = st.session_state.submitted_reading_data
    
    if submitted.get('exam_style', False):
        # 過去問スタイルの採点
        exam_data = submitted.get('exam_data', {})
        format_type = submitted.get('format_type', 'letter_translation_opinion')
        
        if format_type == "letter_translation_opinion":
            content = exam_data.get('formatted_content', '')
            task_instruction = f"{exam_data.get('task1', '')} / {exam_data.get('task2', '')}"
            stream = score_exam_style_stream(
                content,
                submitted['translation'],
                submitted['opinion'],
                format_type,
                task_instruction
            )
        else:  # paper_comment_translation_opinion
            content = exam_data.get('formatted_content', {})
            task_instruction = exam_data.get('task1', '')
            stream = score_exam_style_stream(
                content,
                submitted.get('comment_response', submitted['translation']),
                "",  # 意見はcomment_responseに含まれている
                format_type,
                task_instruction
            )
    else:
        # 標準形式の採点
        stream = score_reading_stream(
            submitted['abstract'],
            submitted['translation'],
            submitted['opinion']
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
                progress = min(chunk_count / 40, 1.0)  # 読解は少し短めに想定
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
        start_time = st.session_state.get('reading_start_time', completion_time)
        duration_seconds = completion_time - start_time
        duration_minutes = int(duration_seconds // 60)
        duration_seconds_remainder = int(duration_seconds % 60)
        
        if submitted.get('exam_style', False):
            exam_type = "english_reading_practice"  # 新DBに存在するタイプ名
            format_names = {
                "letter_translation_opinion": "english_reading_letter_style",
                "paper_comment_translation_opinion": "english_reading_comment_style"
            }
            format_type = submitted.get('format_type', 'letter_translation_opinion')
            if format_type in format_names:
                exam_type = format_names[format_type]
        else:
            exam_type = "english_reading_practice"  # 新DBに存在するタイプ名
        
        history_data = {
            "type": exam_type,
            "date": datetime.now().isoformat(),
            "duration_seconds": duration_seconds,
            "duration_display": f"{duration_minutes}分{duration_seconds_remainder}秒",
            "inputs": submitted,
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
                file_name=f"reading_result_{os.path.splitext(os.path.basename(filename))[0]}.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        # セッション状態更新
        st.session_state.reading_completed = True
        st.session_state.reading_results = full_feedback
        st.session_state.reading_step = 'completed'
        
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
    st.markdown("### 読解練習情報")
    
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
    
    if st.session_state.reading_step != 'setup':
        st.markdown(f"**現在のステップ:** {progress_steps.get(st.session_state.reading_step, 'N/A')}")
    
    st.markdown("### 採点基準")
    score_dist = get_reading_score_distribution()
    
    for category, scores in score_dist.items():
        with st.expander(f"📊 {category}の採点基準"):
            for score_range, description in scores.items():
                st.markdown(f"**{score_range}**: {description}")
    
    st.markdown("### ヒント")
    st.markdown("""
    - **日本語訳**: 正確性と自然さのバランスを重視
    - **意見・考察**: 論文の内容を深く理解し、独自の視点を含める
    - **専門用語**: 適切な医学用語を使用して翻訳する
    - **文脈理解**: 論文全体の流れを把握して翻訳・考察する
    """)
    
    if st.button("最初からやり直す", use_container_width=True):
        for var in session_vars:
            st.session_state[var] = session_vars[var]
        st.rerun() 