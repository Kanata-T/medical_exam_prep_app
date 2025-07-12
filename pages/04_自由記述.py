import streamlit as st
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os

# パス設定（ページを直接実行した場合の対応）
try:
    from modules.medical_knowledge_checker import (
        generate_medical_question,
        score_medical_answer_stream,
        get_default_themes,
        generate_random_medical_theme
    )
    from modules.utils import extract_scores, save_history, auto_save_session
    from modules.session_manager import StreamlitSessionManager
    from modules.database_adapter import DatabaseAdapter
except ImportError:
    # モジュールが見つからない場合、親ディレクトリをパスに追加
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from modules.medical_knowledge_checker import (
        generate_medical_question,
        score_medical_answer_stream,
        get_default_themes,
        generate_random_medical_theme
    )
    from modules.utils import extract_scores, save_history, auto_save_session
    from modules.session_manager import StreamlitSessionManager
    from modules.database_adapter import DatabaseAdapter

# Google AI APIキーの確認
try:
    from modules.utils import check_api_configuration, show_api_setup_guide
except ImportError:
    def check_api_configuration():
        return False, "API設定モジュールが見つかりません"
    def show_api_setup_guide():
        st.error("API設定ガイドが利用できません")

st.set_page_config(
    page_title="医学部採用試験 自由記述対策",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
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
        if current_session.is_authenticated:
            st.sidebar.success(f"🔐 認証済み: {current_session.identification_method.value}")
        else:
            st.sidebar.info(f"🔐 セッション: {current_session.identification_method.value}")
        
    except Exception as e:
        st.sidebar.error(f"セッション初期化エラー: {e}")
        st.session_state.session_initialized = False

# データベースアダプター初期化
try:
    db_adapter = DatabaseAdapter()
    database_available = db_adapter.is_available()
except Exception as e:
    st.error(f"データベース初期化エラー: {e}")
    database_available = False
    db_adapter = None

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

# --- ヘッダー ---
st.title("✍️ 医学部採用試験 自由記述対策")

# 自動セッション保存
auto_save_session()

# --- 履歴データの処理（新システム使用） ---
@st.cache_data(ttl=300, show_spinner=False)
def load_and_process_free_writing_history():
    """自由記述の履歴データを読み込んで処理（新システム）"""
    if not database_available:
        return []
    
    try:
        return db_adapter.load_practice_history('free_writing')
    except Exception as e:
        st.error(f"履歴データの読み込みエラー: {e}")
        return []

@st.cache_data(ttl=300, show_spinner=False)
def get_themes_with_stats():
    """テーマ別の統計情報を取得（新システム）"""
    history = load_and_process_free_writing_history()
    if not history:
        return {}
    
    themes_stats = {}
    for item in history:
        inputs = item.get('inputs', {})
        theme = inputs.get('theme', '不明')
        
        if theme not in themes_stats:
            themes_stats[theme] = {
                'count': 0,
                'scores': [],
                'dates': [],
                'last_date': None,
                'avg_score': 0,
                'latest_feedback': ''
            }
        
        themes_stats[theme]['count'] += 1
        themes_stats[theme]['dates'].append(item.get('date', ''))
        
        # スコア情報
        scores = item.get('scores', {})
        if scores:
            avg_score = sum(scores.values()) / len(scores)
            themes_stats[theme]['scores'].append(avg_score)
        
        # 最新の学習日時
        date_str = item.get('date', '')
        if not themes_stats[theme]['last_date'] or date_str > themes_stats[theme]['last_date']:
            themes_stats[theme]['last_date'] = date_str
            themes_stats[theme]['latest_feedback'] = item.get('feedback', '')
    
    # 平均スコアを計算
    for theme_data in themes_stats.values():
        if theme_data['scores']:
            theme_data['avg_score'] = sum(theme_data['scores']) / len(theme_data['scores'])
    
    return themes_stats

# 履歴関連のヘルパー関数（新システム）
def get_recent_themes_local(limit: int = 5) -> list:
    """最近のテーマを履歴から取得"""
    history = load_and_process_free_writing_history()
    recent_themes = []
    
    for item in history:
        inputs = item.get('inputs', {})
        theme = inputs.get('theme')
        if theme and theme not in recent_themes:
            recent_themes.append(theme)
            if len(recent_themes) >= limit:
                break
    
    return recent_themes

def get_theme_history_local(theme: str) -> list:
    """特定テーマの履歴を取得"""
    history = load_and_process_free_writing_history()
    return [item for item in history if item.get('inputs', {}).get('theme') == theme]

def is_theme_recently_used_local(theme: str, recent_limit: int = 3) -> bool:
    """テーマが最近使用されたかチェック"""
    recent_themes = get_recent_themes_local(recent_limit)
    return theme in recent_themes

def save_recent_theme(theme: str):
    """最近のテーマを保存（新システムでは履歴システムが自動処理）"""
    # 新システムでは履歴保存時に自動的に記録されるため、特別な処理は不要
    pass

def render_progress_comparison(theme: str, theme_history: list):
    """進歩比較の表示"""
    if len(theme_history) < 2:
        return
    
    st.markdown("---")
    st.markdown("### 📈 進歩の軌跡")
    
    scores = []
    dates = []
    
    for item in theme_history:
        item_scores = item.get('scores', {})
        if item_scores:
            avg_score = sum(item_scores.values()) / len(item_scores)
            scores.append(avg_score)
            try:
                date = datetime.fromisoformat(item['date']).date()
                dates.append(date)
            except (ValueError, TypeError, KeyError):
                dates.append(datetime.now().date())
    
    if len(scores) >= 2:
        fig = px.line(
            x=dates,
            y=scores,
            title=f"「{theme}」のスコア推移",
            labels={'x': '練習日', 'y': 'スコア'}
        )
        fig.update_traces(line=dict(width=3, color='#667eea'))
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            yaxis=dict(range=[0, 10.5])
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 改善度表示
        if len(scores) >= 2:
            improvement = scores[-1] - scores[0]
            if improvement > 0:
                st.success(f"📈 初回から+{improvement:.1f}ポイント向上しました！")
            elif improvement == 0:
                st.info("📊 スコアは横ばいです。さらなる向上を目指しましょう。")
            else:
                st.warning(f"📉 前回より{abs(improvement):.1f}ポイント下がりました。復習をおすすめします。")

# --- UIコンポーネント ---
def render_theme_selection():
    """テーマ選択画面を表示"""
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
    recent_themes = get_recent_themes_local(5)
    
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
                    recent_themes = get_recent_themes_local(5)
                    
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
                "循環器系": ["心筋梗塞", "不整脈", "心房細動", "狭心症", "大動脈解離", "心サルコイドーシス", "心アミロイドーシス", "重症大動脈弁狭窄症"],
                "内分泌・代謝": ["糖尿病の診断基準", "糖尿病の三大合併症", "糖尿病性ケトアシドース", "Cushing症候群", "甲状腺機能亢進症", "ステロイドの副作用"],
                "血液・腎臓": ["多発性骨髄腫", "慢性骨髄性白血病", "急性骨髄性白血病", "悪性リンパ腫", "再生不良性貧血", "急性腎不全", "ネフローゼ症候群"],
                "呼吸器・消化器": ["COPD", "Pancoast症候群", "肺癌の治療", "誤嚥性肺炎", "C型肝炎", "胆石性閉塞性胆管炎", "ヘリコバクターピロリ感染"],
                "外科・整形": ["下肢閉塞性動脈硬化症", "マルファン症候群", "交通外傷", "乳癌", "橈骨遠位端骨折", "変形性膝関節症", "高齢者の骨折"],
                "産婦人科・小児": ["母子感染症", "子宮内膜症", "稽留流産", "切迫早産", "川崎病", "小児の解熱薬使用", "熱性けいれん"],
                "救急・麻酔": ["敗血症性ショック", "突然の腹痛", "胸痛の鑑別疾患", "アナフィラキシー", "BLS", "全身麻酔"]
            }
            
            for category, themes in themes_by_category.items():
                st.markdown(f"**{category}**")
                # カテゴリ内のテーマ数に応じてcolumns数を調整（最大4列）
                num_cols = min(4, len([t for t in themes if t in default_themes]))
                if num_cols > 0:
                    cols = st.columns(num_cols)
                    col_idx = 0
                    for theme in themes:
                        if theme in default_themes:  # 存在確認
                            with cols[col_idx % num_cols]:
                                # 最近使用したテーマかどうかの表示（ローカル関数を使用）
                                recently_used = is_theme_recently_used_local(theme, 5)
                                theme_history = get_theme_history_local(theme)
                                
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
                            col_idx += 1
                st.markdown("")  # 間隔追加

        st.markdown("<hr>", unsafe_allow_html=True)

        # カスタムテーマ入力
        st.markdown("**自由に対策したいテーマを入力:**")
        custom_theme = st.text_input("（例：間質性肺炎、脳梗塞）", key="custom_theme_input")
        
        if custom_theme:
            # カスタムテーマの履歴チェック（ローカル関数を使用）
            custom_recently_used = is_theme_recently_used_local(custom_theme, 5)
            custom_history = get_theme_history_local(custom_theme)
            
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
    st.subheader(f"📝 テーマ: {s['theme']}")
    
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
    st.subheader("📊 医学部採用試験基準での評価")

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
            "type": "free_writing",
            "date": completion_time.isoformat(),
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
        
        filename = save_history(history_data)
        if filename:
            st.success("今回の学習内容を履歴に保存しました。")
        else:
            st.warning("履歴の保存で問題が発生しましたが、セッションには記録されています。")
        
        # セッション状態にテーマ履歴を更新
        save_recent_theme(s['theme'])
        
    except Exception as e:
        st.error(f"履歴の保存中にエラーが発生しました: {e}")

    s['step'] = 'completed'
    st.rerun()

