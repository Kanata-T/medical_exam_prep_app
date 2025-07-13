import streamlit as st
import google.genai as genai
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from modules.utils import safe_api_call, score_with_retry_stream
from modules.database_adapter_v3 import DatabaseAdapterV3

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

def score_exam_stream(abstract: str, translation: str, opinion: str, essay: str, essay_theme: str, 
                     save_to_db: bool = True) -> Any:
    """
    採用試験の提出物を採点し、結果をストリーミングで返す。
    リトライ機能付きで503エラーなどに対応。
    
    Args:
        abstract (str): 原文Abstract
        translation (str): 日本語訳
        opinion (str): 意見  
        essay (str): 小論文
        essay_theme (str): 小論文テーマ
        save_to_db (bool): データベースに保存するかどうか
    
    Yields:
        採点結果のストリーミングチャンク
    """
    # 入力検証
    is_valid, error_msg = validate_exam_inputs(abstract, translation, opinion, essay, essay_theme)
    if not is_valid:
        yield type('ErrorChunk', (), {'text': f"❌ 入力エラー: {error_msg}"})()
        return
    
    # 採点開始時間記録
    start_time = datetime.now()
    full_response = ""
    
    # リトライ機能付きの採点関数を定義
    def _score_exam_internal():
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
            
            return response_stream
            
        except ScoringError as e:
            raise e
        except Exception as e:
            # 予期しないエラーの場合
            error_msg = f"システムエラーが発生しました: {str(e)}"
            if "quota" in str(e).lower():
                error_msg += "\n\nAPI使用量の上限に達している可能性があります。しばらく時間をおいてから再試行してください。"
            elif "authentication" in str(e).lower():
                error_msg += "\n\nAPI認証に問題があります。APIキーの設定を確認してください。"
            
            raise ScoringError(error_msg)
    
    # ストリーミング実行とレスポンス収集
    try:
        for chunk in score_with_retry_stream(_score_exam_internal):
            if hasattr(chunk, 'text'):
                full_response += chunk.text
            yield chunk
    except Exception as e:
        yield type('ErrorChunk', (), {'text': f"❌ 採点エラー: {str(e)}"})()
        return
    
    # 採点完了後の処理
    if save_to_db and full_response:
        try:
            # スコア解析
            parsed_result = parse_score_from_response(full_response)
            
            # 入力データ準備
            inputs = {
                'abstract': abstract,
                'translation': translation,
                'opinion': opinion,
                'essay': essay,
                'essay_theme': essay_theme
            }
            
            # データベースに保存
            save_scoring_result(
                exercise_type='採用試験採点',
                inputs=inputs,
                scores=parsed_result['scores'],
                feedback=parsed_result['feedback']
            )
            
        except Exception as e:
            print(f"⚠️ 採点結果保存エラー: {e}")
    
    # 採点時間の記録（オプション）
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"⏱️ 採点時間: {duration:.2f}秒")

def parse_score_from_response(response_text: str) -> Dict[str, Any]:
    """
    AI応答からスコアを解析します。
    
    Args:
        response_text (str): AIの応答テキスト
        
    Returns:
        Dict[str, Any]: 解析されたスコアとフィードバック
    """
    try:
        # JSONスコアの抽出
        score_match = re.search(r'```json\s*({[^}]+})\s*```', response_text, re.DOTALL)
        if score_match:
            score_json = score_match.group(1)
            scores = json.loads(score_json)
        else:
            # フォールバック: 数値の直接抽出
            scores = {}
            score_patterns = {
                "日本語訳": r"日本語訳[：:]\s*(\d+)",
                "意見": r"意見[：:]\s*(\d+)",
                "小論文": r"小論文[：:]\s*(\d+)",
                "翻訳評価": r"翻訳評価[：:]\s*(\d+)",
                "理解度": r"理解度[：:]\s*(\d+)",
                "総合評価": r"総合評価[：:]\s*(\d+)"
            }
            
            for category, pattern in score_patterns.items():
                match = re.search(pattern, response_text)
                if match:
                    scores[category] = int(match.group(1))
        
        return {
            'scores': scores,
            'feedback': response_text,
            'raw_response': response_text
        }
        
    except Exception as e:
        return {
            'scores': {},
            'feedback': response_text,
            'raw_response': response_text,
            'parse_error': str(e)
        }

