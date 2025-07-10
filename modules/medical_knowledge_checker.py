import streamlit as st
import google.genai as genai
from google.genai import types
from google.api_core import retry
import os
import logging
from modules.utils import safe_api_call, score_with_retry_stream

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
    リトライ機能付きで503エラーなどに対応。
    """
    # リトライ機能付きの採点関数を定義
    def _score_medical_internal():
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
            raise e
    
    # リトライ機能付きでストリーミング実行
    try:
        yield from score_with_retry_stream(_score_medical_internal)
    except Exception as e:
        # 最終的にエラーが発生した場合
        logger.error(f"Final error in score_medical_answer_stream: {e}")
        yield from _create_error_stream(e)

def _is_theme_similar(theme1: str, theme2: str) -> bool:
    """
    2つのテーマが類似しているかをチェックします。
    
    Args:
        theme1 (str): 比較するテーマ1
        theme2 (str): 比較するテーマ2
    
    Returns:
        bool: 類似している場合True
    """
    # 正規化（空白除去、小文字化）
    t1 = theme1.replace(" ", "").replace("　", "").lower()
    t2 = theme2.replace(" ", "").replace("　", "").lower()
    
    # 完全一致
    if t1 == t2:
        return True
    
    # 部分一致（より短い方が長い方に含まれる場合）
    if len(t1) >= 3 and len(t2) >= 3:  # 3文字以上の場合のみ部分一致を検査
        if t1 in t2 or t2 in t1:
            return True
    
    # 類似パターンの定義
    similar_patterns = [
        ["敗血症", "敗血症性ショック"],
        ["心筋梗塞", "急性心筋梗塞", "心筋梗塞症"],
        ["腎不全", "急性腎不全", "慢性腎不全"],
        ["肺炎", "誤嚥性肺炎", "細菌性肺炎"],
        ["糖尿病", "糖尿病の診断基準", "糖尿病性ケトアシドース", "糖尿病の三大合併症"],
        ["骨折", "大腿骨頸部骨折", "橈骨遠位端骨折", "椎体骨折"],
        ["乳癌", "乳癌の治療法"],
        ["白血病", "急性骨髄性白血病", "慢性骨髄性白血病", "急性前骨髄球性白血病"]
    ]
    
    # 類似パターンでのチェック
    for pattern in similar_patterns:
        if theme1 in pattern and theme2 in pattern:
            return True
    
    return False

@retry.Retry()
def generate_random_medical_theme(avoid_themes: list = None) -> str:
    """
    AIが医学部採用試験レベルの自由記述問題のテーマをランダムに1つ生成します。
    
    Args:
        avoid_themes (list): 避けるべきテーマのリスト（過去に出題されたテーマなど）
    
    Returns:
        str: 生成されたテーマ
    """
    if not avoid_themes:
        avoid_themes = []
    
    max_attempts = 8  # 最大試行回数を増加
    
    for attempt in range(max_attempts):
        avoid_themes_text = ""
        if avoid_themes and len(avoid_themes) > 0:
            avoid_themes_text = f"""
**重要な制約**: 以下のテーマ及び類似するテーマは最近出題されているため、必ず避けてください：
{', '.join(avoid_themes)}

例: 「敗血症性ショック」が含まれる場合、「敗血症」「ショック」も避けてください
例: 「糖尿病の診断基準」が含まれる場合、「糖尿病」「糖尿病性ケトアシドース」も避けてください

上記のテーマとは明確に異なる、まったく新しい分野のテーマを提案してください。
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

# 出題されやすい分野例（避けるべきテーマと重複しない分野から選択）
- 内科系：感染症、免疫疾患、代謝疾患、内分泌疾患
- 外科系：腫瘍、血管疾患、外傷
- 精神科：認知症、うつ病、統合失調症
- 皮膚科：アトピー性皮膚炎、悪性黒色腫
- 眼科：緑内障、白内障、糖尿病網膜症
- 耳鼻咽喉科：突発性難聴、メニエール病
- 泌尿器科：前立腺肥大症、腎結石
- 婦人科：子宮筋腫、卵巣嚢腫

# 要件
1. 疾患名は正確な医学用語を使用
2. 医学部採用試験で実際に出題される可能性が高いもの
3. 単一の明確な疾患・病態名
4. 研修医レベルで理解すべき重要度の高いもの
5. 避けるべきテーマとは明確に異なる分野のもの

