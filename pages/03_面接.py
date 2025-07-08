import streamlit as st
import time
from datetime import datetime
from modules.interview_prepper import (generate_interview_question, score_interview_answer_stream,
                                     get_interview_question_categories, get_interview_tips,
                                     conduct_interview_session_stream)
from modules.utils import (check_api_configuration, show_api_setup_guide,
                          extract_scores, save_history, format_history_for_download,
                          auto_save_session)
import os
import base64
from io import BytesIO

# 音声機能の依存関係チェック
AUDIO_FEATURES_AVAILABLE = False
try:
    from gtts import gTTS
    import speech_recognition as sr
    AUDIO_FEATURES_AVAILABLE = True
except ImportError:
    pass

st.set_page_config(
    page_title="面接対策",
    page_icon="💼",
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
        margin-bottom: 1rem;
    }
    .stButton>button {
        font-size: 1.1rem;
        font-weight: bold;
    }
    .mode-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 2rem;
        text-align: center;
        transition: all 0.3s;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .mode-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .chat-bubble {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        max-width: 80%;
        width: fit-content;
    }
    .chat-bubble.user {
        background-color: #e6f3ff;
        margin-left: auto;
        text-align: right;
    }
    .chat-bubble.ai {
        background-color: #f1f1f1;
    }
    .chat-bubble-role {
        font-weight: bold;
        font-size: 0.9em;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# --- セッション状態管理 ---
def initialize_session_state():
    # ページ全体で共有
    if 'interview_mode' not in st.session_state:
        st.session_state.interview_mode = None  # None, 'single', 'session'
    
    # 単発練習用
    if 'single_practice_vars' not in st.session_state:
        st.session_state.single_practice_vars = {
            'question': "", 'category': "", 'step': 'setup',
            'completed': False, 'results': None, 'user_answer': "",
            'start_time': 0, 'play_question_audio': False
        }

    # 模擬セッション用
    if 'session_practice_vars' not in st.session_state:
        st.session_state.session_practice_vars = {
            'state': 'not_started',  # not_started, ongoing, completed
            'chat_history': [],  # {'role': 'ai'/'user', 'content': '...'}
            'session_start_time': 0,
            'is_responding': False # AIが応答中かどうかのフラグ
        }

initialize_session_state()

# --- 共通関数 ---

# API設定確認 (共通)
api_ok, api_message = check_api_configuration()
if not api_ok:
    st.error(f"**API設定エラー:** {api_message}")
    show_api_setup_guide()
    st.stop()

def create_audio_html(text: str, autoplay: bool = False) -> str | None:
    if not AUDIO_FEATURES_AVAILABLE: return None
    try:
        fp = BytesIO()
        tts = gTTS(text=text, lang='ja')
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_base64 = base64.b64encode(fp.read()).decode('utf-8')
        autoplay_attr = "autoplay" if autoplay else ""
        return f'<audio controls {autoplay_attr} style="width: 100%;"><source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3"></audio>'
    except Exception as e:
        st.warning(f"音声生成エラー: {e}")
        return None

def safe_recognize_speech():
    if not AUDIO_FEATURES_AVAILABLE:
        st.error("音声認識機能は利用できません。")
        return ""
    try:
        r = sr.Recognizer()
        with sr.Microphone() as source:
            st.info("マイクに向かって話してください...")
            with st.spinner("音声認識中..."):
                audio = r.listen(source, timeout=10, phrase_time_limit=60)
            text = r.recognize_google(audio, language='ja-JP')
            st.success("音声をテキストに変換しました。")
            return text
    except Exception as e:
        st.warning(f"音声認識エラー: {e}")
        return ""

# --- モード選択UI ---
def render_mode_selection():
    st.markdown('<h1 class="main-header">面接対策</h1>', unsafe_allow_html=True)
    st.markdown("### 練習モードを選択してください")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True, height=250):
            st.markdown("#### 🎯 単発練習")
            st.write("特定の質問に対して、集中的に回答を練習します。一つ一つの回答を深く掘り下げたい場合におすすめです。")
            if st.button("単発練習を始める", use_container_width=True, type="secondary"):
                st.session_state.interview_mode = 'single'
                st.rerun()
    with col2:
        with st.container(border=True, height=250):
            st.markdown("#### 💬 模擬面接セッション")
            st.write("入室から退室まで、実際の面接に近い流れで練習します。文脈を維持したAIとの対話を通じて、総合的な面接力を鍛えます。")
            if st.button("模擬面接を始める", use_container_width=True, type="primary"):
                st.session_state.interview_mode = 'session'
                st.rerun()

