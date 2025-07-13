"""
Streamlit Cloud環境でのセッション管理とユーザー識別
複数の手法を組み合わせて安定した識別を実現
パスワードベース認証との統合対応
"""

import os
import hashlib
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
import streamlit as st
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class IdentificationMethod(Enum):
    """ユーザー識別方法"""
    PASSWORD_AUTH = "password_auth"          # 新規追加
    EMAIL = "email"
    BROWSER_FINGERPRINT = "browser_fingerprint"
    URL_PARAMETER = "url_parameter"
    SESSION_TOKEN = "session_token"

@dataclass
class UserSession:
    """ユーザーセッション情報"""
    user_id: str
    identification_method: IdentificationMethod
    created_at: datetime
    last_active: datetime
    metadata: Dict[str, Any]
    is_persistent: bool = False
    is_authenticated: bool = False           # 新規追加
    user_profile: Optional[Any] = None       # 新規追加

class BrowserFingerprinter:
    """ブラウザフィンガープリント生成クラス"""
    
    @staticmethod
    def generate_fingerprint() -> str:
        """
        ブラウザフィンガープリントを生成します。
        
        Returns:
            str: 生成されたフィンガープリント
        """
        try:
            # 既存のフィンガープリントがある場合は再利用
            if 'current_fingerprint' in st.session_state:
                existing_fingerprint = st.session_state.current_fingerprint
                if existing_fingerprint and len(existing_fingerprint) == 16:
                    logger.debug(f"Reusing existing fingerprint: {existing_fingerprint}")
                    return existing_fingerprint
            
            components = []
            
            # Streamlit固有の情報（より安定した値を使用）
            components.append(str(st.get_option('server.port') or '8501'))
            components.append(str(st.get_option('server.baseUrlPath') or ''))
            
            # セッション情報（利用可能な場合）
            if hasattr(st, 'session_state') and hasattr(st.session_state, '_state'):
                # セッション状態のハッシュ（個人情報は除外）
                session_info = str(hash(str(st.session_state.get('_streamlit_session_id', ''))))
                components.append(session_info)
            
            # URLパラメータ（利用可能な場合）
            try:
                query_params = st.query_params
                if query_params:
                    # 特定のパラメータのみ使用（個人情報は除外）
                    safe_params = {k: v for k, v in query_params.items() 
                                 if k not in ['email', 'name', 'token']}
                    components.append(str(sorted(safe_params.items())))
            except:
                pass
            
            # デフォルト値を追加（一意性確保）
            components.append('streamlit_medical_app')
            components.append(str(datetime.now().strftime('%Y-%m-%d')))  # 日付ベース
            
            # フィンガープリント生成
            fingerprint_string = '|'.join(str(c) for c in components)
            fingerprint = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:16]
            
            # セッション状態に保存
            st.session_state.current_fingerprint = fingerprint
            
            logger.debug(f"Generated new fingerprint: {fingerprint}")
            return fingerprint
            
        except Exception as e:
            logger.error(f"Error generating fingerprint: {e}")
            # フォールバック
            fallback_fingerprint = hashlib.sha256(f"{uuid.uuid4()}".encode()).hexdigest()[:16]
            st.session_state.current_fingerprint = fallback_fingerprint
            return fallback_fingerprint
    
    @staticmethod
    def is_fingerprint_stable(fingerprint: str) -> bool:
        """
        フィンガープリントの安定性をチェックします。
        
        Args:
            fingerprint (str): チェックするフィンガープリント
        
        Returns:
            bool: 安定している場合True
        """
        try:
            # セッション状態から履歴を取得
            fingerprint_history = st.session_state.get('fingerprint_history', [])
            
            if len(fingerprint_history) < 2:
                return False
            
            # 最近5回の履歴で安定性をチェック
            recent_fingerprints = [fp for fp, _ in fingerprint_history[-5:]]
            stability_rate = recent_fingerprints.count(fingerprint) / len(recent_fingerprints)
            
            return stability_rate >= 0.8  # 80%以上の安定性
            
        except Exception as e:
            logger.error(f"Error checking fingerprint stability: {e}")
            return False

