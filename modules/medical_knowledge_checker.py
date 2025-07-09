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
    指定されたテーマに基いて、医学部採用試験形式の自由記述問題を生成します。
    """
    import random
    
    # 問題パターンの定義
    question_patterns = [
        {
            "type": "basic_knowledge",
            "template": "{theme}について知っていることを述べよ。（症状、検査、治療など）",
            "weight": 3
        },
        {
            "type": "patient_explanation", 
            "template": "{theme}について、小学6年生にもわかるように説明書を作れ。",
            "weight": 2
        },
        {
            "type": "clinical_assessment",
            "template": "{theme}の患者に対するassessmentとplanを作れ。なお、planについては治療計画、検査計画、患者教育計画について述べよ。",
            "weight": 2
        },
        {
            "type": "differential_diagnosis",
            "template": "{theme}を疑う症例において、鑑別疾患と鑑別に必要な検査について述べよ。",
            "weight": 2
        },
        {
            "type": "examination_procedure",
            "template": "{theme}が疑われる患者に対して、どのような診察や検査を行うか述べよ。",
            "weight": 2
        },
        {
            "type": "treatment_plan",
            "template": "{theme}の治療方針について、薬物療法、非薬物療法、合併症対策を含めて述べよ。",
            "weight": 2
        },
        {
            "type": "diagnostic_criteria",
            "template": "{theme}の診断基準と、一つ例を挙げて具体的な治療法を記載せよ。",
            "weight": 1
        },
        {
            "type": "complications",
            "template": "{theme}の治療における合併症とその対策について述べよ。",
            "weight": 1
        }
    ]
    
    # 重み付きランダム選択
    weights = [pattern["weight"] for pattern in question_patterns]
    selected_pattern = random.choices(question_patterns, weights=weights)[0]
    
    # AIに詳細な問題を生成させる
    prompt = f"""
あなたは医学部採用試験の問題作成委員です。
以下のテーマと形式に基づいて、実際の医学部採用試験レベルの自由記述問題を作成してください。

テーマ: {theme}
基本形式: {selected_pattern['template'].format(theme=theme)}
問題タイプ: {selected_pattern['type']}

以下の要件を満たす問題を作成してください：
1. 医学部採用試験の実際の出題レベルに合わせる
2. 医師として必要な実践的知識を問う
3. 簡潔で明確な問題文にする
4. 適切な分量の回答が期待できる問題にする

問題タイプ別の追加要件：
- basic_knowledge: 病態生理、症状、検査、治療を総合的に問う
- patient_explanation: 専門用語を避け、わかりやすい説明を求める
- clinical_assessment: 実際の臨床現場での判断能力を問う
- differential_diagnosis: 鑑別診断の思考プロセスを問う
- examination_procedure: 診察の手順や検査の選択理由を問う
- treatment_plan: 治療の優先順位や選択理由を問う
- diagnostic_criteria: 具体的な診断基準や数値を含める
- complications: 予防策や早期発見のポイントを含める

問題文のみを簡潔に出力してください。
"""
    
    try:
        client = _get_gemini_client()
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error generating medical question: {e}")
        # フォールバック：基本的な問題形式を使用
        return selected_pattern['template'].format(theme=theme)

def score_medical_answer_stream(question: str, answer: str):
    """
    ユーザーの回答を医学部採用試験の基準で評価し、フィードバックと模範解答をストリーミングで返します。
    """
    prompt = f"""
# 指示
あなたは医学部採用試験の採点委員です。医師として実際に働く上で必要な知識と判断力を評価してください。
以下の回答を、医学部採用試験の採点基準に沿って厳格に評価・添削してください。

# 採点基準（各10点満点）
- **臨床的正確性**: 医学的事実の正確性と、実際の臨床現場での適用可能性
- **実践的思考**: 臨床現場での判断力と問題解決能力
- **包括性**: 問われている内容に対する網羅性と体系的な理解
- **論理構成**: 文章の構成が論理的で、医師として適切な表現力があるか

# 評価のポイント
- 国試レベルを超えた実践的知識
- 患者安全を考慮した判断
- チーム医療での連携を意識した内容
- Evidence-based medicineに基づく記述
- 患者・家族への配慮

# 出力形式
必ず以下の形式で、マークダウンを使用して出力してください。

