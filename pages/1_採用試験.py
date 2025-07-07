import streamlit as st
import time
from datetime import datetime, timedelta
from modules.paper_finder import find_medical_paper, generate_essay_theme, get_sample_keywords
from modules.scorer import score_exam_stream, get_score_distribution
from modules.utils import (handle_submission, reset_session_state, 
                          check_api_configuration, show_api_setup_guide,
                          extract_scores, save_history, format_history_for_download,
                          restore_exam_session, auto_save_session)
import os

st.set_page_config(
    page_title="医学部採用試験シミュレーター",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
    'time_extended': False
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
            st.switch_page("pages/4_📊_学習履歴.py")
    
    with col3:
        if st.button("小論文対策へ", use_container_width=True):
            st.switch_page("pages/2_✍️_小論文対策.py")
    
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
    
    # サンプルキーワードとAI生成の説明
    with st.expander("🤖 AIによる自動キーワード生成について", expanded=False):
        st.markdown("""
        **AIによる自動生成の特徴:**
        - 医師国家試験の出題範囲内から選択
        - 臨床的に重要度の高い分野を優先
        - 最新の医学研究動向を反映
        - PubMedで高品質な論文が見つかりやすいキーワード
        
        **参考：従来のサンプルキーワード**
        """)
        sample_keywords = get_sample_keywords()
        cols = st.columns(3)
        for i, keyword in enumerate(sample_keywords):
            with cols[i % 3]:
                if st.button(keyword, key=f"sample_{i}", use_container_width=True):
                    st.session_state.search_keywords = keyword
                    st.rerun()
    
    # キーワード入力
    keywords = st.text_input(
        "検索したい論文のキーワードを入力してください（空白の場合はAIが自動選択）",
        value=st.session_state.get('search_keywords', ''),
        placeholder="例: diabetes mellitus, hypertension, COVID-19",
        help="医学論文のPubMed検索に使用するキーワードを英語で入力してください。空白の場合、AIが医師国家試験範囲内から臨床的に重要なキーワードを自動選択します。"
    )
    
    # 試験開始ボタン
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("試験開始（60分）", type="primary", use_container_width=True):
            loading_message = "論文とテーマを準備中..."
            if not keywords.strip():
                loading_message += "（AIがキーワードを自動選択中...約45秒）"
            else:
                loading_message += "（約30秒）"
                
            with st.spinner(loading_message):
                # 論文検索
                paper_result = find_medical_paper(keywords)
                if 'error' in paper_result:
                    st.error(f"論文検索エラー: {paper_result['error']}")
                    st.stop()
                
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
                success_msg += f"\n選択されたキーワード: `{paper_result.get('keywords_used', '')}`"
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
        
        # 課題1: Abstract読解と翻訳
        st.markdown('<div class="task-card">', unsafe_allow_html=True)
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

        # 課題1: 意見・考察
        st.markdown('<div class="task-card">', unsafe_allow_html=True)
        st.markdown("#### Abstractを読んでの意見・考察")
        opinion = st.text_area(
            "このAbstractの内容について、あなたの意見や考察を述べてください。",
            height=600,
            key="opinion",
            label_visibility="collapsed",
            help="論文の内容を理解した上で、独自の視点や洞察を含めた意見を記述してください"
        )
        st.caption(f"入力文字数: {len(opinion)}文字")
        st.markdown("</div>", unsafe_allow_html=True)

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
            # 入力チェック
            can_submit = (
                translation and len(translation.strip()) >= 30 and
                opinion and len(opinion.strip()) >= 50 and
                essay and len(essay.strip()) >= 100
            )
            
            if st.button("提出して採点する", type="primary", use_container_width=True, disabled=not can_submit):
                if not can_submit:
                    st.error("すべての項目に適切な分量を入力してください。")
                else:
                    # 採点フェーズへ移行
                    st.session_state.exam_step = 'scoring'
                    st.session_state.submitted_data = {
                        'translation': translation,
                        'opinion': opinion,
                        'essay': essay,
                        'keywords': st.session_state.get('search_keywords', ''),
                        'abstract': st.session_state.paper_data['abstract'],
                        'citations': st.session_state.paper_data.get('citations', [])
                    }
                    st.rerun()
        
        with col2:
            if not can_submit:
                st.warning("入力不足の項目があります")
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
    
    # 採点実行
    submitted = st.session_state.submitted_data
    stream = score_exam_stream(
        submitted['abstract'],
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
        
        # 履歴保存
        scores = extract_scores(full_feedback)
        history_data = {
            "type": "採用試験",
            "date": datetime.now().isoformat(),
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