def save_scoring_result(exercise_type: str, inputs: Dict[str, Any], scores: Dict[str, Any], 
                       feedback: str, ai_model: str = 'gemini-2.5-pro') -> bool:
    """
    採点結果をデータベースに保存します。
    
    Args:
        exercise_type (str): 演習タイプ
        inputs (Dict[str, Any]): 入力データ
        scores (Dict[str, Any]): スコアデータ
        feedback (str): フィードバック
        ai_model (str): 使用したAIモデル
        
    Returns:
        bool: 保存成功時True
    """
    try:
        db_adapter = DatabaseAdapterV3()
        
        # 入力データの準備
        input_data = {
            'type': exercise_type,
            'date': str(datetime.now()),
            'inputs': inputs,
            'scores': scores,
            'feedback': feedback,
            'duration_seconds': 0  # 採点時間は別途計測が必要
        }
        
        # データベースに保存
        success = db_adapter.save_practice_history(input_data)
        
        if success:
            print(f"✅ 採点結果を保存しました: {exercise_type}")
        else:
            print(f"❌ 採点結果の保存に失敗しました: {exercise_type}")
        
        return success
        
    except Exception as e:
        print(f"❌ 採点結果保存エラー: {e}")
        return False

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

def score_reading_stream(abstract: str, translation: str, opinion: str, save_to_db: bool = True) -> Any:
    """
    英語読解（翻訳+考察）の提出物を採点し、結果をストリーミングで返す。
    リトライ機能付きで503エラーなどに対応。
    
    Args:
        abstract (str): 原文Abstract
        translation (str): 日本語訳
        opinion (str): 意見・考察
        save_to_db (bool): データベースに保存するかどうか
    
    Yields:
        採点結果のストリーミングチャンク
    """
    # 入力検証
    is_valid, error_msg = validate_reading_inputs(abstract, translation, opinion)
    if not is_valid:
        yield type('ErrorChunk', (), {'text': f"❌ 入力エラー: {error_msg}"})()
        return

    # 採点開始時間記録
    start_time = datetime.now()
    full_response = ""
    
    # リトライ機能付きの採点関数を定義
    def _score_reading_internal():
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
            
            return response_stream
            
        except ScoringError as e:
            raise e
        except Exception as e:
            # 予期しないエラーの場合
            error_msg = f"システムエラーが発生しました: {str(e)}"
            if "quota" in str(e).lower():
                error_msg += "\n\nAPI使用量の上限に達している可能性があります。しばらく時間をおいてから再試行してください。"
            elif "authentication" in str(e).lower():
                error_msg += "\n\nAPI認証に問題があります。APIキーの設定を確認してください。"
            
            raise ScoringError(error_msg)
    
    # ストリーミング実行とレスポンス収集
    try:
        for chunk in score_with_retry_stream(_score_reading_internal):
            if hasattr(chunk, 'text'):
                full_response += chunk.text
            yield chunk
    except Exception as e:
        yield type('ErrorChunk', (), {'text': f"❌ 採点エラー: {str(e)}"})()
        return
    
    # 採点完了後の処理
    if save_to_db and full_response:
        try:
            # スコア解析
            parsed_result = parse_score_from_response(full_response)
            
            # 入力データ準備
            inputs = {
                'abstract': abstract,
                'translation': translation,
                'opinion': opinion
            }
            
            # データベースに保存
            save_scoring_result(
                exercise_type='english_reading_practice',  # 新DBに存在するタイプ名
                inputs=inputs,
                scores=parsed_result['scores'],
                feedback=parsed_result['feedback']
            )
            
        except Exception as e:
            print(f"⚠️ 採点結果保存エラー: {e}")
    
    # 採点時間の記録（オプション）
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"⏱️ 採点時間: {duration:.2f}秒")