class SessionPersistence:
    """セッション永続化管理クラス"""
    
    @staticmethod
    def save_session_token(user_id: str, session_data: Dict[str, Any]) -> str:
        """
        セッショントークンを生成・保存します。
        
        Args:
            user_id (str): ユーザーID
            session_data (Dict[str, Any]): セッションデータ
        
        Returns:
            str: 生成されたセッショントークン
        """
        try:
            # セッショントークン生成
            token_data = {
                'user_id': user_id,
                'created_at': datetime.now().isoformat(),
                'session_data': session_data,
                'expires_at': (datetime.now() + timedelta(days=30)).isoformat()  # 30日間有効
            }
            
            token_string = json.dumps(token_data, ensure_ascii=False)
            token = hashlib.sha256(token_string.encode()).hexdigest()[:32]
            
            # Streamlitのセッション状態に保存
            if 'session_tokens' not in st.session_state:
                st.session_state.session_tokens = {}
            
            st.session_state.session_tokens[token] = token_data
            
            # 永続化のため、クッキーにも保存（Streamlitの機能を使用）
            try:
                # クッキーに保存（Streamlitの機能）
                st.session_state[f'session_token_{token}'] = token_data
            except:
                pass
            
            # URLパラメータとしても設定（オプション）
            try:
                st.query_params['session_token'] = token
            except:
                pass  # URL更新が失敗しても継続
            
            logger.info(f"Saved session token for user: {user_id}")
            return token
            
        except Exception as e:
            logger.error(f"Error saving session token: {e}")
            return ""
    
    @staticmethod
    def save_auth_token(user_id: str, user_profile: Dict[str, Any]) -> str:
        """
        認証トークンを生成・保存します。
        
        Args:
            user_id (str): ユーザーID
            user_profile (Dict[str, Any]): ユーザープロフィール
        
        Returns:
            str: 生成された認証トークン
        """
        try:
            # datetimeオブジェクトを文字列に変換する関数
            def datetime_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            # 認証トークン生成
            auth_data = {
                'user_id': user_id,
                'user_profile': user_profile,
                'created_at': datetime.now().isoformat(),
                'expires_at': (datetime.now() + timedelta(days=30)).isoformat(),
                'is_authenticated': True
            }
            
            token_string = json.dumps(auth_data, ensure_ascii=False, default=datetime_serializer)
            auth_token = hashlib.sha256(token_string.encode()).hexdigest()[:32]
            
            # セッション状態に保存
            if 'auth_tokens' not in st.session_state:
                st.session_state.auth_tokens = {}
            
            st.session_state.auth_tokens[auth_token] = auth_data
            st.session_state.current_auth_token = auth_token
            
            logger.info(f"Saved auth token for user: {user_id}")
            return auth_token
            
        except Exception as e:
            logger.error(f"Error saving auth token: {e}")
            return ""
    
    @staticmethod
    def load_session_from_token(token: str) -> Optional[Dict[str, Any]]:
        """
        セッショントークンからセッション情報を復元します。
        
        Args:
            token (str): セッショントークン
        
        Returns:
            Optional[Dict[str, Any]]: 復元されたセッション情報、またはNone
        """
        try:
            # 1. セッション状態から取得
            session_tokens = st.session_state.get('session_tokens', {})
            if token in session_tokens:
                token_data = session_tokens[token]
                
                # 有効期限チェック
                expires_at = datetime.fromisoformat(token_data.get('expires_at', '1970-01-01T00:00:00'))
                if datetime.now() < expires_at:
                    return token_data
                else:
                    # 期限切れトークンを削除
                    del session_tokens[token]
            
            # 2. 個別セッション状態から取得
            individual_token_key = f'session_token_{token}'
            if individual_token_key in st.session_state:
                token_data = st.session_state[individual_token_key]
                
                # 有効期限チェック
                expires_at = datetime.fromisoformat(token_data.get('expires_at', '1970-01-01T00:00:00'))
                if datetime.now() < expires_at:
                    # セッショントークン辞書にも復元
                    if 'session_tokens' not in st.session_state:
                        st.session_state.session_tokens = {}
                    st.session_state.session_tokens[token] = token_data
                    return token_data
                else:
                    # 期限切れトークンを削除
                    del st.session_state[individual_token_key]
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading session from token: {e}")
            return None
    
    @staticmethod
    def load_auth_from_token(token: str) -> Optional[Dict[str, Any]]:
        """
        認証トークンから認証情報を復元します。
        
        Args:
            token (str): 認証トークン
        
        Returns:
            Optional[Dict[str, Any]]: 復元された認証情報、またはNone
        """
        try:
            auth_tokens = st.session_state.get('auth_tokens', {})
            if token in auth_tokens:
                auth_data = auth_tokens[token]
                
                # 有効期限チェック
                expires_at = datetime.fromisoformat(auth_data.get('expires_at', '1970-01-01T00:00:00'))
                if datetime.now() < expires_at:
                    return auth_data
                else:
                    # 期限切れトークンを削除
                    del auth_tokens[token]
                    if st.session_state.get('current_auth_token') == token:
                        del st.session_state.current_auth_token
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading auth from token: {e}")
            return None
    
    @staticmethod
    def cleanup_expired_tokens() -> None:
        """
        期限切れトークンのクリーンアップを行います。
        """
        try:
            current_time = datetime.now()
            
            # セッショントークンのクリーンアップ
            session_tokens = st.session_state.get('session_tokens', {})
            expired_session_tokens = []
            for token, token_data in session_tokens.items():
                expires_at = datetime.fromisoformat(token_data.get('expires_at', '1970-01-01T00:00:00'))
                if current_time >= expires_at:
                    expired_session_tokens.append(token)
            
            for token in expired_session_tokens:
                del session_tokens[token]
            
            # 認証トークンのクリーンアップ
            auth_tokens = st.session_state.get('auth_tokens', {})
            expired_auth_tokens = []
            for token, auth_data in auth_tokens.items():
                expires_at = datetime.fromisoformat(auth_data.get('expires_at', '1970-01-01T00:00:00'))
                if current_time >= expires_at:
                    expired_auth_tokens.append(token)
            
            for token in expired_auth_tokens:
                del auth_tokens[token]
                if st.session_state.get('current_auth_token') == token:
                    del st.session_state.current_auth_token
            
            total_expired = len(expired_session_tokens) + len(expired_auth_tokens)
            if total_expired > 0:
                logger.info(f"Cleaned up {total_expired} expired tokens")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")

