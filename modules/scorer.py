import streamlit as st
import google.genai as genai
from modules.utils import safe_api_call

def validate_exam_inputs(abstract, translation, opinion, essay, essay_theme):
    """
    採点対象の入力値を検証します。
    
    Args:
        abstract (str): 原文Abstract
        translation (str): 日本語訳
        opinion (str): 意見
        essay (str): 小論文
        essay_theme (str): 小論文テーマ
    
    Returns:
        tuple: (bool, str) - (有効?, エラーメッセージ)
    """
    if not abstract or len(abstract.strip()) < 50:
        return False, "Abstractが不足しています。"
    
    if not translation or len(translation.strip()) < 30:
        return False, "日本語訳を入力してください（最低30文字）。"
    
    if not opinion or len(opinion.strip()) < 50:
        return False, "意見を入力してください（最低50文字）。"
    
    if not essay or len(essay.strip()) < 100:
        return False, "小論文を入力してください（最低100文字）。"
    
    if not essay_theme or len(essay_theme.strip()) < 10:
        return False, "小論文テーマが設定されていません。"
    
    return True, ""

def get_scoring_prompt(abstract, translation, opinion, essay, essay_theme):
    """
    採点用プロンプトを生成します。
    
    Returns:
        str: 採点用プロンプト
    """
    return f"""あなたは医学部研修医採用試験の経験豊富な採点者です。以下の答案を厳正かつ公平に採点してください。評価は出力制限を気にせず細かく可能な限り書いてください。

【原文Abstract】
{abstract}

【受験者の回答】
■ 課題1: Abstractの日本語訳
{translation}

■ 課題2: Abstractに対する意見
{opinion}

■ 課題3: 小論文「{essay_theme}」
{essay}

【採点基準】
各項目を10点満点で評価してください。

1. **日本語訳 (10点満点)**
   - 正確性 (4点): 専門用語や文脈の理解度
   - 流暢性 (3点): 自然で読みやすい日本語
   - 完成度 (3点): 全体的なまとまりと訳し漏れの有無

2. **意見 (10点満点)**
   - 理解度 (3点): Abstractの内容を正確に把握
   - 論理性 (4点): 筋道立った議論の展開
   - 独創性 (3点): 独自の視点や深い洞察

3. **小論文 (10点満点)**
   - 構成力 (4点): 序論・本論・結論の明確性
   - 内容の充実度 (4点): 具体例や根拠の提示
   - 文章技術 (2点): 表現力と文法の正確性

【出力形式】
必ず以下の形式で出力してください：

**スコア:**
```json
{{
  "日本語訳": [1-10の整数],
  "意見": [1-10の整数],
  "小論文": [1-10の整数]
}}
```

## 総合評価
[30点満点中の得点と全体的なコメント]

## 課題1: 日本語訳の評価
**良い点:**
- [具体的な良い点を記述。どの表現や良かったかを記載してください。]

**改善点:**
- [具体的な改善点を記述。どの表現が改善すべきか。また、改善するとしたらどのようにすべきかを記載してください。]

## 課題2: 意見の評価
**良い点:**
- [具体的な良い点を記述。どの表現や良かったかを記載してください。]

**改善点:**
- [具体的な改善点を記述。どの表現が改善すべきか。また、改善するとしたらどのようにすべきかを記載してください。論理性や構成、内容の充実度などについても記載してください。
]

## 課題3: 小論文の評価
**良い点:**
- [具体的な良い点を記述。どの表現や良かったかを記載してください。]

**改善点:**
- [具体的な改善点を記述。どの表現が改善すべきか。また、改善するとしたらどのようにすべきかを記載してください。論理性や構成、内容の充実度などについても記載してください。]

## 学習アドバイス
[今後の学習に向けた具体的なアドバイス]
"""

class ScoringError(Exception):
    """採点処理専用の例外クラス"""
    pass