def get_exam_style_scoring_prompt(content, translation, opinion, format_type, task_instruction=""):
    """
    過去問スタイル用の採点プロンプトを生成します。
    
    Args:
        content: 出題内容（Letterまたはコメント形式のデータ）
        translation: 受験者の翻訳
        opinion: 受験者の意見（Letter形式の場合のみ）
        format_type: 出題形式 ("letter_translation_opinion" or "paper_comment_translation_opinion")
        task_instruction: 課題指示文
    
    Returns:
        str: 採点用プロンプト
    """
    if format_type == "letter_translation_opinion":
        return f"""あなたは県総採用試験の過去問スタイル（Letter形式）の経験豊富な採点者です。以下の答案を厳正かつ公平に採点してください。評価は出力制限を気にせず細かく可能な限り書いてください。

【過去問スタイル出題】
課題: {task_instruction}

【出題Letter】
{content}

【受験者の回答】
■ 課題1: Letterの日本語訳
{translation}

■ 課題2: Letterに対する意見
{opinion}

【採点基準】
各項目を10点満点で評価してください。

1. **日本語訳 (10点満点)**
   - 正確性 (4点): 専門用語や文脈の理解度、統計データの正確な翻訳
   - 流暢性 (3点): 自然で読みやすい日本語表現
   - 完成度 (3点): 全体的なまとまりと訳し漏れの有無

2. **意見 (10点満点)**
   - 理解度 (4点): Letterの内容と論点を正確に把握
   - 論理性 (4点): 筋道立った議論の展開
   - 独創性 (2点): 独自の視点や深い洞察

【出力形式】
必ず以下の形式で出力してください：

**スコア:**
```json
{{
  "日本語訳": [1-10の整数],
  "意見": [1-10の整数]
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
- [重要な専門用語や統計データについて、より適切な日本語表現を提示してください。]

## 課題2: 意見の評価
**良い点:**
- [具体的な良い点を記述。どの観点や論理展開が良かったかを記載してください。]

**改善点:**
- [具体的な改善点を記述。論理性、理解度、考察の深さなどについて改善すべき点を記載してください。]

**意見のヒント:**
- [このLetterに関して、より深い考察につながるような観点や視点を提示してください。]

## 学習アドバイス
[医学英語読解力向上のための具体的なアドバイス]
"""
    
    else:  # paper_comment_translation_opinion
        paper_summary = content.get('paper_summary', '') if isinstance(content, dict) else ""
        comment_text = content.get('comment', '') if isinstance(content, dict) else ""
        
        return f"""あなたは県総採用試験の過去問スタイル（論文コメント形式）の経験豊富な採点者です。以下の答案を厳正かつ公平に採点してください。評価は出力制限を気にせず細かく可能な限り書いてください。

【過去問スタイル出題】
課題: {task_instruction}

【論文概要】
{paper_summary}

【コメント】
{comment_text}

【受験者の回答】
■ 統合回答（翻訳 + 意見）
{translation}

【採点基準】
以下の観点で10点満点で評価してください。

1. **翻訳部分 (5点満点)**
   - 正確性 (3点): コメントの内容を正確に理解し翻訳
   - 表現力 (2点): 自然で読みやすい日本語表現

2. **意見部分 (5点満点)**
   - 理解度 (2点): コメントの論点を正確に把握
   - 論理性 (2点): 筋道立った意見の展開
   - 独創性 (1点): 独自の視点や深い洞察

【出力形式】
必ず以下の形式で出力してください：

**スコア:**
```json
{{
  "統合回答": [1-10の整数]
}}
```

## 総合評価
[10点満点中の得点と全体的なコメント]

## 翻訳部分の評価
**良い点:**
- [具体的な良い点を記述。どの表現が良かったかを記載してください。]

**改善点:**
- [具体的な改善点を記述。どの表現が改善すべきか。また、改善するとしたらどのようにすべきかを記載してください。]

**模範訳例:**
- [重要な表現について、より適切な日本語表現を提示してください。]

## 意見部分の評価
**良い点:**
- [具体的な良い点を記述。どの観点や論理展開が良かったかを記載してください。]

**改善点:**
- [具体的な改善点を記述。論理性、理解度、考察の深さなどについて改善すべき点を記載してください。]

**意見のヒント:**
- [このコメントに関して、より深い考察につながるような観点や視点を提示してください。]

## 学習アドバイス
[医学英語読解力向上のための具体的なアドバイス]
"""

