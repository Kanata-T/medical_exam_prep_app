import streamlit as st
from google import genai
from google.genai import types
from google.api_core import retry
import os
import logging
import json

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

def validate_interview_inputs(question, answer):
    """
    面接入力値を検証します。
    """
    if not question or len(question.strip()) < 5:
        return False, "面接質問が設定されていません。"
    if not answer or len(answer.strip()) < 10:
        return False, "回答を入力してください（最低10文字）。"
    if len(answer.strip()) > 2000:
        return False, "回答が長すぎます（2000文字以内）。"
    return True, ""

def get_interview_question_categories():
    """
    面接質問のカテゴリとサンプルを返します。
    """
    return {
        "自己PR・志望動機": ["なぜ当院を志望されたのですか？", "あなたの強みを教えてください。", "将来どのような医師になりたいですか？"],
        "医師としての倫理観": ["患者さんとのコミュニケーションで心がけていることはありますか？", "医師として最も大切だと思うことは何ですか？", "チーム医療における医師の役割をどう考えますか？"],
        "困難・ストレス対処": ["これまでで最も困難だった経験とその対処法を教えてください。", "ストレスをどのように解消していますか？", "意見の合わない同僚とどう接しますか？"],
        "専門性・学習意欲": ["興味のある診療科とその理由を教えてください。", "最新の医療技術についてどう思いますか？", "生涯学習をどのように継続していく予定ですか？"]
    }

def get_interview_scoring_prompt(question: str, answer: str) -> str:
    """単発の面接回答を評価するためのプロンプトを生成する"""
    return f"""
# 指示
あなたはプロの採用面接官です。以下の面接のやり取りについて、評価と具体的な改善点をフィードバックしてください。

# 評価のルール
- 評価項目は「論理性」「具体性」「自己理解」「コミュニケーション能力」「熱意」の5つです。
- 各項目を5段階評価（1〜5点）で採点し、必ず `【評価スコア】` の形式でまとめてください。
- 良かった点と改善点を、それぞれ具体的に指摘してください。
- 改善点は、単なるダメ出しではなく、応募者が次につながるような建設的なアドバイスを心がけてください。
- 全体を通して、厳しすぎず、丁寧かつプロフェッショナルな口調を維持してください。

---

# 面接のやり取り
**面接官からの質問:**
「{question}」

**応募者の回答:**
「{answer}」

---

# 評価とフィードバック
"""

@retry.Retry()
def generate_interview_question(category: str = "all") -> dict:
    """AIを用いて面接の質問を1つ生成する"""
    prompt = f"""
あなたは日本の医療機関における採用面接官です。
医学生や研修医志望者に対して行う、効果的な面接質問を1つだけ生成してください。
質問カテゴリ: {category if category != 'all' else '総合的な質問'}
応募者の思考力、倫理観、コミュニケーション能力を測れるような、深みのある質問を期待します。
質問のみを簡潔に提示してください。
"""
    try:
        client = _get_gemini_client()
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        question_text = response.text.strip().replace('「', '').replace('」', '')
        return {"question": question_text, "category": category}
    except Exception as e:
        logger.error(f"Error generating interview question: {e}")
        return {"error": str(e)}

def score_interview_answer_stream(question: str, answer: str):
    """単発の面接回答を評価し、結果をストリーミングで返す"""
    prompt = get_interview_scoring_prompt(question, answer)
    try:
        client = _get_gemini_client()
        stream = client.models.generate_content_stream(model=GEMINI_MODEL, contents=prompt)
        return stream
    except Exception as e:
        return _create_error_stream(e)

def get_interview_tips() -> dict:
    """面接対策のヒントを返す"""
    return {
        "基本的な心構え": ["結論から話すことを意識する（PREP法）", "身だしなみを整え、清潔感を出す", "明るい表情とハキハキした声で話す", "正しい敬語を使う", "逆質問は、企業への理解度と熱意を示すチャンスです。事前にいくつか準備しておきましょう。"],
        "回答の構成（STARメソッド）": ["**S (Situation):** 状況 - いつ、どこでの出来事か", "**T (Task):** 課題 - どのような目標や課題があったか", "**A (Action):** 行動 - その課題に対して具体的に何をしたか", "**R (Result):** 結果 - 行動の結果どうなったか、何を学んだか"]
    }

def conduct_interview_session_stream(history: list[dict]):
    """模擬面接セッションを実行し、面接官の次の発言をストリーミングで返す"""
    system_instruction = """
あなたは、プロの採用面接官です。これから初期研修採用試験において、応募者との模擬面接セッションを行います。
以下の指示と会話履歴に基づいて、面接官として��然で適切な発言を生成してください。

【面接の進行フロー】
1.  **開始**: 会話履歴が空の場合、まず応募者に挨拶し、簡単な自己紹介（例：「本日はよろしくお願いします。面接官のAIです。」）をした後、最初の質問を投げかけてください。最初の質問は自己紹介や志望動機など、基本的なものから始めてください。
2.  **質疑応答**: 応募者の回答に対して、1〜2回深掘りの質問をしてください。深掘りが終わったら、次のテーマの質問に移ってください。「では次に、〇〇についてお伺いします。」のように、話題の転換を明確にすると自然です。
3.  **セッションの終了**: 合計で約10分程度を目安とし、全体で4〜5つの質問と回答のやり取りが完了したら、面接を終了する旨を伝えてください。（例：「以上で面接は終了です。本日はありがとうございました。」）
4.  **総合評価**: 面接終了の挨拶の後、必ず"---"という区切り線を入れ、その下に【総合フィードバック】という見出しで、セッション全体を通しての応募者の回答に対する詳細な評価を記述してください。評価の観点は、「論理性」「具体性」「自己理解��「コミュニケーション能力」「熱意」などを含め、良かった点と改善点を具体的に指摘してください。

【発言のルール】
- あなたの発言は、一度の応答で「挨拶→最初の質問」や「次の質問」や「終了の挨拶→総合評価」のように、1つのフェーズのみとしてください。複数のフェーズを一度に返さないでください。
- 応募者の回答をオウム返しに繰り返すのではなく、自然な相槌（「なるほど」「ありがとうございます」など）を打ってから質問に移ってください。
- 厳しすぎず、丁寧かつプロフェッショナルな口調を維持してください。
"""
    
    try:
        client = _get_gemini_client()
        chat = client.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(system_instruction=system_instruction)
        )
        
        # 履歴を再構築
        for item in history[:-1]: # 最後のユーザーメッセージは含めない
            chat.send_message(item["content"])

        # 最後のユーザーメッセージを送信してストリーム応答を取得
        last_message = history[-1]["content"] if history else "面接を開始してください。"
        stream = chat.send_message_stream(last_message)
        return stream

    except Exception as e:
        return _create_error_stream(e)
