import streamlit as st
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from modules.user_auth import (
    get_user_auth_manager, UserProfile, UserSettings, LoginResult, 
    UserAchievement, AccountStatus
)
from modules.utils import auto_save_session
from modules.session_manager import StreamlitSessionManager, SessionPersistence
import os
from modules.database_adapter_v3 import DatabaseAdapterV3
import logging

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="ユーザー管理",
    page_icon="👤",
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
    .auth-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 2rem;
        margin: 1rem 0;
    }
    .profile-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 2rem;
        color: white;
        margin-bottom: 2rem;
    }
    .stats-card {
        background-color: #ffffff;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .achievement-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        margin: 0.25rem;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        text-align: center;
    }
    .setting-group {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    .success-message {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        color: #155724;
        margin: 1rem 0;
    }
    .error-message {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        color: #721c24;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'auth_mode' not in st.session_state:
    st.session_state.auth_mode = 'login'  # 'login', 'register', 'profile', 'settings'
if 'user_authenticated' not in st.session_state:
    st.session_state.user_authenticated = False
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = None
if 'auth_token' not in st.session_state:
    st.session_state.auth_token = None

# 自動保存
auto_save_session()

# UserAuthManagerの取得
auth_manager = get_user_auth_manager()
if not auth_manager:
    st.error("ユーザー管理機能が利用できません。データベース接続を確認してください。")
    st.stop()

# セッション管理の初期化
session_manager = StreamlitSessionManager()

def restore_auth_state():
    """認証状態を復元"""
    try:
        # 1. URLパラメータからセッショントークンを確認
        session_token = st.query_params.get('session_token', None)
        if session_token:
            session_data = SessionPersistence.load_session_from_token(session_token)
            if session_data and session_data.get('is_authenticated', False):
                user_profile = session_data.get('user_profile')
                if user_profile:
                    st.session_state.user_authenticated = True
                    st.session_state.user_profile = user_profile
                    st.session_state.auth_token = session_token
                    logger.info(f"認証状態をURLパラメータから復元: {user_profile.get('display_name', 'Unknown')}")
                    return True
        
        # 2. セッション状態から認証トークンを確認
        if 'current_auth_token' in st.session_state:
            auth_token = st.session_state.current_auth_token
            auth_data = SessionPersistence.load_auth_from_token(auth_token)
            if auth_data and auth_data.get('is_authenticated', False):
                st.session_state.user_authenticated = True
                st.session_state.user_profile = auth_data.get('user_profile')
                st.session_state.auth_token = auth_token
                logger.info(f"認証状態をセッションから復元: {auth_data.get('user_profile', {}).get('display_name', 'Unknown')}")
                return True
        
        # 3. 既存のセッション状態を確認
        if 'user_authenticated' in st.session_state and st.session_state.user_authenticated:
            if 'user_profile' in st.session_state and st.session_state.user_profile:
                user_profile = st.session_state.user_profile
                if hasattr(user_profile, 'display_name'):
                    logger.info(f"既存の認証状態を確認: {user_profile.display_name}")
                else:
                    logger.info("既存の認証状態を確認: Unknown")
                return True
        
        logger.info("認証状態の復元に失敗")
        return False
    except Exception as e:
        logger.error(f"認証状態の復元中にエラーが発生しました: {e}")
        return False

def save_auth_state(user_profile: UserProfile):
    """認証状態を保存"""
    try:
        # UserProfileオブジェクトをJSON化可能な辞書に変換
        profile_dict = {
            'user_id': user_profile.user_id,
            'email': user_profile.email,
            'display_name': user_profile.display_name,
            'first_name': user_profile.first_name,
            'last_name': user_profile.last_name,
            'avatar_url': user_profile.avatar_url,
            'bio': user_profile.bio,
            'timezone': user_profile.timezone,
            'language': user_profile.language,
            'email_verified': user_profile.email_verified,
            'account_status': user_profile.account_status,
            'created_at': user_profile.created_at.isoformat() if user_profile.created_at else None,
            'last_active': user_profile.last_active.isoformat() if user_profile.last_active else None,
            'last_login': user_profile.last_login.isoformat() if user_profile.last_login else None
        }
        
        # セッショントークンを生成・保存
        session_data = {
            'user_profile': profile_dict,
            'is_authenticated': True,
            'login_time': datetime.now().isoformat()
        }
        
        session_token = SessionPersistence.save_session_token(
            user_profile.user_id, session_data
        )
        
        # 認証トークンも生成・保存
        auth_token = SessionPersistence.save_auth_token(
            user_profile.user_id, profile_dict
        )
        
        # セッション状態を設定
        st.session_state.auth_token = session_token
        st.session_state.user_authenticated = True
        st.session_state.user_profile = user_profile
        st.session_state.current_auth_token = auth_token
        
        # URLパラメータにセッショントークンを設定
        try:
            st.query_params['session_token'] = session_token
        except:
            pass  # URL更新が失敗しても継続
        
        logger.info(f"認証状態を保存: {user_profile.display_name}")
        return True
    except Exception as e:
        logger.error(f"認証状態の保存中にエラーが発生しました: {e}")
        return False

def clear_auth_state():
    """認証状態をクリア"""
    try:
        # セッション状態をクリア
        session_keys_to_clear = [
            'user_profile', 'user_authenticated', 'auth_token', 'current_auth_token'
        ]
        
        for key in session_keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
        # セッショントークン辞書もクリア
        if 'session_tokens' in st.session_state:
            del st.session_state.session_tokens
        
        if 'auth_tokens' in st.session_state:
            del st.session_state.auth_tokens
        
        # URLパラメータからセッショントークンを削除
        try:
            if 'session_token' in st.query_params:
                del st.query_params['session_token']
        except:
            pass  # URL更新が失敗しても継続
        
        logger.info("認証状態をクリアしました")
        return True
    except Exception as e:
        logger.error(f"認証状態のクリア中にエラーが発生しました: {e}")
        return False

# ページ読み込み時に認証状態を復元
if 'user_authenticated' not in st.session_state:
    st.session_state.user_authenticated = False

# 認証状態の復元を確実に実行
if not st.session_state.user_authenticated:
    restore_auth_state()

# デバッグ用：認証状態を表示
if st.session_state.get('user_authenticated'):
    user_profile = st.session_state.get('user_profile')
    if user_profile and hasattr(user_profile, 'display_name'):
        st.sidebar.success(f"✅ ログイン中: {user_profile.display_name}")
    else:
        st.sidebar.success("✅ ログイン中: Unknown")
else:
    st.sidebar.info("🔐 未ログイン")

# タイトル
st.markdown('<h1 class="main-header">👤 ユーザー管理</h1>', unsafe_allow_html=True)

def show_login_form():
    """ログインフォーム表示"""
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    st.markdown("### 🔐 ログイン")
    
    with st.form("login_form"):
        email = st.text_input("メールアドレス", placeholder="your@email.com")
        password = st.text_input("パスワード", type="password")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            login_clicked = st.form_submit_button("ログイン", type="primary", use_container_width=True)
        
        with col2:
            if st.form_submit_button("新規登録", use_container_width=True):
                st.session_state.auth_mode = 'register'
                st.rerun()
        
        with col3:
            if st.form_submit_button("パスワードを忘れた", use_container_width=True):
                st.session_state.auth_mode = 'reset_password'
                st.rerun()
    
    if login_clicked:
        if not email or not password:
            st.error("メールアドレスとパスワードを入力してください。")
        else:
            with st.spinner("ログイン中..."):
                login_result, user_profile, message = auth_manager.login_user(email, password)
                
                if login_result == LoginResult.SUCCESS and user_profile:
                    # 認証状態を保存
                    if save_auth_state(user_profile):
                        st.session_state.auth_mode = 'profile'
                        st.success(message)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("ログイン状態の保存に失敗しました。")
                else:
                    st.error(message)
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_register_form():
    """ユーザー登録フォーム表示"""
    st.markdown('<div class="auth-card">', unsafe_allow_html=True)
    st.markdown("### 📝 新規ユーザー登録")
    
    with st.form("register_form"):
        email = st.text_input("メールアドレス *", placeholder="your@email.com")
        
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("名前", placeholder="太郎")
        with col2:
            last_name = st.text_input("姓", placeholder="田中")
        
        display_name = st.text_input("表示名 *", placeholder="田中太郎", 
                                   value=f"{last_name} {first_name}" if first_name and last_name else "")
        
        password = st.text_input("パスワード *", type="password", 
                                help="8文字以上、大文字・小文字・数字・特殊文字を含む")
        password_confirm = st.text_input("パスワード確認 *", type="password")
        
        terms_accepted = st.checkbox("利用規約とプライバシーポリシーに同意します", value=False)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            register_clicked = st.form_submit_button("登録", type="primary", use_container_width=True)
        
        with col2:
            if st.form_submit_button("ログインに戻る", use_container_width=True):
                st.session_state.auth_mode = 'login'
                st.rerun()
    
    if register_clicked:
        errors = []
        
        if not email or not display_name or not password:
            errors.append("必須項目を入力してください")
        
        if password != password_confirm:
            errors.append("パスワードが一致しません")
        
        if not terms_accepted:
            errors.append("利用規約に同意してください")
        
        if errors:
            for error in errors:
                st.error(error)
        else:
            with st.spinner("ユーザー登録中..."):
                success, message, user_id = auth_manager.register_user(
                    email, password, display_name, first_name, last_name
                )
                
                if success:
                    st.success(message)
                    st.info("登録が完了しました。ログインしてください。")
                    time.sleep(2)
                    st.session_state.auth_mode = 'login'
                    st.rerun()
                else:
                    st.error(message)
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_user_profile():
    """ユーザープロフィール表示"""
    user_profile = st.session_state.user_profile
    
    if not user_profile:
        st.error("ユーザー情報を取得できません。")
        return
    
    # プロフィールカード
    st.markdown('<div class="profile-card">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        if user_profile.avatar_url:
            st.image(user_profile.avatar_url, width=100)
        else:
            st.markdown("### 👤")
    
    with col2:
        st.markdown(f"### {user_profile.display_name}")
        st.markdown(f"**メール**: {user_profile.email}")
        
        if user_profile.first_name or user_profile.last_name:
            full_name = f"{user_profile.last_name or ''} {user_profile.first_name or ''}".strip()
            st.markdown(f"**氏名**: {full_name}")
        
        if user_profile.bio:
            st.markdown(f"**自己紹介**: {user_profile.bio}")
        
        # ステータス表示
        status_color = {"active": "🟢", "inactive": "🟡", "suspended": "🔴"}.get(user_profile.account_status, "⚪")
        st.markdown(f"**ステータス**: {status_color} {user_profile.account_status}")
        
        if user_profile.created_at:
            st.markdown(f"**登録日**: {user_profile.created_at.strftime('%Y年%m月%d日')}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # タブでコンテンツを分割
    tab1, tab2, tab3, tab4 = st.tabs(["📊 学習統計", "🏆 成果・バッジ", "⚙️ 設定", "✏️ プロフィール編集"])
    
    with tab1:
        show_learning_statistics(user_profile.user_id)
    
    with tab2:
        show_user_achievements(user_profile.user_id)
    
    with tab3:
        show_user_settings(user_profile.user_id)
    
    with tab4:
        show_profile_edit(user_profile)

def show_learning_statistics(user_id: str):
    """学習統計表示"""
    st.markdown("### 学習統計")
    
    # データベースから実際の統計を取得
    try:
        adapter = DatabaseAdapterV3()
        if adapter.is_available():
            # 実際の統計データを取得
            total_sessions = 0
            average_score = 0.0
            streak_days = 0
            monthly_sessions = 0
            
            # 学習履歴から統計を計算
            history = adapter.get_user_history(limit=1000)  # 全履歴を取得
            
            if history:
                total_sessions = len(history)
                
                # 平均スコアを計算
                scores = []
                for session in history:
                    if 'scores' in session and session['scores']:
                        for score in session['scores']:
                            if 'score_value' in score:
                                scores.append(score['score_value'])
                
                if scores:
                    average_score = sum(scores) / len(scores)
                
                # 今月のセッション数を計算
                current_month = datetime.now().month
                monthly_sessions = 0
                for s in history:
                    try:
                        # 新しいDB設計に対応した日付フィールドの取得
                        date_str = s.get('date') or s.get('created_at') or s.get('start_time')
                        if date_str:
                            if isinstance(date_str, str):
                                # 文字列の場合はパース
                                if 'Z' in date_str:
                                    date_str = date_str.replace('Z', '+00:00')
                                session_date = datetime.fromisoformat(date_str)
                            else:
                                # datetimeオブジェクトの場合
                                session_date = date_str
                            
                            if session_date.month == current_month:
                                monthly_sessions += 1
                    except (ValueError, TypeError, AttributeError) as e:
                        # 日付パースエラーの場合はスキップ
                        continue
                
                # 連続日数は簡略化（実際の実装ではより複雑）
                streak_days = min(7, total_sessions)  # 仮の実装
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown('<div class="stats-card">', unsafe_allow_html=True)
                st.metric("総練習回数", str(total_sessions))
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown('<div class="stats-card">', unsafe_allow_html=True)
                st.metric("平均スコア", f"{average_score:.1f}" if average_score > 0 else "0.0")
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col3:
                st.markdown('<div class="stats-card">', unsafe_allow_html=True)
                st.metric("連続日数", str(streak_days))
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col4:
                st.markdown('<div class="stats-card">', unsafe_allow_html=True)
                st.metric("今月の練習", str(monthly_sessions))
                st.markdown('</div>', unsafe_allow_html=True)
            
            # 学習履歴グラフ（簡略化）
            st.markdown("#### 📈 学習進捗")
            if total_sessions > 0:
                st.success(f"現在 {total_sessions} 回の練習を完了しています。詳細は「学習履歴」ページで確認できます。")
            else:
                st.info("まだ練習履歴がありません。練習を始めて統計を確認しましょう！")
        else:
            st.warning("データベース接続が利用できません。統計情報を表示できません。")
    except Exception as e:
        st.error(f"統計データの取得中にエラーが発生しました: {e}")
        # フォールバック: 基本的な統計表示
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown('<div class="stats-card">', unsafe_allow_html=True)
            st.metric("総練習回数", "0")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="stats-card">', unsafe_allow_html=True)
            st.metric("平均スコア", "0.0")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown('<div class="stats-card">', unsafe_allow_html=True)
            st.metric("連続日数", "0")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col4:
            st.markdown('<div class="stats-card">', unsafe_allow_html=True)
            st.metric("今月の練習", "0")
            st.markdown('</div>', unsafe_allow_html=True)

def show_user_achievements(user_id: str):
    """ユーザー成果表示"""
    st.markdown("### 🏆 成果・バッジ")
    
    achievements = auth_manager.get_user_achievements(user_id)
    
    if not achievements:
        st.info("まだ成果がありません。練習を始めて最初のバッジを獲得しましょう！")
        return
    
    # 成果統計
    total_points = sum(a.points_earned for a in achievements)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("獲得バッジ数", len(achievements))
    with col2:
        st.metric("合計ポイント", total_points)
    with col3:
        recent_count = len([a for a in achievements if a.earned_at >= datetime.now() - timedelta(days=30)])
        st.metric("今月の成果", recent_count)
    
    # バッジ表示
    st.markdown("#### 🎖️ 獲得バッジ")
    
    for achievement in achievements:
        with st.container(border=True):
            col1, col2 = st.columns([1, 4])
            
            with col1:
                st.markdown(f'<div style="font-size: 3rem; text-align: center; background-color: {achievement.badge_color}; border-radius: 50%; width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; margin: 0 auto;">{achievement.badge_icon}</div>', unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"**{achievement.achievement_name}**")
                st.markdown(achievement.achievement_description)
                st.caption(f"獲得日: {achievement.earned_at.strftime('%Y年%m月%d日')} | ポイント: {achievement.points_earned}pt")

def show_user_settings(user_id: str):
    """ユーザー設定表示・編集"""
    st.markdown("### ⚙️ 設定")
    
    settings = auth_manager.get_user_settings(user_id)
    if not settings:
        st.error("設定を取得できませんでした。")
        return
    
    with st.form("settings_form"):
        st.markdown('<div class="setting-group">', unsafe_allow_html=True)
        st.markdown("#### 🎯 学習目標")
        
        col1, col2 = st.columns(2)
        with col1:
            daily_goal = st.number_input("1日の練習目標数", min_value=1, max_value=10, value=settings.daily_practice_goal)
            weekly_goal = st.number_input("1週間の練習目標数", min_value=1, max_value=50, value=settings.weekly_practice_goal)
        
        with col2:
            target_score = st.slider("目標スコア", min_value=5.0, max_value=10.0, value=float(settings.target_score), step=0.1)
            practice_time = st.selectbox("練習時間帯", 
                                       options=['anytime', 'morning', 'afternoon', 'evening'],
                                       index=['anytime', 'morning', 'afternoon', 'evening'].index(settings.preferred_practice_time),
                                       format_func=lambda x: {'anytime': 'いつでも', 'morning': '朝', 'afternoon': '午後', 'evening': '夜'}[x])
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="setting-group">', unsafe_allow_html=True)
        st.markdown("#### 🔔 通知設定")
        
        col1, col2 = st.columns(2)
        with col1:
            email_notifications = st.checkbox("メール通知", value=settings.email_notifications)
            practice_reminders = st.checkbox("練習リマインダー", value=settings.practice_reminders)
        
        with col2:
            achievement_notifications = st.checkbox("成果通知", value=settings.achievement_notifications)
            weekly_summary = st.checkbox("週次サマリー", value=settings.weekly_summary)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="setting-group">', unsafe_allow_html=True)
        st.markdown("#### 🎮 学習設定")
        
        col1, col2 = st.columns(2)
        with col1:
            difficulty = st.select_slider("好みの難易度", options=[1, 2, 3, 4, 5], value=settings.preferred_difficulty,
                                        format_func=lambda x: f"レベル {x}")
            auto_save = st.checkbox("自動保存", value=settings.auto_save_enabled)
            show_hints = st.checkbox("ヒント表示", value=settings.show_hints)
        
        with col2:
            enable_timer = st.checkbox("タイマー機能", value=settings.enable_timer)
            duration = st.number_input("デフォルト練習時間（分）", min_value=5, max_value=300, value=settings.default_practice_duration)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="setting-group">', unsafe_allow_html=True)
        st.markdown("#### 🎨 UI設定")
        
        col1, col2 = st.columns(2)
        with col1:
            theme = st.selectbox("テーマ", options=['light', 'dark', 'auto'], 
                               index=['light', 'dark', 'auto'].index(settings.theme),
                               format_func=lambda x: {'light': 'ライト', 'dark': 'ダーク', 'auto': '自動'}[x])
            font_size = st.selectbox("フォントサイズ", options=['small', 'medium', 'large'],
                                   index=['small', 'medium', 'large'].index(settings.font_size),
                                   format_func=lambda x: {'small': '小', 'medium': '中', 'large': '大'}[x])
        
        with col2:
            sidebar_collapsed = st.checkbox("サイドバーを折りたたむ", value=settings.sidebar_collapsed)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="setting-group">', unsafe_allow_html=True)
        st.markdown("#### 🔒 プライバシー設定")
        
        profile_visibility = st.selectbox("プロフィール公開範囲", 
                                        options=['public', 'friends', 'private'],
                                        index=['public', 'friends', 'private'].index(settings.profile_visibility),
                                        format_func=lambda x: {'public': '公開', 'friends': '友達のみ', 'private': '非公開'}[x])
        show_stats = st.checkbox("学習統計を表示", value=settings.show_learning_stats)
        allow_analysis = st.checkbox("データ分析を許可", value=settings.allow_data_analysis)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.form_submit_button("設定を保存", type="primary", use_container_width=True):
            # 新しい設定を作成
            new_settings = UserSettings(
                daily_practice_goal=daily_goal,
                weekly_practice_goal=weekly_goal,
                target_score=target_score,
                preferred_practice_time=practice_time,
                email_notifications=email_notifications,
                practice_reminders=practice_reminders,
                achievement_notifications=achievement_notifications,
                weekly_summary=weekly_summary,
                preferred_difficulty=difficulty,
                auto_save_enabled=auto_save,
                show_hints=show_hints,
                enable_timer=enable_timer,
                default_practice_duration=duration,
                theme=theme,
                font_size=font_size,
                sidebar_collapsed=sidebar_collapsed,
                profile_visibility=profile_visibility,
                show_learning_stats=show_stats,
                allow_data_analysis=allow_analysis
            )
            
            success, message = auth_manager.update_user_settings(user_id, new_settings)
            if success:
                st.success(message)
                time.sleep(1)
                st.rerun()
            else:
                st.error(message)

def show_profile_edit(user_profile: UserProfile):
    """プロフィール編集"""
    st.markdown("### ✏️ プロフィール編集")
    
    with st.form("profile_edit_form"):
        display_name = st.text_input("表示名", value=user_profile.display_name or "")
        
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("名前", value=user_profile.first_name or "")
        with col2:
            last_name = st.text_input("姓", value=user_profile.last_name or "")
        
        bio = st.text_area("自己紹介", value=user_profile.bio or "", max_chars=500, 
                          help="最大500文字")
        
        col1, col2 = st.columns(2)
        with col1:
            timezone = st.selectbox("タイムゾーン", 
                                  options=['Asia/Tokyo', 'Asia/Seoul', 'UTC', 'America/New_York'],
                                  index=['Asia/Tokyo', 'Asia/Seoul', 'UTC', 'America/New_York'].index(user_profile.timezone or 'Asia/Tokyo'))
        
        with col2:
            language = st.selectbox("言語", 
                                  options=['ja', 'en', 'ko'],
                                  index=['ja', 'en', 'ko'].index(user_profile.language or 'ja'),
                                  format_func=lambda x: {'ja': '日本語', 'en': 'English', 'ko': '한국어'}[x])
        
        if st.form_submit_button("プロフィールを更新", type="primary"):
            updates = {
                'display_name': display_name,
                'first_name': first_name,
                'last_name': last_name,
                'bio': bio,
                'timezone': timezone,
                'language': language
            }
            
            success, message = auth_manager.update_user_profile(user_profile.user_id, updates)
            if success:
                st.success(message)
                # プロフィールを再取得
                updated_profile = auth_manager.get_user_profile(user_profile.user_id)
                if updated_profile:
                    st.session_state.user_profile = updated_profile
                time.sleep(1)
                st.rerun()
            else:
                st.error(message)
    
    # パスワード変更セクション
    st.markdown("---")
    st.markdown("#### 🔐 パスワード変更")
    
    with st.form("password_change_form"):
        current_password = st.text_input("現在のパスワード", type="password")
        new_password = st.text_input("新しいパスワード", type="password")
        confirm_password = st.text_input("新しいパスワード（確認）", type="password")
        
        if st.form_submit_button("パスワードを変更"):
            if not current_password or not new_password:
                st.error("すべてのフィールドを入力してください。")
            elif new_password != confirm_password:
                st.error("新しいパスワードが一致しません。")
            else:
                success, message = auth_manager.change_password(user_profile.user_id, current_password, new_password)
                if success:
                    st.success(message)
                else:
                    st.error(message)

def show_logout_button():
    """ログアウトボタン表示"""
    if st.session_state.user_authenticated and st.session_state.user_profile:
        with st.sidebar:
            st.markdown("---")
            if st.button("🚪 ログアウト", use_container_width=True, type="secondary"):
                if auth_manager.logout_user(st.session_state.user_profile.user_id):
                    # 認証状態をクリア
                    if clear_auth_state():
                        st.session_state.auth_mode = 'login'
                        st.success("ログアウトしました。")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("ログアウト中にエラーが発生しました")

# メイン処理
def main():
    # 認証状態の確認
    if st.session_state.user_authenticated and st.session_state.user_profile:
        # 認証済み - プロフィール表示
        show_user_profile()
        show_logout_button()
    else:
        # 未認証 - ログイン/登録フォーム表示
        if st.session_state.auth_mode == 'login':
            show_login_form()
        elif st.session_state.auth_mode == 'register':
            show_register_form()
        else:
            # デフォルトはログイン
            st.session_state.auth_mode = 'login'
            show_login_form()

if __name__ == "__main__":
    main()

# サイドバー情報
with st.sidebar:
    st.markdown("### 👤 ユーザー管理")
    
    if st.session_state.user_authenticated and st.session_state.user_profile:
        user = st.session_state.user_profile
        st.success(f"ログイン中: {user.display_name}")
        st.caption(f"メール: {user.email}")
        
        # 簡易統計表示
        st.markdown("---")
        st.markdown("#### 📊 クイック統計")
        st.info("統計データの読み込み中...")
        
    else:
        st.info("ログインしてください")
        
        # ゲスト機能の説明
        st.markdown("---")
        st.markdown("#### 🎯 ユーザー登録のメリット")
        st.markdown("""
        - 📚 学習履歴の永続保存
        - 🏆 成果・バッジシステム
        - 📊 詳細な学習統計
        - ⚙️ 個人設定の保存
        - 🔔 練習リマインダー
        - 📱 マルチデバイス対応
        """)
    
    st.markdown("---")
    st.markdown("#### 🔒 セキュリティ")
    st.markdown("""
    - 🛡️ パスワードの暗号化保存
    - 🔐 アカウントロック機能
    - 📝 アクティビティログ
    - 🚫 不正アクセス検知
    """) 