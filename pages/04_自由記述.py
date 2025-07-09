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
    auto_save_session,
    get_recent_themes,
    get_theme_history,
    is_theme_recently_used,
    render_progress_comparison,
    save_recent_theme
)

st.set_page_config(
    page_title="医学部採用試験 自由記述対策",
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
    st.header("✍️ 医学部採用試験 自由記述対策")
    st.markdown("医学部採用試験で実際に出題される形式の自由記述問題で対策を行います。")
    
    # 医学部採用試験の特徴を説明
    with st.expander("📋 医学部採用試験 自由記述問題の特徴", expanded=False):
        st.markdown("""
        **🎯 出題形式の種類**:
        - **基本知識型**: 「〜について知っていることを述べよ」
        - **患者説明型**: 「小学6年生にもわかるように説明せよ」  
        - **臨床評価型**: 「assessmentとplanを作れ」
        - **鑑別診断型**: 「鑑別疾患と鑑別検査を述べよ」
        - **診察・検査型**: 「どのような診察や検査を行うか」
        - **治療計画型**: 「治療方針について述べよ」
        - **診断基準型**: 「診断基準と治療法を記載せよ」
        - **合併症型**: 「合併症とその対策について」
        
        **📝 評価ポイント**:
        - 国試レベルを超えた実践的知識
        - 患者安全を考慮した判断力
        - チーム医療での連携意識
        - Evidence-based medicineに基づく記述
        """)

    # 最近のテーマを取得（過去5回分を回避するため）
    recent_themes = get_recent_themes("自由記述", 5)
    
    with st.container(border=True):
        st.subheader("1. テーマを選択または入力してください")

        # 最近のテーマがある場合は警告を表示
        if recent_themes:
            st.info(f"💡 最近の練習テーマ（過去5回）: {', '.join(recent_themes[:5])} \n過去5回と重複しないテーマを選択することで、バランス良く学習できます。")

        # ランダムテーマ生成ボタン
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("🎲 AIが医学部採用試験形式でランダム出題", use_container_width=True, type="primary"):
                with st.spinner("医学部採用試験形式の問題を生成中..."):
                    # 過去5回のテーマを取得して回避
                    recent_themes = get_recent_themes("自由記述", 5)
                    
                    # 最大5回試行して、過去5回と重複しないテーマを生成
                    max_attempts = 5
                    generated_theme = None
                    
                    for attempt in range(max_attempts):
                        theme = generate_random_medical_theme(avoid_themes=recent_themes)
                        
                        # エラーチェック
                        if "エラー" in theme:
                            if attempt == max_attempts - 1:
                                st.error(f"テーマ生成でエラーが発生しました: {theme}")
                                break
                            continue
                        
                        # 過去5回のテーマとの重複チェック
                        if theme not in recent_themes:
                            generated_theme = theme
                            break
                        elif attempt == max_attempts - 1:
                            # 最後の試行でも重複する場合は警告して使用
                            st.warning(f"⚠️ 「{theme}」は最近出題されましたが、他に適切なテーマが見つからないため使用します。")
                            generated_theme = theme
                            break
                    
                    if generated_theme:
                        s['theme'] = generated_theme
                        save_recent_theme(generated_theme)
                        s['step'] = 'generating_question'
                        st.success(f"新しいテーマ「{generated_theme}」で医学部採用試験形式の問題を生成します！")
                        st.rerun()
        
        with col2:
            st.caption("🎯 8つの問題形式からランダムに選択")
        
        st.markdown("<hr>", unsafe_allow_html=True)

        # デフォルトテーマのボタン
        st.markdown("**医学部採用試験 頻出テーマから選択:**")
        default_themes = get_default_themes()
        
        # 確認待ちのテーマがあるかチェック
        if 'pending_theme_confirmation' not in st.session_state:
            st.session_state.pending_theme_confirmation = None
        
        # 確認ダイアログの表示
        if st.session_state.pending_theme_confirmation:
            theme = st.session_state.pending_theme_confirmation
            st.warning(f"⚠️ 「{theme}」は過去5回以内に練習済みです。本当に続けますか？")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("はい、続けます", type="primary", use_container_width=True):
                    s['theme'] = theme
                    save_recent_theme(theme)
                    s['step'] = 'generating_question'
                    st.session_state.pending_theme_confirmation = None
                    st.rerun()
            with col2:
                if st.button("別のテーマを選ぶ", use_container_width=True):
                    st.session_state.pending_theme_confirmation = None
                    st.rerun()
        else:
            # 通常のテーマ選択ボタン
            # テーマを分類して表示
            themes_by_category = {
                "内科系": ["多発性骨髄腫", "急性腎不全", "ネフローゼ症候群", "慢性骨髄性白血病", "再生不良性貧血", "COPD", "C型肝炎", "プロラクチノーマ"],
                "外科・外傷系": ["胆石性閉塞性胆管炎", "下肢閉塞性動脈硬化症", "マルファン症候群", "乳癌", "心臓粘液腫"],
                "小児・産婦人科": ["川崎病", "神経発達障害", "新生児マススクリーニング", "双体妊娠"],
                "整形・循環器他": ["大腿骨頸部骨折", "大腿骨頭置換術", "心筋梗塞", "不整脈", "敗血症性ショック", "糖尿病性ケトアシドース"]
            }
            
            for category, themes in themes_by_category.items():
                st.markdown(f"**{category}**")
                cols = st.columns(4)
                for i, theme in enumerate(themes):
                    if theme in default_themes:  # 存在確認
                        with cols[i % 4]:
                            # 最近使用したテーマかどうかの表示
                            recently_used = is_theme_recently_used("自由記述", theme, 5)
                            theme_history = get_theme_history("自由記述", theme)
                            
                            # ボタンの表示テキストとスタイル
                            button_text = theme
                            if recently_used:
                                button_text += " 🔄"
                            elif theme_history:
                                button_text += f" 📊({len(theme_history)}回)"
                            
                            button_type = "secondary" if recently_used else "primary"
                            
                            if st.button(button_text, use_container_width=True, key=f"theme_{theme}", type=button_type):
                                if recently_used:
                                    # 最近使用したテーマの場合は確認状態にセット
                                    st.session_state.pending_theme_confirmation = theme
                                    st.rerun()
                                else:
                                    s['theme'] = theme
                                    save_recent_theme(theme)
                                    s['step'] = 'generating_question'
                                    st.rerun()
                st.markdown("")  # 間隔追加

        st.markdown("<hr>", unsafe_allow_html=True)

        # カスタムテーマ入力
        st.markdown("**自由に対策したいテーマを入力:**")
        custom_theme = st.text_input("（例：間質性肺炎、脳梗塞）", key="custom_theme_input")
        
        if custom_theme:
            # カスタムテーマの履歴チェック
            custom_recently_used = is_theme_recently_used("自由記述", custom_theme, 5)
            custom_history = get_theme_history("自由記述", custom_theme)
            
            warning_text = ""
            if custom_recently_used:
                warning_text = " ⚠️ 最近練習済み"
            elif custom_history:
                warning_text = f" 📊 過去{len(custom_history)}回実施"
        
        button_label = "このテーマで医学部採用試験形式の問題を作成"
        if custom_theme and custom_recently_used:
            button_label += " (過去5回以内に練習済み)"
            
        if st.button(button_label, type="primary", disabled=not custom_theme):
            s['theme'] = custom_theme
            save_recent_theme(custom_theme)
            s['step'] = 'generating_question'
            st.rerun()

def render_question_generation():
    """問題生成中のスピナーを表示"""
    with st.spinner(f"「{s['theme']}」で医学部採用試験形式の問題を生成中..."):
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
    st.header(f"📝 医学部採用試験 自由記述問題")
    st.subheader(f"テーマ: {s['theme']}")
    
    # 問題タイプの判定と表示
    question_type = "基本知識型"
    if "小学6年生" in s['question'] or "説明書" in s['question']:
        question_type = "患者説明型"
    elif "assessment" in s['question'] and "plan" in s['question']:
        question_type = "臨床評価型"
    elif "鑑別" in s['question']:
        question_type = "鑑別診断型"
    elif "診察" in s['question'] or "検査" in s['question']:
        question_type = "診察・検査型"
    elif "治療方針" in s['question'] or "治療計画" in s['question']:
        question_type = "治療計画型"
    elif "診断基準" in s['question']:
        question_type = "診断基準型"
    elif "合併症" in s['question']:
        question_type = "合併症型"
    
    st.info(f"🎯 **問題形式**: {question_type}")
    
    with st.container(border=True):
        st.subheader("問題")
        st.markdown(f"**{s['question']}**")

    st.subheader("あなたの回答")
    
    # 問題タイプに応じたヒント
    hint_text = ""
    if question_type == "患者説明型":
        hint_text = "💡 専門用語を避け、分かりやすい言葉で説明してください"
    elif question_type == "臨床評価型":
        hint_text = "💡 assessment（現状評価）とplan（計画）を明確に分けて記述してください"
    elif question_type == "鑑別診断型":
        hint_text = "💡 鑑別疾患を列挙し、それぞれを除外するための検査を記述してください"
    elif question_type == "診察・検査型":
        hint_text = "💡 系統的な診察手順と、必要な検査を優先順位をつけて記述してください"
    elif question_type == "治療計画型":
        hint_text = "💡 薬物療法、非薬物療法、患者教育を含めて包括的に記述してください"
    else:
        hint_text = "💡 病態生理、症状、検査、治療を体系的に記述してください"
    
    if hint_text:
        st.caption(hint_text)

    s['answer'] = st.text_area(
        "ここに回答を入力してください...",
        height=400,
        value=s.get('answer', ''),
        help="医学部採用試験レベルの実践的な知識で回答してください"
    )
    
    # 文字数表示
    char_count = len(s['answer'])
    st.caption(f"入力文字数: {char_count}文字")
    
    # 文字数による評価
    if char_count >= 300:
        st.success("✅ 充分な分量です")
    elif char_count >= 150:
        st.warning("⚠️ もう少し詳しく記述してください")
    elif char_count >= 50:
        st.info("💭 基本的な内容は記述されています")
    elif char_count > 0:
        st.error("❌ 内容が不足しています")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("回答を提出して医学部採用試験基準で採点", type="primary", disabled=len(s['answer']) < 20):
            s['step'] = 'scoring'
            st.rerun()
    
    with col2:
        if st.button("テーマ選択に戻る"):
            s['step'] = 'theme_selection'
            initialize_session() # 状態をリセット
            st.rerun()

def render_scoring_and_feedback():
    """採点とフィードバック表示画面"""
    st.header("📊 医学部採用試験基準での評価")

    with st.spinner("医学部採用試験の採点委員が評価中..."):
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
        # 所要時間の計算
        completion_time = datetime.now()
        start_time = s.get('start_time', completion_time)
        duration_seconds = (completion_time - start_time).total_seconds()
        duration_minutes = int(duration_seconds // 60)
        duration_seconds_remainder = int(duration_seconds % 60)
        
        history_data = {
            "type": "医学部採用試験 自由記述",
            "date": s['start_time'].isoformat(),
            "duration_seconds": duration_seconds,
            "duration_display": f"{duration_minutes}分{duration_seconds_remainder}秒",
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
        
        # セッション状態にテーマ履歴を更新
        save_recent_theme(s['theme'])
        
    except Exception as e:
        st.error(f"履歴の保存中にエラーが発生しました: {e}")

    s['step'] = 'completed'
    st.rerun()

def render_completed_screen():
    """完了画面を表示"""
    st.header("🎉 医学部採用試験基準での評価完了")
    
    with st.container(border=True):
        st.markdown(s['feedback'])

    # 進歩比較の表示
    if s.get('theme'):
        theme_history = get_theme_history("自由記述", s['theme'])
        if theme_history:
            render_progress_comparison(s['theme'], theme_history)

    st.success("お疲れ様でした！医学部採用試験レベルでの学習が完了しました。")
    
    # 次の練習のための推奨テーマ表示
    if s.get('theme'):
        st.markdown("---")
        st.markdown("### 🚀 次の練習におすすめ")
        
        # 最近使用していないテーマを推奨
        default_themes = get_default_themes()
        recent_themes = get_recent_themes("自由記述", 5)
        recommended_themes = [theme for theme in default_themes if theme not in recent_themes]
        
        if recommended_themes:
            st.markdown("**最近練習していない医学部頻出テーマ:**")
            rec_cols = st.columns(min(4, len(recommended_themes)))
            for i, rec_theme in enumerate(recommended_themes[:4]):
                with rec_cols[i]:
                    if st.button(f"📚 {rec_theme}", use_container_width=True):
                        s['theme'] = rec_theme
                        save_recent_theme(rec_theme)
                        s['step'] = 'generating_question'
                        s['answer'] = ""
                        s['feedback'] = None
                        st.rerun()
        else:
            st.info("すべての頻出テーマを最近練習済みです。ランダムテーマをお試しください。")
    
    if st.button("新しい医学部採用試験問題に挑戦", type="primary"):
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