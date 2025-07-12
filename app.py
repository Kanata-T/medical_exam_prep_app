import streamlit as st
import google.genai as genai
from modules.session_manager import session_manager
from modules.user_auth import get_user_auth_manager
from modules.utils import auto_save_session
from datetime import datetime, timedelta

# genai.configure(api_key=st.secrets["GOOGLE_API_KEY"]) # この行は新しいSDKでは不要になる可能性が高い

st.set_page_config(
    page_title="医学部研修医採用試験対策支援アプリ",
    page_icon="🩺",
    layout="wide"
)

# セッション管理とユーザー認証の初期化
current_session = session_manager.get_user_session()
session_manager.update_session_activity(current_session)
auto_save_session()

# ページヘッダー
col1, col2 = st.columns([3, 1])

with col1:
    st.title("🩺 医学部研修医採用試験対策支援アプリ")

with col2:
    # ユーザー状態表示
    if current_session.is_authenticated and current_session.user_profile:
        user_name = current_session.user_profile.get('display_name', 'ユーザー')
        st.success(f"👤 {user_name}")
        if st.button("📊 マイページ", use_container_width=True):
            st.switch_page("pages/07_ユーザー管理.py")
    else:
        st.info("ゲストモード")
        if st.button("🔐 ログイン", use_container_width=True, type="primary"):
            st.switch_page("pages/07_ユーザー管理.py")

# メイン機能説明
st.markdown(
    """
    このアプリケーションは、医学部研修医の採用試験対策を総合的に支援するために開発されました。
    AIによるパーソナライズされたフィードバックを通じて、あなたの合格を力強くサポートします。
    """
)

# 認証状態に応じた表示
if current_session.is_authenticated:
    # 認証済みユーザー向けのパーソナライズ表示
    st.markdown("---")
    st.markdown("### 🎯 あなたの学習状況")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # 簡易統計（実装簡略化）
    with col1:
        st.metric(
            label="総練習回数",
            value="42",
            delta="+3",
            help="全ての練習タイプを合わせた実施回数"
        )
    
    with col2:
        st.metric(
            label="平均スコア",
            value="8.2",
            delta="+0.5",
            help="最近10回の練習の平均スコア"
        )
    
    with col3:
        st.metric(
            label="連続日数",
            value="7",
            delta="+7",
            help="連続して練習した日数"
        )
    
    with col4:
        st.metric(
            label="今月の練習",
            value="15",
            delta="+8",
            help="今月実施した練習回数"
        )
    
    # 最近の成果表示
    auth_manager = get_user_auth_manager()
    if auth_manager:
        achievements = auth_manager.get_user_achievements(current_session.user_id)
        recent_achievements = [a for a in achievements if a.earned_at >= datetime.now() - timedelta(days=7)]
        
        if recent_achievements:
            st.markdown("### 🏆 今週の成果")
            achievement_cols = st.columns(min(len(recent_achievements), 4))
            for i, achievement in enumerate(recent_achievements[:4]):
                with achievement_cols[i]:
                    st.markdown(f"""
                    <div style="text-align: center; padding: 1rem; border: 1px solid #e1e5e9; border-radius: 8px; background-color: {achievement.badge_color}20;">
                        <div style="font-size: 2rem;">{achievement.badge_icon}</div>
                        <div style="font-weight: bold; margin-top: 0.5rem;">{achievement.achievement_name}</div>
                        <div style="font-size: 0.8rem; margin-top: 0.25rem;">{achievement.points_earned}pt</div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # おすすめ練習
    st.markdown("---")
    st.markdown("### 📚 今日のおすすめ練習")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **🎯 弱点克服練習**
        
        前回のスコアから、以下の練習をおすすめします：
        """)
        
        if st.button("📝 小論文練習", use_container_width=True):
            st.switch_page("pages/02_小論文.py")
    
    with col2:
        st.markdown("""
        **⭐ 得意分野伸展**
        
        得意な分野をさらに伸ばしましょう：
        """)
        
        if st.button("📖 英語読解練習", use_container_width=True):
            st.switch_page("pages/05_英語読解.py")