def score_exam_stream(abstract, translation, opinion, essay, essay_theme):
    """
    採用試験の提出物を採点し、結果をストリーミングで返す。
    
    Args:
        abstract (str): 原文Abstract
        translation (str): 日本語訳
        opinion (str): 意見  
        essay (str): 小論文
        essay_theme (str): 小論文テーマ
    
    Yields:
        採点結果のストリーミングチャンク
    """
    # 入力検証
    is_valid, error_msg = validate_exam_inputs(abstract, translation, opinion, essay, essay_theme)
    if not is_valid:
        yield type('ErrorChunk', (), {'text': f"❌ 入力エラー: {error_msg}"})()
        return
    
    try:
        client = genai.Client()
        prompt = get_scoring_prompt(abstract, translation, opinion, essay, essay_theme)
        
        # ストリーミング応答を生成
        response_stream = client.models.generate_content_stream(
            model='gemini-2.5-pro',
            contents=prompt
        )
        
        # レスポンスが有効かチェック
        if not response_stream:
            raise ScoringError("AI採点システムから応答が得られませんでした。")
        
        chunk_count = 0
        for chunk in response_stream:
            chunk_count += 1
            if hasattr(chunk, 'text') and chunk.text:
                yield chunk
            else:
                # 無効なチャンクの場合は警告を表示
                yield type('WarningChunk', (), {
                    'text': f"\n⚠️ [チャンク{chunk_count}] 応答形式が予期しない形式です。\n"
                })()
        
        # チャンクが全く受信されなかった場合
        if chunk_count == 0:
            raise ScoringError("採点結果を取得できませんでした。")
            
    except ScoringError as e:
        yield type('ErrorChunk', (), {'text': f"❌ 採点エラー: {str(e)}"})()
    except Exception as e:
        # 予期しないエラーの場合
        error_msg = f"❌ システムエラーが発生しました: {str(e)}"
        if "quota" in str(e).lower():
            error_msg += "\n\n💡 API使用量の上限に達している可能性があります。しばらく時間をおいてから再試行してください。"
        elif "authentication" in str(e).lower():
            error_msg += "\n\n💡 API認証に問題があります。APIキーの設定を確認してください。"
        
        yield type('ErrorChunk', (), {'text': error_msg})()

def get_score_distribution():
    """
    採点基準の詳細説明を返します。
    
    Returns:
        dict: 採点基準の詳細
    """
    return {
        "日本語訳": {
            "9-10点": "専門用語も含めて正確に訳され、自然で流暢な日本語",
            "7-8点": "概ね正確で読みやすいが、一部に不自然な表現がある",
            "5-6点": "基本的な意味は伝わるが、誤訳や不適切な表現が散見される",
            "3-4点": "部分的に正確だが、重要な誤訳や脱落がある",
            "1-2点": "大部分が不正確または理解困難"
        },
        "意見": {
            "9-10点": "深い洞察と独創性があり、論理的で説得力のある論述",
            "7-8点": "適切な理解に基づく妥当な意見で、論理性もある",
            "5-6点": "基本的な理解はあるが、論理性や独創性に欠ける",
            "3-4点": "部分的理解に基づく浅い意見",
            "1-2点": "理解不足で論理性に欠ける"
        },
        "小論文": {
            "9-10点": "明確な構成で具体的根拠もあり、優れた文章技術",
            "7-8点": "適切な構成と内容で、文章技術も概ね良好",
            "5-6点": "基本的な構成はあるが、内容の充実度や文章技術に課題",
            "3-4点": "構成や内容に明確な不備がある", 
            "1-2点": "構成が不明確で内容も不十分"
        }
    }

def validate_reading_inputs(abstract, translation, opinion):
    """
    英語読解（翻訳+考察）の入力値を検証します。
    
    Args:
        abstract (str): 原文Abstract
        translation (str): 日本語訳
        opinion (str): 意見・考察
    
    Returns:
        tuple: (bool, str) - (有効?, エラーメッセージ)
    """
    if not abstract or len(abstract.strip()) < 50:
        return False, "Abstractが不足しています。"
    
    if not translation or len(translation.strip()) < 30:
        return False, "日本語訳を入力してください（最低30文字）。"
    
    if not opinion or len(opinion.strip()) < 50:
        return False, "意見・考察を入力してください（最低50文字）。"
    
    return True, ""