# --- 単発練習モード ---
def run_single_practice():
    st.markdown('<h1 class="main-header">面接対策 (単発練習)</h1>', unsafe_allow_html=True)
    
    # 状態をローカル変数に展開（個別に参照）
    vars_dict = st.session_state.single_practice_vars
    
    # 完了後の表示
    if vars_dict.get('completed', False) and vars_dict.get('results'):
        st.success("評価が完了しました。")
        st.markdown("### 評価結果")
        with st.container(border=True):
            st.markdown(vars_dict['results'])
        
        # 追加質問機能
        from modules.utils import render_followup_chat, clear_followup_chat
        
        # 元のコンテンツを準備
        original_content = {
            'question': vars_dict.get('question', ''),
            'answer': vars_dict.get('user_answer', '')
        }
        
        # 追加質問チャット機能
        render_followup_chat(
            original_content=original_content,
            original_results=vars_dict['results'],
            question_type="面接",
            session_key="interview_followup"
        )
        
        # アクションボタン
        st.markdown("---")
        st.markdown("#### 次のアクション")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("新しい質問で練習", type="primary", use_container_width=True):
                # チャット履歴もクリア
                clear_followup_chat("interview_followup")
                st.session_state.single_practice_vars = {
                    'question': "", 'category': "", 'step': 'setup', 'completed': False, 
                    'results': None, 'user_answer': "", 'start_time': 0, 'play_question_audio': False
                }
                st.rerun()
        
        with col2:
            if st.button("質問履歴をクリア", use_container_width=True):
                clear_followup_chat("interview_followup")
                st.rerun()
        
        return

    # セットアップ
    if vars_dict.get('step') == 'setup':
        with st.container(border=True):
            st.markdown("### 質問の選択")
            question_categories = get_interview_question_categories()
            tabs = st.tabs(list(question_categories.keys()))
            for tab, (category, questions) in zip(tabs, question_categories.items()):
                with tab:
                    for i, q in enumerate(questions):
                        if st.button(q, key=f"sq_{category}_{i}", use_container_width=True):
                            st.session_state.single_practice_vars.update({
                                'question': q, 'category': category, 'step': 'answering',
                                'start_time': time.time(), 'play_question_audio': True
                            })
                            st.rerun()
            if st.button("AIでランダムな質問を生成", type="primary", use_container_width=True):
                with st.spinner("AIが質問を生成中..."):
                    res = generate_interview_question()
                    st.session_state.single_practice_vars.update({
                        'question': res['question'], 'category': res.get('category', '一般'),
                        'step': 'answering', 'start_time': time.time(), 'play_question_audio': True
                    })
                    st.rerun()

    # 回答
    elif vars_dict.get('step') == 'answering':
        st.markdown("#### 面接官からの質問")
        st.info(f"##### 「{vars_dict.get('question', '')}」")

        audio_placeholder = st.empty()
        if vars_dict.get('play_question_audio', False):
            audio_html = create_audio_html(vars_dict.get('question', ''), autoplay=True)
            if audio_html: 
                audio_placeholder.markdown(audio_html, unsafe_allow_html=True)
            st.session_state.single_practice_vars['play_question_audio'] = False # Ensure this block runs only once
            
            # Automatically start voice recognition after playing audio
            st.info("質問の再生が終わったら、回答の音声認識が自動で始まります。")
            recognized_text = safe_recognize_speech()
            if recognized_text:
                st.session_state.single_practice_vars['user_answer'] = recognized_text
                st.rerun()

        answer = st.text_area("あなたの回答（音声認識後に編集できます）", height=250, value=vars_dict.get('user_answer', ''))
        st.session_state.single_practice_vars['user_answer'] = answer
        
        col1, col2 = st.columns([1,1])
        with col1:
            if AUDIO_FEATURES_AVAILABLE:
                if st.button("🎤 もう一度音声で入力する", use_container_width=True):
                    recognized_text = safe_recognize_speech()
                    if recognized_text:
                        st.session_state.single_practice_vars['user_answer'] = recognized_text
                        st.rerun()
        
        with col2:
            if st.button("回答を提出して評価を受ける", type="primary", disabled=len(answer) < 10, use_container_width=True):
                st.session_state.single_practice_vars['step'] = 'scoring'
                st.rerun()

    # 評価
    elif vars_dict.get('step') == 'scoring':
        st.info("AIが評価中です...")
        stream = score_interview_answer_stream(vars_dict.get('question', ''), vars_dict.get('user_answer', ''))
        with st.container(border=True):
            feedback = st.write_stream(stream)
        st.session_state.single_practice_vars['results'] = feedback
        st.session_state.single_practice_vars['completed'] = True
        # 履歴保存
        history_data = {
            "type": "面接対策(単発)", "date": datetime.now().isoformat(),
            "inputs": {"question": vars_dict.get('question', ''), "answer": vars_dict.get('user_answer', '')},
            "feedback": feedback, "scores": extract_scores(feedback)
        }
        save_history(history_data)
        st.rerun()