def render_completed_screen():
    """完了画面を表示"""
    st.subheader("🎉 医学部採用試験基準での評価完了")
    
    with st.container(border=True):
        st.markdown(s['feedback'])

    # 進歩比較の表示（ローカル関数を使用）
    if s.get('theme'):
        theme_history = get_theme_history_local(s['theme'])
        if theme_history:
            render_progress_comparison(s['theme'], theme_history)

    st.success("お疲れ様でした！医学部採用試験レベルでの学習が完了しました。")
    
    # 次の練習のための推奨テーマ表示
    if s.get('theme'):
        st.markdown("---")
        st.markdown("### 🚀 次の練習におすすめ")
        
        # 最近使用していないテーマを推奨（ローカル関数を使用）
        default_themes = get_default_themes()
        recent_themes = get_recent_themes_local(5)
        recommended_themes = [theme for theme in default_themes if theme not in recent_themes]
        
        if recommended_themes:
            st.markdown("**最近練習していない医学部頻出テーマ:**")
            rec_cols = st.columns(min(4, len(recommended_themes)))
            for i, rec_theme in enumerate(recommended_themes[:4]):
                with rec_cols[i]:
                    if st.button(f"📚 {rec_theme}", use_container_width=True, key=f"recommend_{rec_theme}"):
                        # 状態を完全にリセットしてから新しいテーマを設定
                        s['theme'] = rec_theme
                        save_recent_theme(rec_theme)
                        s['step'] = 'generating_question'
                        s['answer'] = ""
                        s['feedback'] = None
                        s['question'] = ""
                        s['start_time'] = None
                        # 確認状態もリセット
                        if 'pending_theme_confirmation' in st.session_state:
                            st.session_state.pending_theme_confirmation = None
                        st.rerun()
        else:
            st.info("すべての頻出テーマを最近練習済みです。ランダムテーマをお試しください。")
    
    if st.button("新しい医学部採用試験問題に挑戦", type="primary"):
        # セッション状態を完全にリセット
        s['step'] = 'theme_selection'
        s['theme'] = ""
        s['question'] = ""
        s['answer'] = ""
        s['feedback'] = None
        s['start_time'] = None
        # 確認状態もリセット
        if 'pending_theme_confirmation' in st.session_state:
            st.session_state.pending_theme_confirmation = None
        st.rerun()