テーマ名のみを簡潔に出力してください。
"""
        
        try:
            client = _get_gemini_client()
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            generated_theme = response.text.strip()
            
            # 生成されたテーマが回避リストと類似していないかチェック
            is_similar = False
            for avoid_theme in avoid_themes:
                if _is_theme_similar(generated_theme, avoid_theme):
                    is_similar = True
                    break
            
            if not is_similar:
                return generated_theme
            else:
                logger.info(f"Generated theme '{generated_theme}' is similar to avoided themes. Retrying... (attempt {attempt + 1})")
                continue
                
        except Exception as e:
            logger.error(f"Error generating random medical theme (attempt {attempt + 1}): {e}")
            continue
    
    # 最大試行回数に達した場合のフォールバック
    logger.warning("Max attempts reached for theme generation. Using fallback theme.")
    
    # 避けるべきテーマと重複しないフォールバックテーマのリスト
    fallback_themes = [
        "緑内障", "白内障", "メニエール病", "突発性難聴", "前立腺肥大症", 
        "子宮筋腫", "卵巣嚢腫", "アトピー性皮膚炎", "悪性黒色腫", "認知症",
        "うつ病", "統合失調症", "腎結石", "尿路感染症", "甲状腺癌",
        "パーキンソン病", "筋萎縮性側索硬化症", "多発性硬化症", "てんかん"
    ]
    
    # フォールバックテーマからも類似していないものを選択
    for fallback_theme in fallback_themes:
        is_similar = False
        for avoid_theme in avoid_themes:
            if _is_theme_similar(fallback_theme, avoid_theme):
                is_similar = True
                break
        
        if not is_similar:
            return fallback_theme
    
    return "フォールバックテーマの生成中にエラーが発生しました。"

def get_default_themes():
    """
    医学部採用試験で頻出のデフォルト出題テーマをリストで返します。
    実際の過去問に基づいた実践的なテーマを収録。
    """
    return [
        # 循環器系
        "心筋梗塞",
        "不整脈",
        "心房細動",
        "狭心症",
        "大動脈解離",
        "心サルコイドーシス",
        "心アミロイドーシス",
        "重症大動脈弁狭窄症",
        "心臓リハビリテーション",
        "心臓粘液腫",
        
        # 内分泌・代謝系
        "糖尿病の診断基準",
        "糖尿病の三大合併症",
        "糖尿病性ケトアシドース",
        "Cushing症候群",
        "甲状腺機能亢進症",
        "ステロイドの副作用",
        "プロラクチノーマ",
        
        # 血液系
        "多発性骨髄腫",
        "慢性骨髄性白血病",
        "急性骨髄性白血病",
        "急性前骨髄球性白血病",
        "悪性リンパ腫",
        "再生不良性貧血",
        
        # 腎・泌尿器系
        "急性腎不全",
        "ネフローゼ症候群",
        
        # 呼吸器系
        "COPD",
        "Pancoast症候群",
        "肺癌の治療",
        "誤嚥性肺炎",
        
        # 消化器系
        "C型肝炎",
        "胆石性閉塞性胆管炎",
        "ヘリコバクターピロリ感染",
        "肝切除と乳酸値上昇",
        "腹膜炎",
        "急性胆嚢炎",
        "肝細胞癌",
        
        # 外科・外傷系
        "下肢閉塞性動脈硬化症",
        "マルファン症候群",
        "交通外傷",
        
        # 乳腺外科
        "乳癌",
        "乳癌の治療法",
        
        # 整形外科系
        "大腿骨頸部骨折",
        "大腿骨頭置換術",
        "橈骨遠位端骨折",
        "椎体骨折",
        "変形性膝関節症",
        "高齢者の骨折",
        
        # 産婦人科系
        "双体妊娠",
        "母子感染症",
        "子宮内膜症",
        "稽留流産",
        "切迫早産",
        "妊娠糖尿病",
        "胎児発育不全",
        "分娩の三要素",
        
        # 小児科系
        "川崎病",
        "神経発達障害",
        "新生児マススクリーニング",
        "小児の解熱薬使用",
        "熱性けいれん",
        
        # 救急医学
        "敗血症性ショック",
        "突然の腹痛",
        "胸痛の鑑別疾患",
        "口渇と体重減少",
        "アナフィラキシー",
        "BLS",
        
        # 麻酔科
        "全身麻酔"
    ]