# --- 模擬面接セッションモード ---
def run_session_practice():
    st.markdown('<h1 class="main-header">面接対策 (模擬面接セッション)</h1>', unsafe_allow_html=True)
    
    # 状態をローカル変数に展開
    state = st.session_state.session_practice_vars

    # チャット履歴表示
    for msg in state['chat_history']:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # AIの応答に音声再生ボタンを追加
            if msg["role"] == "ai" and AUDIO_FEATURES_AVAILABLE:
                audio_html = create_audio_html(msg["content"])
                if audio_html:
                    st.markdown(audio_html, unsafe_allow_html=True)


    # メインロジック
    if state['state'] == 'not_started':
        if st.button("模擬面接を開始する", type="primary", use_container_width=True):
            state['state'] = 'ongoing'
            state['is_responding'] = True
            st.rerun()

    elif state['state'] == 'ongoing':
        # AIの応答を処理 (セッション開始直後またはユーザーの入力後)
        if state['is_responding']:
            with st.chat_message("ai"):
                placeholder = st.empty()
                full_response = ""
                # 履歴が空の場合、最初の発言を生成
                stream = conduct_interview_session_stream(state['chat_history'])
                for chunk in stream:
                    if hasattr(chunk, 'text') and chunk.text:
                        full_response += chunk.text
                        placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)
                
            state['chat_history'].append({"role": "ai", "content": full_response})
            state['is_responding'] = False
            
            # 終了判定
            if "---" in full_response and "【総合フィードバック】" in full_response:
                state['state'] = 'completed'
                feedback_part = full_response.split("---", 1)[1]
                history_data = {
                    "type": "面接対策(セッション)", "date": datetime.now().isoformat(),
                    "inputs": {"conversation": state['chat_history']},
                    "feedback": feedback_part, "scores": extract_scores(feedback_part)
                }
                save_history(history_data)
            
            st.rerun()

        # --- ユーザー入力エリア ---
        # AIが応答中でない場合にのみ表示
        if not state['is_responding']:
            # 音声入力ボタン
            if AUDIO_FEATURES_AVAILABLE:
                if st.button("🎤 音声で回答する", use_container_width=True):
                    recognized_text = safe_recognize_speech()
                    if recognized_text:
                        state['chat_history'].append({"role": "user", "content": recognized_text})
                        state['is_responding'] = True
                        st.rerun()

            # テキスト入力
            prompt = st.chat_input("または、テキストで回答を入力", disabled=state['is_responding'])
            if prompt:
                state['chat_history'].append({"role": "user", "content": prompt})
                state['is_responding'] = True
                st.rerun()

    elif state['state'] == 'completed':
        st.success("模擬面接セッションが完了しました。お疲れ様でした！")
        st.info("最終評価は上記チャット履歴の末尾に記載されています。")
        if st.button("新しいセッションを始める", type="primary"):
            st.session_state.session_practice_vars = {
                'state': 'not_started', 'chat_history': [], 
                'session_start_time': 0, 'is_responding': False
            }
            st.rerun()


# --- メインルーチン ---
def main():
    if st.session_state.interview_mode is None:
        render_mode_selection()
    elif st.session_state.interview_mode == 'single':
        run_single_practice()
    elif st.session_state.interview_mode == 'session':
        run_session_practice()

    # サイドバー
    with st.sidebar:
        st.header("面接対策")
        if st.session_state.interview_mode:
            if st.button("モード選択に戻る", use_container_width=True):
                st.session_state.interview_mode = None
                # reset states
                initialize_session_state()
                st.rerun()
        
        st.markdown("---")
        st.markdown("##### 音声機能")
        if AUDIO_FEATURES_AVAILABLE:
            st.success("利用可能")
        else:
            st.warning("利用不可。`uv pip install gtts SpeechRecognition` を実行してください。")

if __name__ == "__main__":
    main()

    # セッション状態の自動保存
    auto_save_session(page_key="interview")