# --- 履歴表示のUIコンポーネント ---
def render_history_overview():
    """履歴概要を表示"""
    st.markdown("これまでの自由記述練習の履歴を確認できます。")
    
    # データベース状況とコントロール
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # データベース接続状況を表示
        try:
            if database_available:
                st.success(f"🌐 **データベース接続**: 正常 (ID: {st.session_state.current_session.session_id[:8]}...)")
                if db_adapter.get_database_status().get('database_records'):
                    st.caption(f"📊 データベース内履歴: {db_adapter.get_database_status()['database_records']}件")
            else:
                st.warning("⚠️ **データベース接続**: オフライン")
                if db_adapter.get_database_status().get('offline_records'):
                    st.caption(f"📱 オフライン履歴: {db_adapter.get_database_status()['offline_records']}件")
                    
        except Exception:
            st.info("📱 **履歴保存**: ローカルファイル使用")
    
    with col2:
        if st.button("🔄 履歴更新", help="履歴データを最新の状態に更新します"):
            # キャッシュクリアのみ行い、自動再読み込みを待つ
            st.cache_data.clear()
            st.success("💫 履歴データを更新しました！")
    
    with col3:
        # 履歴エクスポートボタン
        if database_available:
            if st.button("💾 履歴保存", help="履歴をJSONファイルとして保存"):
                try:
                    export_data = db_adapter.export_history('free_writing')
                    st.download_button(
                        label="📥 履歴ダウンロード",
                        data=export_data,
                        file_name=f"自由記述履歴_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                except Exception as e:
                    st.error(f"履歴エクスポートエラー: {e}")
    
    # 履歴とテーマ統計を一度に取得（重複を防止）
    history = load_and_process_free_writing_history()
    if not history:
        st.info("📝 まだ自由記述の履歴がありません。新しい練習タブで練習を始めてください。")
        return
    
    themes_stats = get_themes_with_stats()
    
    # 統計サマリー
    st.subheader("📊 学習サマリー")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("総練習回数", len(history))
    
    with col2:
        st.metric("練習したテーマ数", len(themes_stats))
    
    with col3:
        if themes_stats:
            all_scores = []
            for stats in themes_stats.values():
                all_scores.extend(stats['scores'])
            avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
            st.metric("平均スコア", f"{avg_score:.1f}")
        else:
            st.metric("平均スコア", "N/A")
    
    with col4:
        # 今月の練習回数
        current_month = datetime.now().strftime('%Y-%m')
        this_month_count = sum(1 for item in history if item.get('date', '').startswith(current_month))
        st.metric("今月の練習", f"{this_month_count}回")

def render_theme_history():
    """テーマ別履歴を表示"""
    st.subheader("🎯 テーマ別学習履歴")
    
    themes_stats = get_themes_with_stats()
    if not themes_stats:
        st.info("まだテーマ別の履歴がありません。")
        return
    
    # テーマ選択
    theme_options = list(themes_stats.keys())
    theme_options.sort(key=lambda x: themes_stats[x]['last_date'], reverse=True)
    
    selected_theme = st.selectbox(
        "📋 テーマを選択",
        theme_options,
        format_func=lambda x: f"{x} ({themes_stats[x]['count']}回練習, 平均スコア: {themes_stats[x]['avg_score']:.1f})",
        key="theme_history_selector"
    )
    
    if selected_theme:
        render_theme_detail(selected_theme, themes_stats[selected_theme])

def render_theme_detail(theme, stats):
    """選択されたテーマの詳細履歴を表示"""
    st.markdown(f"### 📖 テーマ: {theme}")
    
    # 基本統計
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("練習回数", stats['count'])
    with col2:
        st.metric("平均スコア", f"{stats['avg_score']:.1f}" if stats['avg_score'] > 0 else "N/A")
    with col3:
        try:
            last_date = datetime.fromisoformat(stats['last_date']).strftime('%Y年%m月%d日') if stats['last_date'] else "不明"
        except (ValueError, TypeError):
            last_date = "不明"
        st.metric("最後の練習", last_date)
    
    # スコア推移グラフ
    if len(stats['scores']) > 1:
        st.markdown("#### 📈 スコア推移")
        try:
            # 日付のパースを安全に行う
            dates = []
            for date in stats['dates'][:len(stats['scores'])]:
                try:
                    dates.append(datetime.fromisoformat(date).date())
                except (ValueError, TypeError):
                    # パースできない日付は現在日時を使用
                    dates.append(datetime.now().date())
            
            fig = px.line(
                x=dates,
                y=stats['scores'],
                title=f"「{theme}」のスコア推移",
                labels={'x': '練習日', 'y': 'スコア'}
            )
            fig.update_traces(line=dict(width=3, color='#667eea'))
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(range=[0, 10.5])
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"グラフの表示中にエラーが発生しました: {e}")
            st.info("スコア推移グラフを表示できませんでした。")
    
    # 詳細履歴（再度の履歴取得を避けるため、すでに取得済みのデータを使用）
    st.markdown("#### 📝 練習履歴詳細")
    history = load_and_process_free_writing_history()
    theme_history = [item for item in history if item.get('inputs', {}).get('theme') == theme]
    
    for i, item in enumerate(theme_history):
        try:
            date = datetime.fromisoformat(item['date']).strftime('%Y年%m月%d日 %H:%M')
        except (ValueError, TypeError, KeyError):
            date = "日時不明"
        duration = item.get('duration_display', '未記録')
        
        with st.expander(f"📅 {date} ({duration})", expanded=i==0):
            # 問題
            question = item.get('inputs', {}).get('question', '問題が記録されていません')
            st.markdown("**出題された問題:**")
            st.markdown(f"> {question}")
            
            # 回答
            answer = item.get('inputs', {}).get('answer', '回答が記録されていません')
            st.markdown("**あなたの回答:**")
            with st.container(border=True):
                st.markdown(answer)
            
            # スコア
            scores = item.get('scores', {})
            if scores:
                st.markdown("**評価スコア:**")
                score_cols = st.columns(len(scores))
                for j, (category, score) in enumerate(scores.items()):
                    with score_cols[j]:
                        st.metric(category, f"{score}/10")
            
            # フィードバック
            feedback = item.get('feedback', '')
            if feedback:
                st.markdown("**詳細評価:**")
                st.markdown(feedback)

