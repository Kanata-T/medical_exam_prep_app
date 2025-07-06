import streamlit as st
import time
from datetime import datetime
from modules.essay_scorer import (generate_long_essay_theme, score_long_essay_stream, 
                                get_essay_themes_samples, get_essay_writing_tips)
from modules.utils import (check_api_configuration, show_api_setup_guide,
                          extract_scores, save_history, format_history_for_download,
                          auto_save_session)
import os

st.set_page_config(
    page_title="小論文対策",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="auto"
)

# カスタムCSS
st.markdown("""
<style>
    .main-header {
        font-weight: bold;
        color: #333;
        padding-bottom: 1rem;
        border-bottom: 2px solid #eee;
        margin-bottom: 2rem;
    }
    .status-box {
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
        border-left: 5px solid;
    }
    .status-success { border-color: #28a745; background-color: #f0fff4; }
    .status-warning { border-color: #ffc107; background-color: #fffaf0; }
    .status-error { border-color: #dc3545; background-color: #fff0f1; }
    .status-info { border-color: #17a2b8; background-color: #f0f8ff; }

    .task-card {
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
        background-color: #f8f9fa;
    }
    
    .word-counter {
        color: #6c757d;
        font-size: 0.9rem;
    }
    
    .progress-text {
        font-size: 0.9rem;
        color: #6c757d;
        text-align: right;
        margin-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# タイトル
st.markdown('<h1 class="main-header">小論文対策</h1>', unsafe_allow_html=True)

# セッション状態の初期化
session_vars = {
    'long_essay_theme': "",
    'essay_step': 'setup',  # setup, writing, scoring, completed
    'essay_completed': False,
    'essay_results': None,
    'start_time': 0
}

for var, default in session_vars.items():
    if var not in st.session_state:
        st.session_state[var] = default

# セッション自動保存
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
if st.session_state.essay_completed and st.session_state.essay_results:
    st.success("採点が完了しました。")
    
    # 結果表示
    st.markdown("### 採点結果")
    with st.container(border=True):
        st.markdown(st.session_state.essay_results)
    
    # アクションボタン
    st.markdown("---")
    st.markdown("#### 次のアクション")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("新しいテーマで練習", type="primary", use_container_width=True):
            for var in session_vars:
                st.session_state[var] = session_vars[var]
            st.rerun()
    
    with col2:
        if st.button("学習履歴を見る", use_container_width=True):
            st.switch_page("pages/4_📊_学習履歴.py") # 後でファイル名変更を反映
    
    st.stop()

# プログレス表示
progress_steps = {
    'setup': 'ステップ1: テーマ選択',
    'writing': 'ステップ2: 執筆',
    'scoring': 'ステップ3: AI採点中',
    'completed': '完了'
}
st.info(f"現在のステップ: **{progress_steps.get(st.session_state.essay_step, '不明')}**")


# セットアップフェーズ
if st.session_state.essay_step == 'setup':
    with st.container(border=True):
        st.markdown("### 小論文テーマの選択")
        st.markdown("練習したいテーマを選択するか、AIに新しいテーマを生成させてください。")

        # サンプルテーマ
        with st.expander("サンプルテーマから選択"):
            sample_themes = get_essay_themes_samples()
            for i, theme in enumerate(sample_themes):
                if st.button(theme, key=f"sample_theme_{i}", use_container_width=True):
                    st.session_state.long_essay_theme = theme
                    st.session_state.essay_step = 'writing'
                    st.session_state.start_time = time.time()
                    st.rerun()
        
        # テーマ生成
        if st.button("AIでランダムテーマ生成", type="primary", use_container_width=True):
            with st.spinner("AIが医療系小論文テーマを生成中です..."):
                theme_result = generate_long_essay_theme()
                if 'error' in theme_result:
                    st.error(f"テーマ生成エラー: {theme_result['error']}")
                else:
                    st.session_state.long_essay_theme = theme_result['theme']
                    st.session_state.essay_step = 'writing'
                    st.session_state.start_time = time.time()
                    st.success("テーマが生成されました。執筆を開始してください。")
                    time.sleep(1)
                    st.rerun()

    with st.expander("小論文作成のヒント"):
        st.markdown("##### 構成の目安時間")
        st.markdown("- **構成メモ**: 15分\n- **清書**: 40分\n- **見直し**: 5分")
        st.markdown("---")
        tips = get_essay_writing_tips()
        for category, tip_list in tips.items():
            st.markdown(f"**{category}**")
            for tip in tip_list:
                st.markdown(f"- {tip}")
            st.markdown("")

# 執筆フェーズ
elif st.session_state.essay_step == 'writing':
    # 経過時間表示
    if st.session_state.start_time > 0:
        elapsed_time = time.time() - st.session_state.start_time
        elapsed_minutes = int(elapsed_time // 60)
        elapsed_seconds = int(elapsed_time % 60)
        st.caption(f"経過時間: {elapsed_minutes:02d}分{elapsed_seconds:02d}秒 | 推奨時間: 60分以内")
    
    # テーマ表示と変更
    with st.container(border=True):
        st.markdown("#### 選択されたテーマ")
        st.markdown(f"**{st.session_state.long_essay_theme}**")
        if st.button("別のテーマに変更", use_container_width=True):
            st.session_state.essay_step = 'setup'
            st.session_state.long_essay_theme = ""
            st.rerun()
    
    # 構成メモ
    with st.container(border=True):
        st.markdown("##### Step 1: 構成メモ")
        st.markdown("まず、小論文の骨子やアイデアを整理しましょう。")
        
        memo = st.text_area(
            "構成メモ",
            height=200,
            key="memo",
            placeholder="序論・本論・結論の構成、主要な論点、具体例などを書き出してください。",
            label_visibility="collapsed"
        )
        st.markdown(f"<div class='word-counter'>文字数: {len(memo)}</div>", unsafe_allow_html=True)

    # 清書
    with st.container(border=True):
        st.markdown("##### Step 2: 清書")
        st.markdown("構成メモをもとに、1000字程度の小論文を作成してください。")
        
        essay = st.text_area(
            "清書（1000字程度）",
            height=400,
            key="essay",
            placeholder="序論・本論・結論の構成を意識し、論理的で説得力のある小論文を作成してください。",
            label_visibility="collapsed"
        )
        
        # 文字数とプログレス
        essay_len = len(essay)
        st.markdown(f"<div class='word-counter'>文字数: {essay_len} / 1000字目安</div>", unsafe_allow_html=True)
        progress = min(essay_len / 1000, 1.0)
        st.progress(progress)
        
    # 提出ボタン
    can_submit = (
        memo and len(memo.strip()) >= 20 and
        essay and len(essay.strip()) >= 200
    )
    
    if st.button("提出して採点する", type="primary", use_container_width=True, disabled=not can_submit):
        if not can_submit:
            st.error("構成メモと清書の両方に適切な内容を入力してください。")
        else:
            # 採点フェーズへ移行
            st.session_state.essay_step = 'scoring'
            st.session_state.submitted_data = {
                'memo': memo,
                'essay': essay,
                'theme': st.session_state.long_essay_theme
            }
            st.rerun()
    if not can_submit:
        st.caption("構成メモ(20字以上)と清書(200字以上)の両方を入力すると提出できます。")


# 採点フェーズ
elif st.session_state.essay_step == 'scoring':
    st.info("AIが採点中です。結果が表示されるまでしばらくお待ちください...")
    
    # 採点実行
    submitted = st.session_state.submitted_data
    stream = score_long_essay_stream(
        submitted['theme'],
        submitted['memo'],
        submitted['essay']
    )
    
    # 採点結果表示
    with st.container(border=True):
        st.markdown("### 採点結果")
        feedback_placeholder = st.empty()
        full_feedback = ""
        
        progress_bar = st.progress(0, "採点中...")
        
        try:
            chunk_count = 0
            for chunk in stream:
                chunk_count += 1
                if hasattr(chunk, 'text') and chunk.text:
                    full_feedback += chunk.text
                    feedback_placeholder.markdown(full_feedback + "▌")
                    
                    # プログレスバー更新（概算）
                    progress = min(chunk_count / 40, 1.0)
                    progress_bar.progress(progress, "採点中...")
            
            # 採点完了
            feedback_placeholder.markdown(full_feedback)
            progress_bar.progress(1.0, "採点完了")
            
            # 履歴保存
            scores = extract_scores(full_feedback)
            history_data = {
                "type": "小論文対策",
                "date": datetime.now().isoformat(),
                "inputs": {
                    "theme": submitted['theme'],
                    "memo": submitted['memo'],
                    "essay": submitted['essay']
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
                    file_name=f"essay_result_{os.path.splitext(os.path.basename(filename))[0]}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            # セッション状態更新
            st.session_state.essay_completed = True
            st.session_state.essay_results = full_feedback
            st.session_state.essay_step = 'completed'
            
            # 完了ページへリダイレクト
            time.sleep(2)
            st.rerun()
            
        except Exception as e:
            st.error(f"採点処理中にエラーが発生しました: {e}")
            if full_feedback:
                st.info("部分的なフィードバック:")
                st.markdown(full_feedback)
            
            if st.button("最初からやり直す", type="primary", use_container_width=True):
                for var in session_vars:
                    st.session_state[var] = session_vars[var]
                st.rerun()

# サイドバー
with st.sidebar:
    st.header("小論文対策")
    
    st.markdown("---")
    
    st.markdown("##### 現在の状況")
    if st.session_state.essay_step != 'setup':
        st.markdown(f"**ステップ:** {progress_steps[st.session_state.essay_step]}")
        
        if st.session_state.start_time > 0:
            elapsed = time.time() - st.session_state.start_time
            st.markdown(f"**経過時間:** {int(elapsed // 60)}分{int(elapsed % 60)}秒")
    else:
        st.markdown("テーマ選択待ちです。")

    st.markdown("---")

    if st.button("セッションをリセット", use_container_width=True, type="secondary"):
        for var in session_vars:
            st.session_state[var] = session_vars[var]
        st.rerun()
        
    with st.expander("評価のポイント"):
        st.markdown("""
        - **構成メモ**: アイデア・論理・発展性
        - **清書**: 構成・論証・表現・深化
        - **医療系**: 現場目線を意識
        - **時事性**: 最新の動向を踏まえる
        """)