def score_exam_style_stream(content: Any, translation: str, opinion: str = "", format_type: str = "", 
                          task_instruction: str = "", save_to_db: bool = True) -> Any:
    """
    過去問スタイルの提出物を採点し、結果をストリーミングで返す。
    リトライ機能付きで503エラーなどに対応。
    
    Args:
        content: 出題内容（Letterまたはコメント形式のデータ）
        translation: 受験者の翻訳
        opinion: 受験者の意見（Letter形式の場合のみ）
        format_type: 出題形式
        task_instruction: 課題指示文
        save_to_db: データベースに保存するかどうか
    
    Yields:
        採点結果のストリーミングチャンク
    """
    # 入力検証
    if not content:
        yield type('ErrorChunk', (), {'text': "❌ 入力エラー: 出題内容が不足しています。"})()
        return
    
    if not translation or len(translation.strip()) < 30:
        yield type('ErrorChunk', (), {'text': "❌ 入力エラー: 翻訳を入力してください（最低30文字）。"})()
        return
    
    if format_type == "letter_translation_opinion" and (not opinion or len(opinion.strip()) < 50):
        yield type('ErrorChunk', (), {'text': "❌ 入力エラー: 意見を入力してください（最低50文字）。"})()
        return

    # 採点開始時間記録
    start_time = datetime.now()
    full_response = ""
    
    # リトライ機能付きの採点関数を定義
    def _score_exam_style_internal():
        try:
            client = genai.Client()
            prompt = get_exam_style_scoring_prompt(content, translation, opinion, format_type, task_instruction)
            
            # ストリーミング応答を生成
            response_stream = client.models.generate_content_stream(
                model='gemini-2.5-pro',
                contents=prompt
            )
            
            # レスポンスが有効かチェック
            if not response_stream:
                raise ScoringError("AI採点システムから応答が得られませんでした。")
            
            return response_stream
            
        except ScoringError as e:
            raise e
        except Exception as e:
            # 予期しないエラーの場合
            error_msg = f"システムエラーが発生しました: {str(e)}"
            if "quota" in str(e).lower():
                error_msg += "\n\nAPI使用量の上限に達している可能性があります。しばらく時間をおいてから再試行してください。"
            elif "authentication" in str(e).lower():
                error_msg += "\n\nAPI認証に問題があります。APIキーの設定を確認してください。"
            
            raise ScoringError(error_msg)
    
    # ストリーミング実行とレスポンス収集
    try:
        for chunk in score_with_retry_stream(_score_exam_style_internal):
            if hasattr(chunk, 'text'):
                full_response += chunk.text
            yield chunk
    except Exception as e:
        yield type('ErrorChunk', (), {'text': f"❌ 採点エラー: {str(e)}"})()
        return
    
    # 採点完了後の処理
    if save_to_db and full_response:
        try:
            # スコア解析
            parsed_result = parse_score_from_response(full_response)
            
            # 入力データ準備
            inputs = {
                'content': content,
                'translation': translation,
                'opinion': opinion,
                'format_type': format_type,
                'task_instruction': task_instruction
            }
            
            # データベースに保存
            save_scoring_result(
                exercise_type='english_reading_practice',  # 新DBに存在するタイプ名
                inputs=inputs,
                scores=parsed_result['scores'],
                feedback=parsed_result['feedback']
            )
            
        except Exception as e:
            print(f"⚠️ 採点結果保存エラー: {e}")
    
    # 採点時間の記録（オプション）
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"⏱️ 採点時間: {duration:.2f}秒")

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
