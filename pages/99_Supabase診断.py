"""
Supabase接続診断ページ
"""

import streamlit as st
import os
from datetime import datetime

st.set_page_config(page_title="Supabase診断", page_icon="🔍")

st.title("🔍 Supabase接続診断")
st.markdown("自由記述ページで「ローカルファイル使用」と表示される原因を診断します。")

# 診断開始
st.header("📋 診断結果")

# 1. Streamlit Secrets確認
st.subheader("1. Streamlit Secrets確認")
try:
    supabase_url = st.secrets.get("SUPABASE_URL")
    supabase_key = st.secrets.get("SUPABASE_ANON_KEY")
    
    if supabase_url and supabase_key:
        st.success("✅ Streamlit Secrets: 正常に設定されています")
        st.write(f"**SUPABASE_URL**: {supabase_url}")
        st.write(f"**SUPABASE_ANON_KEY**: {supabase_key[:20]}...")
    else:
        st.error("❌ Streamlit Secrets: 設定が不完全です")
        st.write(f"SUPABASE_URL: {bool(supabase_url)}")
        st.write(f"SUPABASE_ANON_KEY: {bool(supabase_key)}")
        
except Exception as e:
    st.error(f"❌ Streamlit Secrets読み込みエラー: {e}")
    supabase_url = None
    supabase_key = None

# 2. Supabaseライブラリ確認
st.subheader("2. Supabaseライブラリ確認")
try:
    from supabase import create_client
    st.success("✅ supabase-py ライブラリ: 正常にインポートされています")
    
    # 3. 接続テスト
    st.subheader("3. Supabase接続テスト")
    if supabase_url and supabase_key:
        try:
            client = create_client(supabase_url, supabase_key)
            st.success("✅ Supabaseクライアント: 正常に作成されました")
            
            # 4. データベーステスト
            st.subheader("4. データベースアクセステスト")
            try:
                # exercise_typesテーブルのテスト（新スキーマ）
                result = client.table('exercise_types').select('exercise_type_id, display_name').limit(5).execute()
                st.success(f"✅ exercise_types テーブル: 正常にアクセスできます ({len(result.data)}件取得)")
                
                # 取得したデータを表示
                if result.data:
                    st.write("**取得されたexercise_types:**")
                    for item in result.data:
                        st.write(f"- ID: {item['exercise_type_id']}, 名前: {item['display_name']}")
                
            except Exception as e:
                st.error(f"❌ データベースアクセスエラー: {e}")
                
        except Exception as e:
            st.error(f"❌ Supabase接続エラー: {e}")
            
    else:
        st.warning("⚠️ Supabase設定が不完全のため接続テストをスキップしました")
        
except ImportError as e:
    st.error(f"❌ supabase-py インポートエラー: {e}")

# 6. DatabaseAdapter診断
st.subheader("6. DatabaseAdapter診断")
try:
    from modules.database_adapter_v3 import DatabaseAdapterV3
    
    db_adapter = DatabaseAdapterV3()
    is_available = db_adapter.is_available()
    
    if is_available:
        st.success("✅ DatabaseAdapter: 正常に動作しています")
        
        # 状態情報取得
        try:
            status = db_adapter.get_database_status()
            st.write("**データベース状態:**")
            for key, value in status.items():
                st.write(f"- {key}: {value}")
                
        except Exception as e:
            st.error(f"❌ DatabaseAdapter状態取得エラー: {e}")
            
    else:
        st.error("❌ DatabaseAdapter: 利用不可状態です")
        st.write("これが「ローカルファイル使用」と表示される原因です。")
        
except Exception as e:
    st.error(f"❌ DatabaseAdapterインポートエラー: {e}")

# 診断サマリー
st.header("📊 診断サマリー")

# 環境変数確認
env_vars = []
try:
    env_vars = [
        f"SUPABASE_URL: {os.environ.get('SUPABASE_URL', 'NOT SET')[:30]}...",
        f"SUPABASE_ANON_KEY: {os.environ.get('SUPABASE_ANON_KEY', 'NOT SET')[:20]}..."
    ]
except:
    env_vars = ["環境変数確認エラー"]

st.write("**環境変数:**")
for var in env_vars:
    st.write(f"- {var}")

# 推奨アクション
st.header("🔧 推奨アクション")
st.markdown("""
1. **Streamlitアプリを再起動**
   - 設定変更後は必ずアプリを再起動してください
   
2. **Supabaseプロジェクトの状態確認**
   - Supabaseダッシュボードでプロジェクトがアクティブか確認
   - データベースが正常に動作しているか確認
   
3. **ネットワーク接続確認**
   - インターネット接続が正常か確認
   - ファイアウォール設定の確認
   
4. **依存関係の確認**
   - `pip install supabase` でライブラリが正しくインストールされているか確認
""")

# 現在時刻を表示
st.write(f"**診断実行時刻**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}") 