def get_reading_scoring_prompt(abstract, translation, opinion):
    """
    英語読解（翻訳+考察）用の採点プロンプトを生成します。
    
    Returns:
        str: 採点用プロンプト
    """
    return f"""あなたは医学英語読解の経験豊富な採点者です。以下の答案を厳正かつ公平に採点してください。評価は出力制限を気にせず細かく可能な限り書いてください。

【原文Abstract】
{abstract}

【受験者の回答】
■ 課題1: Abstractの日本語訳
{translation}

■ 課題2: Abstractに対する意見・考察
{opinion}

【採点基準】
各項目を10点満点で評価してください。

1. **日本語訳 (10点満点)**
   - 正確性 (4点): 専門用語や文脈の理解度
   - 流暢性 (3点): 自然で読みやすい日本語
   - 完成度 (3点): 全体的なまとまりと訳し漏れの有無

2. **意見・考察 (10点満点)**
   - 理解度 (4点): Abstractの内容を正確に把握
   - 論理性 (4点): 筋道立った議論の展開
   - 独創性 (2点): 独自の視点や深い洞察

【出力形式】
必ず以下の形式で出力してください：

**スコア:**
```json
{{
  "日本語訳": [1-10の整数],
  "意見・考察": [1-10の整数]
}}
```

## 総合評価
[20点満点中の得点と全体的なコメント]

## 課題1: 日本語訳の評価
**良い点:**
- [具体的な良い点を記述。どの表現が良かったかを記載してください。]

**改善点:**
- [具体的な改善点を記述。どの表現が改善すべきか。また、改善するとしたらどのようにすべきかを記載してください。]

**模範訳例:**
- [重要な専門用語や表現について、より適切な日本語表現を提示してください。]

## 課題2: 意見・考察の評価
**良い点:**
- [具体的な良い点を記述。どの観点や論理展開が良かったかを記載してください。]

**改善点:**
- [具体的な改善点を記述。論理性、理解度、考察の深さなどについて改善すべき点を記載してください。]

**考察のヒント:**
- [この論文に関して、より深い考察につながるような観点や視点を提示してください。]

## 学習アドバイス
[医学英語読解力向上のための具体的なアドバイス]
"""

def score_reading_stream(abstract, translation, opinion):
    """
    英語読解（翻訳+考察）の提出物を採点し、結果をストリーミングで返す。
    
    Args:
        abstract (str): 原文Abstract
        translation (str): 日本語訳
        opinion (str): 意見・考察
    
    Yields:
        採点結果のストリーミングチャンク
    """
    # 入力検証
    is_valid, error_msg = validate_reading_inputs(abstract, translation, opinion)
    if not is_valid:
        yield type('ErrorChunk', (), {'text': f"❌ 入力エラー: {error_msg}"})()
        return
    
    try:
        client = genai.Client()
        prompt = get_reading_scoring_prompt(abstract, translation, opinion)
        
        # ストリーミング応答を生成
        response_stream = client.models.generate_content_stream(
            model='gemini-2.5-pro',
            contents=prompt
        )
        
        # レスポンスが有効かチェック
        if not response_stream:
            raise ScoringError("AI採点システムから応答が得られませんでした。")
        
        chunk_count = 0
        for chunk in response_stream:
            chunk_count += 1
            if hasattr(chunk, 'text') and chunk.text:
                yield chunk
            else:
                # 無効なチャンクの場合は警告を表示
                yield type('WarningChunk', (), {
                    'text': f"\n⚠️ [チャンク{chunk_count}] 応答形式が予期しない形式です。\n"
                })()
        
        # チャンクが全く受信されなかった場合
        if chunk_count == 0:
            raise ScoringError("採点結果を取得できませんでした。")
            
    except ScoringError as e:
        yield type('ErrorChunk', (), {'text': f"❌ 採点エラー: {str(e)}"})()
    except Exception as e:
        # 予期しないエラーの場合
        error_msg = f"❌ システムエラーが発生しました: {str(e)}"
        if "quota" in str(e).lower():
            error_msg += "\n\n💡 API使用量の上限に達している可能性があります。しばらく時間をおいてから再試行してください。"
        elif "authentication" in str(e).lower():
            error_msg += "\n\n💡 API認証に問題があります。APIキーの設定を確認してください。"
        
        yield type('ErrorChunk', (), {'text': error_msg})()

def get_reading_score_distribution():
    """
    英語読解採点基準の詳細説明を返します。
    
    Returns:
        dict: 採点基準の詳細
    """
    return {
        "日本語訳": {
            "9-10点": "専門用語も含めて正確に訳され、自然で流暢な日本語",
            "7-8点": "概ね正確で読みやすいが、一部に不自然な表現がある",
            "5-6点": "基本的な意味は伝わるが、誤訳や不適切な表現が散見される",
            "3-4点": "部分的に正確だが、重要な誤訳や脱落がある",
            "1-2点": "大部分が不正確または理解困難"
        },
        "意見・考察": {
            "9-10点": "深い洞察と独創性があり、論理的で説得力のある考察",
            "7-8点": "適切な理解に基づく妥当な考察で、論理性もある",
            "5-6点": "基本的な理解はあるが、考察の深さや独創性に欠ける",
            "3-4点": "部分的理解に基づく表面的な考察",
            "1-2点": "理解不足で論理性に欠ける"
        }
    }