## 📊 評価スコア
```json
{{"臨床的正確性": [1-10の整数], "実践的思考": [1-10の整数], "包括性": [1-10の整数], "論理構成": [1-10の整数]}}
```

## 🎯 総合評価
**レベル**: [A: 90点以上(優秀), B: 80-89点(良好), C: 70-79点(合格), D: 60-69点(要改善), E: 59点以下(不合格)] 

**総評**: [医学部採用試験としての全体的な評価を記述]

## ✅ 優れている点
- [具体的に優れていた点を箇条書きで記述]

## 📝 改善が必要な点
- [具体的に改善すべき点を、臨床現場での重要性と合わせて箇条書きで記述]

## 💡 臨床での活用ポイント
- [実際の臨床現場でどう活かすべきかのアドバイス]

## 📚 模範解答例
[医学部採用試験レベルの、実践的で包括的な模範解答を記述]

## 🔍 追加学習のポイント
- [さらに学習を深めるべき領域や参考となる分野]

---

# 問題
{question}

# 受験者の回答
{answer}

---

# 医学部採用試験レベルでの評価とフィードバック
"""
    try:
        client = _get_gemini_client()
        stream = client.models.generate_content_stream(model=GEMINI_MODEL, contents=prompt)
        return stream
    except Exception as e:
        logger.error(f"Error scoring medical answer: {e}")
        return _create_error_stream(e)

@retry.Retry()
def generate_random_medical_theme(avoid_themes: list = None) -> str:
    """
    AIが医学部採用試験レベルの自由記述問題のテーマをランダムに1つ生成します。
    
    Args:
        avoid_themes (list): 避けるべきテーマのリスト（過去に出題されたテーマなど）
    
    Returns:
        str: 生成されたテーマ
    """
    avoid_themes_text = ""
    if avoid_themes and len(avoid_themes) > 0:
        avoid_themes_text = f"""
**重要な制約**: 以下のテーマは最近出題されているため、必ず避けてください：
{', '.join(avoid_themes)}

上記のテーマとは異なる、新しいテーマを提案してください。
"""
    
    prompt = f"""
あなたは医学部採用試験の問題作成委員です。
医学部採用試験の自由記述問題で実際に出題される可能性の高い、医学的テーマを1つだけ提案してください。

{avoid_themes_text}

# 医学部採用試験の出題傾向
- 臨床現場で遭遇頻度の高い疾患
- 研修医として知っておくべき重要な病態
- 診断・治療に関する実践的知識が問われる疾患
- 患者説明や同僚との情報共有が必要な疾患

# 出題されやすい分野例
- 内科系：血液疾患、腎疾患、呼吸器疾患、消化器疾患、内分泌疾患
- 外科系：外傷、腫瘍、血管疾患
- 小児科：先天性疾患、感染症、発達障害
- 産婦人科：妊娠合併症、生殖器疾患
- 整形外科：骨折、関節疾患
- 救急：ショック、中毒、外傷

# 要件
1. 疾患名は正確な医学用語を使用
2. 医学部採用試験で実際に出題される可能性が高いもの
3. 単一の明確な疾患・病態名
4. 研修医レベルで理解すべき重要度の高いもの

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
    医学部採用試験で頻出のデフォルト出題テーマをリストで返します。
    実際の過去問に基づいた実践的なテーマを収録。
    """
    return [
        # 内科系（頻出）
        "多発性骨髄腫",
        "急性腎不全", 
        "ネフローゼ症候群",
        "慢性骨髄性白血病",
        "再生不良性貧血",
        "COPD",
        "C型肝炎",
        "プロラクチノーマ",
        
        # 外科・外傷系
        "胆石性閉塞性胆管炎",
        "下肢閉塞性動脈硬化症",
        "マルファン症候群",
        "乳癌",
        "心臓粘液腫",
        
        # 小児科系
        "川崎病",
        "神経発達障害",
        "新生児マススクリーニング",
        
        # 産婦人科系
        "双体妊娠",
        
        # 整形外科系
        "大腿骨頸部骨折",
        "大腿骨頭置換術",
        
        # 循環器系
        "心筋梗塞",
        "不整脈",
        
        # その他重要疾患
        "敗血症性ショック",
        "糖尿病性ケトアシドース"
    ]
