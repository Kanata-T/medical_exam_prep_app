"""
ユーザー認証管理システム
パスワードベース認証、プロフィール管理、学習設定管理

新スキーマ対応版 - カテゴリー別管理設計に対応
"""

import hashlib
import secrets
import uuid
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import streamlit as st
from supabase import Client

# ロガー設定
logger = logging.getLogger(__name__)

class AccountStatus(Enum):
    """アカウント状態"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"

class LoginResult(Enum):
    """ログイン結果"""
    SUCCESS = "success"
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_SUSPENDED = "account_suspended"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    USER_NOT_FOUND = "user_not_found"

@dataclass
class UserProfile:
    """ユーザープロフィール情報"""
    user_id: str
    email: str
    display_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    timezone: str = "Asia/Tokyo"
    language: str = "ja"
    email_verified: bool = False
    account_status: str = "active"
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None
    last_login: Optional[datetime] = None

@dataclass
class UserSettings:
    """ユーザー学習設定"""
    # 学習目標
    daily_practice_goal: int = 1
    weekly_practice_goal: int = 7
    target_score: float = 8.0
    preferred_practice_time: str = "anytime"
    
    # 通知設定
    email_notifications: bool = True
    practice_reminders: bool = True
    achievement_notifications: bool = True
    weekly_summary: bool = True
    
    # 学習設定
    preferred_difficulty: int = 2
    auto_save_enabled: bool = True
    show_hints: bool = True
    enable_timer: bool = False
    default_practice_duration: int = 60
    
    # UI設定
    theme: str = "light"
    font_size: str = "medium"
    sidebar_collapsed: bool = False
    
    # プライバシー設定
    profile_visibility: str = "private"
    show_learning_stats: bool = True
    allow_data_analysis: bool = True

@dataclass
class UserAchievement:
    """ユーザー成果"""
    achievement_id: str
    achievement_type: str
    achievement_name: str
    achievement_description: str
    earned_at: datetime
    badge_icon: str
    badge_color: str
    points_earned: int
    metadata: Dict[str, Any]
    is_visible: bool = True

class PasswordManager:
    """パスワード管理クラス"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        パスワードをハッシュ化
        
        Args:
            password: ハッシュ化するパスワード
            
        Returns:
            ハッシュ化されたパスワード（ソルト付き）
        """
        # ソルトを生成
        salt = secrets.token_hex(32)
        # パスワードとソルトを結合してハッシュ化
        pwdhash = hashlib.pbkdf2_hmac('sha256', 
                                      password.encode('utf-8'), 
                                      salt.encode('utf-8'), 
                                      100000)
        return salt + pwdhash.hex()
    
    @staticmethod
    def verify_password(stored_password: str, provided_password: str) -> bool:
        """
        パスワードを検証
        
        Args:
            stored_password: 保存されているハッシュ化パスワード
            provided_password: 検証するパスワード
            
        Returns:
            パスワードが一致するかどうか
        """
        try:
            # ソルトとハッシュを分離
            salt = stored_password[:64]
            stored_hash = stored_password[64:]
            
            # 提供されたパスワードをハッシュ化
            pwdhash = hashlib.pbkdf2_hmac('sha256',
                                          provided_password.encode('utf-8'),
                                          salt.encode('utf-8'),
                                          100000)
            
            return pwdhash.hex() == stored_hash
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def generate_reset_token() -> str:
        """
        パスワードリセットトークンを生成
        
        Returns:
            セキュアなリセットトークン
        """
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
        """
        パスワード強度を検証
        
        Args:
            password: 検証するパスワード
            
        Returns:
            (強度が十分かどうか, エラーメッセージのリスト)
        """
        errors = []
        
        if len(password) < 8:
            errors.append("パスワードは8文字以上である必要があります")
        
        if not re.search(r"[a-z]", password):
            errors.append("小文字を含める必要があります")
        
        if not re.search(r"[A-Z]", password):
            errors.append("大文字を含める必要があります")
        
        if not re.search(r"\d", password):
            errors.append("数字を含める必要があります")
        
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            errors.append("特殊文字を含める必要があります")
        
        return len(errors) == 0, errors

class EmailValidator:
    """メールアドレス検証クラス"""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """
        メールアドレスの形式を検証
        
        Args:
            email: 検証するメールアドレス
            
        Returns:
            有効なメールアドレスかどうか
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def generate_verification_token() -> str:
        """
        メール認証トークンを生成
        
        Returns:
            セキュアな認証トークン
        """
        return secrets.token_urlsafe(32)

