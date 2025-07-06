import streamlit as st
from datetime import datetime
from modules.medical_knowledge_checker import (
    generate_medical_question,
    score_medical_answer_stream,
    get_default_themes,
    generate_random_medical_theme
)
from modules.utils import (
    check_api_configuration,
    show_api_setup_guide,
    save_history,
    extract_scores,
    auto_save_session
)

st.set_page_config(
    page_title="自由記述問題対策",
    page_icon="✍️",
    layout="wide"
)

# --- セッション状態の初期化 ---
def initialize_session():
    if 'knowledge_checker' not in st.session_state:
        st.session_state.knowledge_checker = {
            "step": "theme_selection",  # theme_selection, answering, completed
            "theme": "",
            "question": "",
            "answer": "",
            "feedback": None,
            "start_time": None
        }

initialize_session()
s = st.session_state.knowledge_checker

# --- API設定の確認 ---
api_ok, api_message = check_api_configuration()
if not api_ok:
    st.error(f"**API設定エラー:** {api_message}")
    show_api_setup_guide()
    st.stop()

# --- UIコンポーネント ---
def render_theme_selection():
    """テーマ選択画面を表示"""
    st.header("✍️ 自由記述問題対策")
    st.markdown("医師国家試験レベルの自由記述問題の対策を行います。")

    with st.container(border=True):
        st.subheader("1. テーマを選択または入力してください")

        # ランダムテーマ生成ボタン
        if st.button("🎲 ランダムなテーマで出題", use_container_width=True):
            with st.spinner("AIがテーマを考えています..."):
                theme = generate_random_medical_theme()
                if "エラー" not in theme:
                    s['theme'] = theme
                    s['step'] = 'generating_question'
                    st.rerun()
                else:
                    st.error(theme)
        
        st.markdown("<hr>", unsafe_allow_html=True)

        # デフォルトテーマのボタン
        st.markdown("**主要なテーマから選択:**")
        default_themes = get_default_themes()
        cols = st.columns(4)
        for i, theme in enumerate(default_themes):
            with cols[i % 4]:
                if st.button(theme, use_container_width=True, key=f"theme_{i}"):
                    s['theme'] = theme
                    s['step'] = 'generating_question'
                    st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)

        # カスタムテーマ入力
        st.markdown("**自由に対策したいテーマを入力:**")
        custom_theme = st.text_input("（例：COPD、大腸がん）", key="custom_theme_input")
        if st.button("このテーマで問題を作成", type="primary", disabled=not custom_theme):
            s['theme'] = custom_theme
            s['step'] = 'generating_question'
            st.rerun()

def render_question_generation():
    """問題生成中のスピナーを表示"""
    with st.spinner(f"「{s['theme']}」に関する問題を生成しています..."):
        s['question'] = generate_medical_question(s['theme'])
        if "エラー" in s['question']:
            st.error(s['question'])
            s['step'] = 'theme_selection'
        else:
            s['step'] = 'answering'
            s['start_time'] = datetime.now()
    st.rerun()

def render_answering_screen():
    """回答入力画面を表示"""
    st.header(f"テーマ: {s['theme']}")
    
    with st.container(border=True):
        st.subheader("問題")
        st.info(s['question'])

    st.subheader("あなたの回答")
    s['answer'] = st.text_area(
        "ここに回答を入力してください...",
        height=400,
        value=s.get('answer', '')
    )

    if st.button("回答を提出して添削を受ける", type="primary", disabled=len(s['answer']) < 20):
        s['step'] = 'scoring'
        st.rerun()
    
    if st.button("テーマ選択に戻る"):
        s['step'] = 'theme_selection'
        initialize_session() # 状態をリセット
        st.rerun()

def render_scoring_and_feedback():
    """採点とフィードバック表示画面"""
    st.header("評価とフィードバック")

    with st.spinner("AIがあなたの回答を評価・添削しています..."):
        stream = score_medical_answer_stream(s['question'], s['answer'])
        
        with st.container(border=True):
            feedback_placeholder = st.empty()
            full_response = ""
            try:
                for chunk in stream:
                    full_response += chunk.text
                    feedback_placeholder.markdown(full_response + "▌")
            except Exception as e:
                 st.error(f"ストリームの処理中にエラーが発生しました: {e}")

            feedback_placeholder.markdown(full_response)
            s['feedback'] = full_response

    # 履歴保存
    try:
        history_data = {
            "type": "自由記述",
            "date": s['start_time'].isoformat(),
            "inputs": {
                "theme": s['theme'],
                "question": s['question'],
                "answer": s['answer']
            },
            "feedback": s['feedback'],
            "scores": extract_scores(s['feedback'])
        }
        save_history(history_data)
        st.success("今回の学習内容を履歴に保存しました。")
    except Exception as e:
        st.error(f"履歴の保存中にエラーが発生しました: {e}")

    s['step'] = 'completed'
    st.rerun()

def render_completed_screen():
    """完了画面を表示"""
    st.header("評価完了")
    
    with st.container(border=True):
        st.markdown(s['feedback'])

    st.success("お疲れ様でした！")
    if st.button("新しい問題に取り組む", type="primary"):
        # Reset for next round
        initialize_session()
        st.rerun()

# --- メインロジック ---
def main():
    if s['step'] == 'theme_selection':
        render_theme_selection()
    elif s['step'] == 'generating_question':
        render_question_generation()
    elif s['step'] == 'answering':
        render_answering_screen()
    elif s['step'] == 'scoring':
        render_scoring_and_feedback()
    elif s['step'] == 'completed':
        render_completed_screen()

if __name__ == "__main__":
    main()
    auto_save_session()