class EmailBasedAuth:
    """シンプルなメールベース認証"""
    
    @staticmethod
    def request_email_identification() -> Optional[str]:
        """
        メールアドレスによる識別を要求します。
        
        Returns:
            Optional[str]: 入力されたメールアドレス、またはNone
        """
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔐 学習履歴の継続保存")
        
        # 既存のメールがある場合
        existing_email = st.session_state.get('user_email')
        if existing_email:
            st.sidebar.success(f"📧 認証済み: {existing_email}")
            
            col1, col2 = st.sidebar.columns(2)
            with col1:
                if st.button("変更", key="change_email"):
                    del st.session_state.user_email
                    st.rerun()
            
            with col2:
                if st.button("ログアウト", key="logout_email"):
                    EmailBasedAuth.logout()
                    st.rerun()
            
            return existing_email
        
        # メール入力フォーム
        st.sidebar.info("📱 Streamlit Cloud環境では、学習履歴を継続保存するためメールアドレスの入力をお勧めします")
        
        email = st.sidebar.text_input(
            "メールアドレス（オプション）:",
            key="email_input",
            help="学習履歴を複数デバイスで共有し、継続的に保存するために使用します"
        )
        
        if email:
            if EmailBasedAuth.validate_email(email):
                col1, col2 = st.sidebar.columns(2)
                
                with col1:
                    if st.button("✅ 保存", key="save_email"):
                        st.session_state.user_email = email
                        st.sidebar.success("メールアドレスを保存しました！")
                        st.rerun()
                
                with col2:
                    if st.button("❌ スキップ", key="skip_email"):
                        st.session_state.email_skipped = True
                        st.rerun()
            else:
                st.sidebar.error("有効なメールアドレスを入力してください")
        
        # スキップされた場合
        if st.session_state.get('email_skipped'):
            st.sidebar.warning("⚠️ 匿名モード: 履歴はブラウザセッション中のみ保存されます")
            return None
        
        return None
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        メールアドレスの簡単な検証を行います。
        
        Args:
            email (str): 検証するメールアドレス
        
        Returns:
            bool: 有効なメールアドレスの場合True
        """
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def logout() -> None:
        """
        ログアウト処理を行います。
        """
        keys_to_remove = ['user_email', 'email_skipped', 'session_tokens', 'auth_tokens', 'current_auth_token', 'browser_fingerprint']
        for key in keys_to_remove:
            if key in st.session_state:
                del st.session_state[key]
        
        # URLパラメータもクリア
        try:
            st.query_params.clear()
        except:
            pass

class StreamlitSessionManager:
    """Streamlit Cloud環境でのセッション管理メインクラス"""
    
    def __init__(self) -> None:
        """
        StreamlitSessionManagerを初期化します。
        """
        self.fingerprinter = BrowserFingerprinter()
        self.persistence = SessionPersistence()
        self.email_auth = EmailBasedAuth()
        
        # 初期化時にクリーンアップ実行
        self.persistence.cleanup_expired_tokens()
        
        # データベース連携の初期化
        self._initialize_database()
    
    def _initialize_database(self) -> None:
        """
        データベース連携を初期化します。
        """
        self.db_adapter = None  # 遅延初期化
    
    def _get_database_adapter(self):
        """
        データベースアダプターを遅延初期化で取得します。
        
        Returns:
            DatabaseAdapter or None: データベースアダプター、またはNone
        """
        if self.db_adapter is None:
            try:
                from modules.database_adapter_v3 import DatabaseAdapterV3
                self.db_adapter = DatabaseAdapterV3()
                logger.info("データベースアダプターを初期化しました")
            except Exception as e:
                logger.warning(f"データベースアダプターの初期化に失敗しました: {e}")
                self.db_adapter = None
        
        return self.db_adapter
    
    def get_user_session(self) -> UserSession:
        """
        現在のユーザーセッションを取得します。
        
        Returns:
            UserSession: 現在のユーザーセッション
        """
        try:
            # 既存のセッションがある場合は再利用
            if 'current_user_session' in st.session_state:
                existing_session = st.session_state.current_user_session
                if existing_session and isinstance(existing_session, UserSession):
                    # セッションの有効性をチェック
                    if (existing_session.last_active and 
                        (datetime.now() - existing_session.last_active).total_seconds() < 3600):  # 1時間以内
                        logger.debug(f"Reusing existing session: {existing_session.user_id}")
                        return existing_session
            
            # 1. パスワード認証トークンを確認（最優先）
            session_from_auth = self._try_password_auth()
            if session_from_auth:
                st.session_state.current_user_session = session_from_auth
                return session_from_auth
            
            # 2. URLパラメータからセッショントークンを確認
            session_from_token = self._try_session_token_auth()
            if session_from_token:
                st.session_state.current_user_session = session_from_token
                return session_from_token
            
            # 3. メールベース認証を試行
            session_from_email = self._try_email_auth()
            if session_from_email:
                st.session_state.current_user_session = session_from_email
                return session_from_email
            
            # 4. ブラウザフィンガープリントを使用
            session_from_fingerprint = self._try_fingerprint_auth()
            if session_from_fingerprint:
                st.session_state.current_user_session = session_from_fingerprint
                return session_from_fingerprint
            
            # 5. フォールバック: 新規セッション作成（制限付き）
            fallback_session = self._create_fallback_session()
            st.session_state.current_user_session = fallback_session
            return fallback_session
            
        except Exception as e:
            logger.error(f"Error getting user session: {e}")
            fallback_session = self._create_fallback_session()
            st.session_state.current_user_session = fallback_session
            return fallback_session
    
    def _try_password_auth(self) -> Optional[UserSession]:
        """
        パスワード認証による認証を試行します。
        
        Returns:
            Optional[UserSession]: 認証成功時のセッション、またはNone
        """
        try:
            # 現在の認証トークンを確認
            current_auth_token = st.session_state.get('current_auth_token')
            if not current_auth_token:
                logger.debug("No current_auth_token found in session state")
                return None
            
            # 認証データを復元
            auth_data = self.persistence.load_auth_from_token(current_auth_token)
            if not auth_data:
                logger.debug("Failed to load auth data from token")
                return None
            
            # UserProfileオブジェクトを復元
            user_profile_data = auth_data.get('user_profile')
            if not user_profile_data:
                logger.debug("No user_profile in auth data")
                return None
            
            # UserSessionを作成
            session = UserSession(
                user_id=auth_data['user_id'],
                identification_method=IdentificationMethod.PASSWORD_AUTH,
                created_at=datetime.fromisoformat(auth_data['created_at']),
                last_active=datetime.now(),
                metadata={
                    'auth_token': current_auth_token,
                    'authenticated_at': auth_data['created_at']
                },
                is_persistent=True,
                is_authenticated=True,
                user_profile=user_profile_data
            )
            
            logger.info(f"Password auth successful for user: {auth_data['user_id']}")
            return session
            
        except Exception as e:
            logger.debug(f"Password auth failed: {e}")
            return None
    
    def _try_session_token_auth(self) -> Optional[UserSession]:
        """
        セッショントークンによる認証を試行します。
        
        Returns:
            Optional[UserSession]: 認証成功時のセッション、またはNone
        """
        try:
            # URLパラメータからトークンを取得
            query_params = st.query_params
            token = query_params.get('session_token', None)
            
            if not token:
                return None
            
            # トークンからセッション情報を復元
            token_data = self.persistence.load_session_from_token(token)
            if token_data:
                user_id = token_data['user_id']
                session_data = token_data.get('session_data', {})
                
                return UserSession(
                    user_id=user_id,
                    identification_method=IdentificationMethod.SESSION_TOKEN,
                    created_at=datetime.fromisoformat(token_data['created_at']),
                    last_active=datetime.now(),
                    metadata=session_data,
                    is_persistent=True,
                    is_authenticated=False
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"Session token auth failed: {e}")
            return None
    
    def _try_email_auth(self) -> Optional[UserSession]:
        """
        メールベース認証を試行します。
        
        Returns:
            Optional[UserSession]: 認証成功時のセッション、またはNone
        """
        try:
            email = self.email_auth.request_email_identification()
            if email:
                # メールアドレスをユーザーIDとして使用
                user_id = hashlib.sha256(email.encode()).hexdigest()[:16]
                
                session = UserSession(
                    user_id=user_id,
                    identification_method=IdentificationMethod.EMAIL,
                    created_at=datetime.now(),
                    last_active=datetime.now(),
                    metadata={'email': email},
                    is_persistent=True,
                    is_authenticated=False
                )
                
                # セッショントークンを生成して永続化
                token = self.persistence.save_session_token(user_id, {'email': email})
                session.metadata['session_token'] = token
                
                return session
            
            return None
            
        except Exception as e:
            logger.debug(f"Email auth failed: {e}")
            return None
    
    def _try_fingerprint_auth(self) -> Optional[UserSession]:
        """
        ブラウザフィンガープリントによる認証を試行します。
        
        Returns:
            Optional[UserSession]: 認証成功時のセッション、またはNone
        """
        try:
            fingerprint = self.fingerprinter.generate_fingerprint()
            
            # 既存のセッションがある場合は再利用
            if 'current_fingerprint_session' in st.session_state:
                existing_session = st.session_state.current_fingerprint_session
                if (existing_session and 
                    existing_session.metadata.get('fingerprint') == fingerprint):
                    logger.debug(f"Reusing existing fingerprint session: {fingerprint}")
                    return existing_session
            
            # フィンガープリントの安定性をチェック
            is_stable = self.fingerprinter.is_fingerprint_stable(fingerprint)
            
            # フィンガープリント履歴を更新
            if 'fingerprint_history' not in st.session_state:
                st.session_state.fingerprint_history = []
            
            current_time = datetime.now().isoformat()
            fingerprint_history = st.session_state.fingerprint_history
            fingerprint_history.append((fingerprint, current_time))
            
            # 履歴を最新20件まで保持（削減）
            st.session_state.fingerprint_history = fingerprint_history[-20:]
            
            # 新しいセッションを作成
            session = UserSession(
                user_id=f"temp_{fingerprint}",
                identification_method=IdentificationMethod.BROWSER_FINGERPRINT,
                created_at=datetime.now(),
                last_active=datetime.now(),
                metadata={
                    'fingerprint': fingerprint,
                    'is_stable': is_stable,
                    'fingerprint_method': 'browser_characteristics',
                    'is_temporary': True  # 一時的なセッションであることを明示
                },
                is_persistent=is_stable,
                is_authenticated=False
            )
            
            # セッション状態に保存
            st.session_state.current_fingerprint_session = session
            
            logger.debug(f"Created new fingerprint session: {fingerprint}")
            return session
            
        except Exception as e:
            logger.error(f"Fingerprint auth failed: {e}")
            return None
    
    def _create_fallback_session(self) -> UserSession:
        """
        フォールバックセッションを作成します。
        
        Returns:
            UserSession: フォールバックセッション
        """
        # 既存のフォールバックセッションがある場合は再利用
        if 'fallback_session_id' in st.session_state:
            existing_fallback_id = st.session_state.fallback_session_id
            if existing_fallback_id and existing_fallback_id.startswith('temp_'):
                logger.debug(f"Reusing existing fallback session: {existing_fallback_id}")
                return UserSession(
                    user_id=existing_fallback_id,
                    identification_method=IdentificationMethod.BROWSER_FINGERPRINT,
                    created_at=datetime.now(),
                    last_active=datetime.now(),
                    metadata={
                        'fallback': True,
                        'is_temporary': True,
                        'warning': 'Temporary session - history may not persist',
                        'reused': True
                    },
                    is_persistent=False,
                    is_authenticated=False
                )
        
        # 新しいフォールバックセッションを作成
        fallback_id = f"temp_{str(uuid.uuid4())[:16]}"
        st.session_state.fallback_session_id = fallback_id
        
        logger.debug(f"Created new fallback session: {fallback_id}")
        return UserSession(
            user_id=fallback_id,
            identification_method=IdentificationMethod.BROWSER_FINGERPRINT,
            created_at=datetime.now(),
            last_active=datetime.now(),
            metadata={
                'fallback': True,
                'is_temporary': True,
                'warning': 'Temporary session - history may not persist'
            },
            is_persistent=False,
            is_authenticated=False
        )
    
    def authenticate_user(self, user_profile: Dict[str, Any]) -> bool:
        """
        ユーザーを認証状態にします。
        
        Args:
            user_profile (Dict[str, Any]): ユーザープロフィール
        
        Returns:
            bool: 認証が成功した場合True
        """
        try:
            user_id = user_profile.get('user_id')
            if not user_id:
                return False
            
            # 認証トークンを生成
            auth_token = self.persistence.save_auth_token(user_id, user_profile)
            if not auth_token:
                return False
            
            # セッション状態に保存
            st.session_state.user_authenticated = True
            st.session_state.user_profile = user_profile
            st.session_state.current_auth_token = auth_token
            
            logger.info(f"User authenticated: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return False
    
    def logout_user(self) -> bool:
        """
        ユーザーをログアウトします。
        
        Returns:
            bool: ログアウトが成功した場合True
        """
        try:
            # セッション状態をクリア
            auth_keys = [
                'user_authenticated', 'user_profile', 'current_auth_token',
                'auth_tokens', 'user_email', 'email_skipped'
            ]
            
            for key in auth_keys:
                if key in st.session_state:
                    del st.session_state[key]
            
            logger.info("User logged out")
            return True
            
        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            return False
    
    def update_session_activity(self, session: UserSession) -> None:
        """
        セッションアクティビティを更新します。
        
        Args:
            session (UserSession): 更新するセッション
        """
        try:
            session.last_active = datetime.now()
            
            # 永続化が必要な場合はトークンを更新
            if session.is_persistent:
                if 'session_token' in session.metadata:
                    token = session.metadata['session_token']
                    session_tokens = st.session_state.get('session_tokens', {})
                    if token in session_tokens:
                        session_tokens[token]['last_active'] = datetime.now().isoformat()
                
                if session.is_authenticated and 'auth_token' in session.metadata:
                    token = session.metadata['auth_token']
                    auth_tokens = st.session_state.get('auth_tokens', {})
                    if token in auth_tokens:
                        auth_tokens[token]['last_active'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
    
    def get_session_info_display(self, session: UserSession) -> Dict[str, str]:
        """
        セッション情報の表示用データを取得します。
        
        Args:
            session (UserSession): セッション情報
        
        Returns:
            Dict[str, str]: 表示用のセッション情報
        """
        # 一時的なセッションかどうかを判定
        is_temporary = session.user_id.startswith('temp_') or session.metadata.get('is_temporary', False)
        
        info = {
            'ユーザーID': session.user_id[:8] + '...',
            '認証方法': {
                IdentificationMethod.PASSWORD_AUTH: 'パスワード認証',
                IdentificationMethod.EMAIL: 'メールアドレス',
                IdentificationMethod.BROWSER_FINGERPRINT: 'ブラウザ特性',
                IdentificationMethod.SESSION_TOKEN: 'セッショントークン',
                IdentificationMethod.URL_PARAMETER: 'URLパラメータ'
            }.get(session.identification_method, '不明'),
            '永続化': '有効' if session.is_persistent else '無効',
            '認証状態': '認証済み' if session.is_authenticated else '未認証',
            '最終アクティブ': session.last_active.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 一時的なセッションの場合は警告を追加
        if is_temporary:
            info['セッションタイプ'] = '一時的（履歴は保存されません）'
        
        if session.identification_method == IdentificationMethod.EMAIL:
            info['メールアドレス'] = session.metadata.get('email', '未設定')
        
        if session.identification_method == IdentificationMethod.PASSWORD_AUTH and session.user_profile:
            info['表示名'] = session.user_profile.get('display_name', '未設定')
            info['メールアドレス'] = session.user_profile.get('email', '未設定')
        
        if session.identification_method == IdentificationMethod.BROWSER_FINGERPRINT:
            info['安定性'] = '安定' if session.metadata.get('is_stable') else '不安定'
        
        return info
    
    def show_session_status(self, session: UserSession) -> None:
        """
        セッション状態をサイドバーに表示します。
        
        Args:
            session (UserSession): 表示するセッション
        """
        with st.sidebar.expander("🔐 セッション情報", expanded=False):
            info = self.get_session_info_display(session)
            
            for key, value in info.items():
                st.text(f"{key}: {value}")
            
            # 一時的なセッションの場合は特別な警告を表示
            is_temporary = session.user_id.startswith('temp_') or session.metadata.get('is_temporary', False)
            if is_temporary:
                st.error("🚫 一時セッション: 学習履歴は保存されません。ログインして永続的なセッションを作成してください。")
            elif not session.is_persistent:
                st.warning("⚠️ 一時セッション: ブラウザを閉じると履歴が失われる可能性があります")
            
            # 認証状態に応じたアクション
            if session.is_authenticated:
                st.success("✅ 認証済みユーザー")
                if st.button("ログアウト", key="session_logout"):
                    self.logout_user()
                    st.rerun()
            else:
                st.info("ℹ️ ゲストユーザー")
                if st.button("ログイン", key="session_login"):
                    st.switch_page("pages/07_ユーザー管理.py")

# シングルトンインスタンス
session_manager = StreamlitSessionManager() 