class UserAuthManager:
    """ユーザー認証管理メインクラス"""
    
    def __init__(self, supabase_client: Client):
        """
        初期化
        
        Args:
            supabase_client: Supabaseクライアント
        """
        self.client = supabase_client
        self.password_manager = PasswordManager()
        self.email_validator = EmailValidator()
    
    def register_user(self, email: str, password: str, display_name: str, 
                     first_name: str = "", last_name: str = "") -> Tuple[bool, str, Optional[str]]:
        """
        ユーザー登録
        
        Args:
            email: メールアドレス
            password: パスワード
            display_name: 表示名
            first_name: 名（オプション）
            last_name: 姓（オプション）
            
        Returns:
            (成功したかどうか, メッセージ, ユーザーID)
        """
        try:
            # メールアドレス検証
            if not self.email_validator.is_valid_email(email):
                return False, "無効なメールアドレスです", None
            
            # パスワード強度検証
            is_strong, password_errors = self.password_manager.validate_password_strength(password)
            if not is_strong:
                return False, "パスワードが弱すぎます: " + ", ".join(password_errors), None
            
            # 既存ユーザー確認
            existing_user = self.client.table('users').select('user_id').eq('email', email).execute()
            if existing_user.data:
                return False, "このメールアドレスは既に登録されています", None
            
            # パスワードハッシュ化
            password_hash = self.password_manager.hash_password(password)
            verification_token = self.email_validator.generate_verification_token()
            
            # ユーザー作成
            user_data = {
                'email': email,
                'display_name': display_name,
                'first_name': first_name,
                'last_name': last_name,
                'password_hash': password_hash,
                'email_verification_token': verification_token,
                'account_status': AccountStatus.PENDING_VERIFICATION.value,
                'created_at': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'terms_accepted': True,
                'terms_accepted_at': datetime.now().isoformat(),
                'privacy_policy_accepted': True,
                'privacy_policy_accepted_at': datetime.now().isoformat()
            }
            
            result = self.client.table('users').insert(user_data).execute()
            
            if result.data:
                user_id = result.data[0]['user_id']
                logger.info(f"User registered successfully: {user_id}")
                
                # TODO: メール認証送信（実装は後で）
                # self.send_verification_email(email, verification_token)
                
                return True, "ユーザー登録が完了しました。メール認証を確認してください。", user_id
            else:
                return False, "ユーザー登録に失敗しました", None
                
        except Exception as e:
            logger.error(f"Error in register_user: {e}")
            return False, f"登録エラー: {e}", None
    
    def login_user(self, email: str, password: str) -> Tuple[LoginResult, Optional[UserProfile], str]:
        """
        ユーザーログイン
        
        Args:
            email: メールアドレス
            password: パスワード
            
        Returns:
            (ログイン結果, ユーザープロフィール, メッセージ)
        """
        try:
            # ユーザー検索
            user_result = self.client.table('users').select('*').eq('email', email).execute()
            
            if not user_result.data:
                return LoginResult.USER_NOT_FOUND, None, "ユーザーが見つかりません"
            
            user_data = user_result.data[0]
            user_id = user_data['user_id']
            
            # アカウント状態確認
            if user_data['account_status'] == AccountStatus.SUSPENDED.value:
                return LoginResult.ACCOUNT_SUSPENDED, None, "アカウントが停止されています"
            
            # アカウントロック確認
            if (user_data.get('account_locked_until') and 
                datetime.fromisoformat(user_data['account_locked_until'].replace('Z', '+00:00')) > datetime.now()):
                return LoginResult.ACCOUNT_LOCKED, None, "アカウントがロックされています。しばらく待ってから再試行してください"
            
            # パスワード検証
            if not user_data.get('password_hash'):
                return LoginResult.INVALID_CREDENTIALS, None, "パスワードが設定されていません"
            
            if not self.password_manager.verify_password(user_data['password_hash'], password):
                # 失敗ログイン回数を増加
                self._handle_failed_login(email)
                return LoginResult.INVALID_CREDENTIALS, None, "メールアドレスまたはパスワードが正しくありません"
            
            # メール認証確認（オプション）
            if not user_data.get('email_verified', False):
                # 本番では厳密にするが、開発中は警告のみ
                logger.warning(f"User {email} logged in without email verification")
            
            # ログイン成功 - セッション情報更新
            self._update_login_success(user_id)
            
            # ユーザープロフィール作成
            profile = UserProfile(
                user_id=user_id,
                email=user_data['email'],
                display_name=user_data['display_name'],
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                avatar_url=user_data.get('avatar_url'),
                bio=user_data.get('bio'),
                timezone=user_data.get('timezone', 'Asia/Tokyo'),
                language=user_data.get('language', 'ja'),
                email_verified=user_data.get('email_verified', False),
                account_status=user_data['account_status'],
                created_at=datetime.fromisoformat(user_data['created_at'].replace('Z', '+00:00')) if user_data.get('created_at') else None,
                last_active=datetime.fromisoformat(user_data['last_active'].replace('Z', '+00:00')) if user_data.get('last_active') else None,
                last_login=datetime.now()
            )
            
            # アクティビティログ記録
            self._log_user_activity(user_id, 'login', 'User logged in successfully')
            
            return LoginResult.SUCCESS, profile, "ログインしました"
            
        except Exception as e:
            logger.error(f"Error in login_user: {e}")
            return LoginResult.INVALID_CREDENTIALS, None, f"ログインエラー: {e}"
    
    def logout_user(self, user_id: str) -> bool:
        """
        ユーザーログアウト
        
        Args:
            user_id: ユーザーID
            
        Returns:
            ログアウトが成功したかどうか
        """
        try:
            # アクティビティログ記録
            self._log_user_activity(user_id, 'logout', 'User logged out')
            
            # セッション状態をクリア
            if 'user_profile' in st.session_state:
                del st.session_state.user_profile
            if 'user_authenticated' in st.session_state:
                del st.session_state.user_authenticated
            if 'auth_token' in st.session_state:
                del st.session_state.auth_token
            
            logger.info(f"User logged out: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error in logout_user: {e}")
            return False
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        ユーザープロフィール取得
        
        Args:
            user_id: ユーザーID
            
        Returns:
            ユーザープロフィール（見つからない場合はNone）
        """
        try:
            result = self.client.table('users').select('*').eq('user_id', user_id).execute()
            
            if not result.data:
                return None
            
            user_data = result.data[0]
            
            return UserProfile(
                user_id=user_data['user_id'],
                email=user_data['email'],
                display_name=user_data['display_name'],
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                avatar_url=user_data.get('avatar_url'),
                bio=user_data.get('bio'),
                timezone=user_data.get('timezone', 'Asia/Tokyo'),
                language=user_data.get('language', 'ja'),
                email_verified=user_data.get('email_verified', False),
                account_status=user_data['account_status'],
                created_at=datetime.fromisoformat(user_data['created_at'].replace('Z', '+00:00')) if user_data.get('created_at') else None,
                last_active=datetime.fromisoformat(user_data['last_active'].replace('Z', '+00:00')) if user_data.get('last_active') else None,
                last_login=datetime.fromisoformat(user_data['last_login'].replace('Z', '+00:00')) if user_data.get('last_login') else None
            )
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None
    
    def update_user_profile(self, user_id: str, profile_updates: Dict[str, Any]) -> Tuple[bool, str]:
        """
        ユーザープロフィール更新
        
        Args:
            user_id: ユーザーID
            profile_updates: 更新するプロフィール情報
            
        Returns:
            (成功したかどうか, メッセージ)
        """
        try:
            # 更新可能フィールドのみ許可
            allowed_fields = {
                'display_name', 'first_name', 'last_name', 'avatar_url', 'bio', 
                'timezone', 'language'
            }
            
            filtered_updates = {k: v for k, v in profile_updates.items() if k in allowed_fields}
            
            if not filtered_updates:
                return False, "更新可能なフィールドがありません"
            
            # 更新実行
            result = self.client.table('users').update(filtered_updates).eq('user_id', user_id).execute()
            
            if result.data:
                # アクティビティログ
                self._log_user_activity(user_id, 'profile_update', f'Profile updated: {list(filtered_updates.keys())}')
                return True, "プロフィールを更新しました"
            else:
                return False, "プロフィール更新に失敗しました"
                
        except Exception as e:
            logger.error(f"Error updating user profile: {e}")
            return False, f"更新エラー: {e}"
    
    def get_user_settings(self, user_id: str) -> Optional[UserSettings]:
        """
        ユーザー設定取得
        
        Args:
            user_id: ユーザーID
            
        Returns:
            ユーザー設定（見つからない場合はNone）
        """
        try:
            result = self.client.table('user_settings').select('*').eq('user_id', user_id).execute()
            
            if not result.data:
                # デフォルト設定を作成
                self._create_default_settings(user_id)
                result = self.client.table('user_settings').select('*').eq('user_id', user_id).execute()
            
            if result.data:
                settings_data = result.data[0]
                return UserSettings(
                    daily_practice_goal=settings_data.get('daily_practice_goal', 1),
                    weekly_practice_goal=settings_data.get('weekly_practice_goal', 7),
                    target_score=float(settings_data.get('target_score', 8.0)),
                    preferred_practice_time=settings_data.get('preferred_practice_time', 'anytime'),
                    email_notifications=settings_data.get('email_notifications', True),
                    practice_reminders=settings_data.get('practice_reminders', True),
                    achievement_notifications=settings_data.get('achievement_notifications', True),
                    weekly_summary=settings_data.get('weekly_summary', True),
                    preferred_difficulty=settings_data.get('preferred_difficulty', 2),
                    auto_save_enabled=settings_data.get('auto_save_enabled', True),
                    show_hints=settings_data.get('show_hints', True),
                    enable_timer=settings_data.get('enable_timer', False),
                    default_practice_duration=settings_data.get('default_practice_duration', 60),
                    theme=settings_data.get('theme', 'light'),
                    font_size=settings_data.get('font_size', 'medium'),
                    sidebar_collapsed=settings_data.get('sidebar_collapsed', False),
                    profile_visibility=settings_data.get('profile_visibility', 'private'),
                    show_learning_stats=settings_data.get('show_learning_stats', True),
                    allow_data_analysis=settings_data.get('allow_data_analysis', True)
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            return None
    
    def update_user_settings(self, user_id: str, settings: UserSettings) -> Tuple[bool, str]:
        """
        ユーザー設定更新
        
        Args:
            user_id: ユーザーID
            settings: 更新する設定
            
        Returns:
            (成功したかどうか, メッセージ)
        """
        try:
            settings_dict = asdict(settings)
            settings_dict['updated_at'] = datetime.now().isoformat()
            
            result = self.client.table('user_settings').update(settings_dict).eq('user_id', user_id).execute()
            
            if result.data:
                self._log_user_activity(user_id, 'settings_update', 'User settings updated')
                return True, "設定を更新しました"
            else:
                return False, "設定更新に失敗しました"
                
        except Exception as e:
            logger.error(f"Error updating user settings: {e}")
            return False, f"設定更新エラー: {e}"
    
    def change_password(self, user_id: str, current_password: str, new_password: str) -> Tuple[bool, str]:
        """
        パスワード変更
        
        Args:
            user_id: ユーザーID
            current_password: 現在のパスワード
            new_password: 新しいパスワード
            
        Returns:
            (成功したかどうか, メッセージ)
        """
        try:
            # 現在のパスワード確認
            user_result = self.client.table('users').select('password_hash').eq('user_id', user_id).execute()
            
            if not user_result.data:
                return False, "ユーザーが見つかりません"
            
            current_hash = user_result.data[0]['password_hash']
            
            if not self.password_manager.verify_password(current_hash, current_password):
                return False, "現在のパスワードが正しくありません"
            
            # 新しいパスワードの強度確認
            is_strong, errors = self.password_manager.validate_password_strength(new_password)
            if not is_strong:
                return False, "新しいパスワードが弱すぎます: " + ", ".join(errors)
            
            # パスワード更新
            new_hash = self.password_manager.hash_password(new_password)
            
            result = self.client.table('users').update({
                'password_hash': new_hash,
                'password_reset_token': None,
                'password_reset_expires': None
            }).eq('user_id', user_id).execute()
            
            if result.data:
                self._log_user_activity(user_id, 'password_change', 'Password changed successfully')
                return True, "パスワードを変更しました"
            else:
                return False, "パスワード変更に失敗しました"
                
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return False, f"パスワード変更エラー: {e}"
    
    def get_user_achievements(self, user_id: str) -> List[UserAchievement]:
        """
        ユーザー成果取得（現在は無効化）
        
        Args:
            user_id: ユーザーID
            
        Returns:
            ユーザー成果のリスト（現在は空リスト）
        """
        # 成果機能は現在無効化（user_achievementsテーブルが存在しないため）
        # 将来的に実装する場合は、テーブル作成後にこの機能を有効化
        return []
    
    def _handle_failed_login(self, email: str) -> None:
        """
        ログイン失敗処理
        
        Args:
            email: メールアドレス
        """
        try:
            self.client.rpc('handle_failed_login', {'user_email': email}).execute()
        except Exception as e:
            logger.error(f"Error handling failed login: {e}")
    
    def _update_login_success(self, user_id: str) -> None:
        """
        ログイン成功時の更新
        
        Args:
            user_id: ユーザーID
        """
        try:
            self.client.table('users').update({
                'last_login': datetime.now().isoformat(),
                'last_active': datetime.now().isoformat(),
                'login_attempts': 0,
                'account_locked_until': None
            }).eq('user_id', user_id).execute()
        except Exception as e:
            logger.error(f"Error updating login success: {e}")
    
    def _log_user_activity(self, user_id: str, activity_type: str, description: str) -> None:
        """
        ユーザーアクティビティログ
        
        Args:
            user_id: ユーザーID
            activity_type: アクティビティタイプ
            description: アクティビティ説明
        """
        try:
            # 一時的なユーザーID（temp_プレフィックス）の場合はログを記録しない
            if user_id.startswith('temp_'):
                logger.debug(f"Skipping activity log for temporary user: {user_id}")
                return
            
            # Streamlitから情報を取得（可能な限り）
            user_agent = st.get_option('server.headless')  # 簡略化
            
            activity_data = {
                'user_id': user_id,
                'activity_type': activity_type,
                'activity_description': description,
                'session_id': None,  # session_idはNULLに設定（外部キー制約を回避）
                'metadata': {
                    'user_agent': str(user_agent),
                    'timestamp': datetime.now().isoformat()
                }
            }
            
            self.client.table('user_activity_log').insert(activity_data).execute()
            
        except Exception as e:
            logger.error(f"Error logging user activity: {e}")
    
    def _create_default_settings(self, user_id: str) -> None:
        """
        デフォルト設定作成
        
        Args:
            user_id: ユーザーID
        """
        try:
            default_settings = asdict(UserSettings())
            default_settings['user_id'] = user_id
            
            self.client.table('user_settings').insert(default_settings).execute()
        except Exception as e:
            logger.error(f"Error creating default settings: {e}")

# グローバルインスタンス（遅延初期化）
_user_auth_manager = None

def get_user_auth_manager() -> Optional[UserAuthManager]:
    """
    UserAuthManagerのシングルトンインスタンスを取得
    
    Returns:
        UserAuthManagerインスタンス（データベースが利用できない場合はNone）
    """
    global _user_auth_manager
    
    if _user_auth_manager is None:
        try:
            from modules.database_v3 import db_manager_v3
            if db_manager_v3.is_available():
                _user_auth_manager = UserAuthManager(db_manager_v3.client)
            else:
                logger.warning("Database not available, user auth features disabled")
                return None
        except Exception as e:
            logger.error(f"Failed to initialize UserAuthManager: {e}")
            return None
    
    return _user_auth_manager 