def render_recent_activity():
    """最近の活動を表示"""
    st.subheader("🕒 最近の活動")
    
    history = load_and_process_free_writing_history()
    if not history:
        st.info("最近の活動はありません。")
        return
    
    # 最新5件を表示
    recent_items = history[:5]
    
    for item in recent_items:
        try:
            date = datetime.fromisoformat(item['date']).strftime('%Y年%m月%d日 %H:%M')
        except (ValueError, TypeError, KeyError):
            date = "日時不明"
        theme = item.get('inputs', {}).get('theme', '不明')
        duration = item.get('duration_display', '未記録')
        
        # スコアの計算
        scores = item.get('scores', {})
        avg_score = sum(scores.values()) / len(scores) if scores else 0
        score_text = f"平均スコア: {avg_score:.1f}" if avg_score > 0 else "スコア未記録"
        
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                st.markdown(f"**{theme}**")
                st.caption(f"📅 {date}")
            with col2:
                st.markdown(f"⏱️ {duration}")
                st.caption("所要時間")
            with col3:
                st.markdown(f"📊 {score_text}")
                if avg_score >= 8:
                    st.caption("🌟 優秀")
                elif avg_score >= 6:
                    st.caption("👍 良好")
                elif avg_score > 0:
                    st.caption("📈 要改善")

