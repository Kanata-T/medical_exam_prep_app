import streamlit as st
from google import genai
from google.genai import types
from google.api_core import retry
import os
import logging

# ロガー設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 定数
GEMINI_MODEL = "gemini-2.5-flash"

def _get_gemini_client():
    """Geminiクライアントを初期化して返す"""
    try:
        api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is not configured.")
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        st.error("Gemini APIクライアントの初期化に失敗しました。APIキーの設定を確認してください。")
        st.stop()

def _create_error_stream(e: Exception):
    """エラー情報をストリーム形式で返すためのジェネレータ"""
    error_message = f"API呼び出しエラー: {e}"
    logger.error(f"An error occurred: {error_message}")
    yield error_message

@retry.Retry()
def generate_medical_question(theme: str) -> str:
    """
    指定されたテーマに基��いて、国試レベルの自由記述問題を生成します。
    """
    prompt = f"""
あなたは日本の医師国家試験の問題作成委員です。
以下のテーマについて、受験者の知識の深さと応用力を測るための自由記述問題を1つ作成してください。
問題は、原因、病態生理、症状、検査所見、診断、治療法など、総合的な知識を問う形式にしてください。
テーマ: 「{theme}」
問題文のみを簡潔に出力してください。
"""
    try:
        client = _get_gemini_client()
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error generating medical question: {e}")
        return "問題の生成中にエラーが発生しました。"

def score_medical_answer_stream(question: str, answer: str):
    """
    ユーザーの回答を評価し、フィードバックと模範解答をストリーミングで返します。
    """
    prompt = f"""
# 指示
あなたは経験豊富な指導医です。医学生または研修医が記述した以下の回答を、医師国家試験の採点基準に沿って厳格に評価・添削してください。

# 採点基準
- **医学的正確性**: 記述���容に誤りがないか。
- **網羅性**: 問われている内容に対して、重要なキーワードや概念（原因、症状、検査、治療など）が過不足なく含まれているか。
- **論理構成**: 文章の構成が論理的で、分かりやすいか。
- **専門用語の適切性**: 専門用語を正しく使用できているか。

# 出力形式
必ず以下の形式で、マークダウンを使用して出力してください。

## 評価スコア
- **医学的正確性**: [1-5]点
- **網羅性**: [1-5]点
- **論理構成**: [1-5]点
- **総合評価**: [S, A, B, C, D のいずれか]

## 総評
[全体的な評価を簡潔に記述]

## 良かった点
- [具体的に良かった点を箇条書きで記述]

## 改善点
- [具体的に改善すべき点を、なぜそうすべきかという理由と共に箇条書きで記述]

## 模範解答例
[あなたが作成した、この問題に対する理想的な模範解答を記述]

---

# 問題
{question}

# 受験者の回答
{answer}

---

# 評価とフィードバック
"""
    try:
        client = _get_gemini_client()
        stream = client.models.generate_content_stream(model=GEMINI_MODEL, contents=prompt)
        return stream
    except Exception as e:
        logger.error(f"Error scoring medical answer: {e}")
        return _create_error_stream(e)

@retry.Retry()
def generate_random_medical_theme() -> str:
    """
    AIが国試レベルの自由記述問題のテーマをランダムに1つ生成します。
    """
    prompt = """
あなたは日本の医師国家試験の問題作成委員です。
医学生や研修医の知識を試すのに適した、自由記述問題のテーマを1つだけ提案してください。
テーマは、特定の疾患名（例：クローン病）、病態（例：DIC）、治療法（例：免疫チェックポイント阻害薬）など、医学的に意義のあるものにしてください。
テーマ名のみを簡潔に出力してください。
"""
    try:
        client = _get_gemini_client()
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error generating random medical theme: {e}")
        return "ランダムなテーマの生成中にエラーが発生しました。"

def get_default_themes():
    """
    デフォルトの出題テーマをリストで返します。
    """
    return [
        "多発性骨髄腫",
        "急性腎不全",
        "心筋梗塞",
        "脳梗塞",
        "糖尿病性ケトアシドー���ス",
        "敗血症性ショック",
        "間質性肺炎",
        "大腿骨頸部骨折後のリハビリテーション"
    ]