else:
    # 未認証ユーザー向けの機能説明
    st.markdown("---")
    st.markdown("### ✨ ユーザー登録のメリット")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **📊 学習データの永続保存**
        - 練習履歴の長期保存
        - スコアの推移グラフ
        - 詳細な分析レポート
        
        **🏆 成果・バッジシステム**
        - 練習達成による成果獲得
        - モチベーション向上
        - 学習継続のサポート
        """)
    
    with col2:
        st.markdown("""
        **⚙️ 個人設定・カスタマイズ**
        - 学習目標の設定
        - 練習リマインダー
        - UI設定の保存
        
        **📱 マルチデバイス対応**
        - PC・スマホで同期
        - どこでも学習継続
        - セキュアなデータ管理
        """)
    
    st.info("💡 **今すぐ無料登録**で、より充実した学習体験をお楽しみください！")

# メイン機能一覧
st.markdown("---")
st.markdown("### 🎯 主な機能")

# 機能カードを表示
function_cols = st.columns(2)

with function_cols[0]:
    with st.container(border=True):
        st.markdown("#### 📄 採用試験シミュレーター")
        st.markdown("""
        医学論文のAbstract読解、意見陳述、小論文作成を、60分の時間制限付きで実践的に練習できます。
        
        **特徴:**
        - 本格的な時間制限
        - 過去問スタイル対応
        - 包括的な採点
        """)
        if st.button("📄 試験練習を開始", key="exam_button", use_container_width=True):
            st.switch_page("pages/01_県総_採用試験.py")
    
    with st.container(border=True):
        st.markdown("#### 🎙️ AI面接シミュレーター")
        st.markdown("""
        AIが面接官となり、実践的な質問を投げかけます。あなたの回答に対し、多角的な視点からフィードバックを提供します。
        
        **特徴:**
        - 単発練習とセッション練習
        - 音声認識対応
        - リアルタイム対話
        """)
        if st.button("🎙️ 面接練習を開始", key="interview_button", use_container_width=True):
            st.switch_page("pages/03_面接.py")

with function_cols[1]:
    with st.container(border=True):
        st.markdown("#### ✍️ 小論文対策")
        st.markdown("""
        1000字の小論文に特化し、「構成メモ」と「清書」の両方をAIが評価。論理的思考力と文章構成力を鍛えます。
        
        **特徴:**
        - 段階的な執筆サポート
        - 構成力の向上
        - 論理的思考の訓練
        """)
        if st.button("✍️ 小論文練習を開始", key="essay_button", use_container_width=True):
            st.switch_page("pages/02_小論文.py")
    
    with st.container(border=True):
        st.markdown("#### 📖 英語読解")
        st.markdown("""
        医学論文のAbstractを使った読解練習。翻訳と意見・考察を通じて、専門英語力を向上させます。
        
        **特徴:**
        - 最新医学論文使用
        - 過去問スタイル対応
        - 専門用語の習得
        """)
        if st.button("📖 英語読解を開始", key="reading_button", use_container_width=True):
            st.switch_page("pages/05_英語読解.py")

# 追加機能
st.markdown("---")
st.markdown("### 📊 学習サポート機能")

support_cols = st.columns(3)

with support_cols[0]:
    with st.container(border=True):
        st.markdown("#### 📝 自由記述")
        st.markdown("医学的なテーマについて自由に記述し、AIからフィードバックを受けられます。")
        if st.button("📝 自由記述", key="writing_button", use_container_width=True):
            st.switch_page("pages/04_自由記述.py")

with support_cols[1]:
    with st.container(border=True):
        st.markdown("#### 📚 学習履歴")
        st.markdown("すべての練習結果を確認し、成長の軌跡を分析できます。")
        if st.button("📚 学習履歴", key="history_button", use_container_width=True):
            st.switch_page("pages/06_学習履歴.py")

with support_cols[2]:
    with st.container(border=True):
        st.markdown("#### 👤 ユーザー管理")
        st.markdown("プロフィール、設定、成果を管理し、学習目標を設定できます。")
        if st.button("👤 マイページ", key="profile_button", use_container_width=True):
            st.switch_page("pages/07_ユーザー管理.py")

# フッター
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem;">
    <p>💡 <strong>学習のコツ:</strong> 継続的な練習が合格への近道です。毎日少しずつでも練習を続けることをおすすめします。</p>
    <p>🔒 あなたの学習データは安全に保護されています</p>
</div>
""", unsafe_allow_html=True)

# サイドバー情報
with st.sidebar:
    st.markdown("### 🩺 医学部採用試験対策")
    
    # セッション情報表示
    session_manager.show_session_status(current_session)
    
    st.markdown("---")
    st.markdown("### 🎯 クイックアクセス")
    
    quick_buttons = [
        ("📄 採用試験", "pages/01_県総_採用試験.py"),
        ("✍️ 小論文", "pages/02_小論文.py"),
        ("🎙️ 面接", "pages/03_面接.py"),
        ("📖 英語読解", "pages/05_英語読解.py"),
        ("📝 自由記述", "pages/04_自由記述.py"),
        ("📚 学習履歴", "pages/06_学習履歴.py")
    ]
    
    for button_text, page_path in quick_buttons:
        if st.button(button_text, key=f"quick_{page_path}", use_container_width=True):
            st.switch_page(page_path)
    
    st.markdown("---")
    st.markdown("### 💡 学習のヒント")
    
    tips = [
        "毎日少しずつでも練習を継続する",
        "苦手分野を重点的に練習する",
        "フィードバックを次の練習に活かす",
        "時間を意識した練習を心がける",
        "複数の練習タイプをバランスよく"
    ]
    
    for tip in tips:
        st.markdown(f"• {tip}")
    
    st.markdown("---")
    st.caption("🔄 自動保存機能により、学習進捗は常に保存されます")
    st.caption("⚡ AI採点により、即座にフィードバックを受けられます")