# --- メインロジック ---
def main():
    st.header("✍️ 医学部採用試験 自由記述対策")
    
    # タブの作成
    tab1, tab2 = st.tabs(["🆕 新しい練習", "📚 履歴"])
    
    with tab1:
        # 既存のメインフロー
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
    
    with tab2:
        # 履歴表示
        render_history_overview()
        
        st.markdown("---")
        
        # タブで履歴の詳細を分ける
        history_tab1, history_tab2 = st.tabs(["🎯 テーマ別履歴", "🕒 最近の活動"])
        
        with history_tab1:
            render_theme_history()
        
        with history_tab2:
            render_recent_activity()

if __name__ == "__main__":
    main()
    auto_save_session()

# サイドバー（統一されたセッション管理システム）
with st.sidebar:
    st.markdown("### 自由記述対策")
    
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
    
    # 現在の状況表示
    if s['step'] != 'theme_selection':
        step_names = {
            'generating_question': 'ステップ2: 問題生成中',
            'answering': 'ステップ3: 回答入力',
            'scoring': 'ステップ4: AI採点中',
            'completed': '完了'
        }
        current_step = step_names.get(s['step'], 'N/A')
        st.markdown(f"**現在のステップ:** {current_step}")
        
        if s['theme']:
            st.markdown(f"**テーマ:** {s['theme']}")
    
    st.markdown("---")
    
    # 評価ポイント
    with st.expander("📊 評価ポイント"):
        st.markdown("""
        - **医学知識**: 正確性・深度
        - **臨床応用**: 実践的な思考力
        - **論理構成**: 体系的な記述
        - **患者安全**: 安全への配慮
        """)
    
    st.markdown("---")
    
    if st.button("🔄 セッションをリセット", use_container_width=True):
        s['step'] = 'theme_selection'
        s['theme'] = ""
        s['question'] = ""
        s['answer'] = ""
        s['feedback'] = None
        s['start_time'] = None
        st.rerun()