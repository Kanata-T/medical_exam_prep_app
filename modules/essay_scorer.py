import streamlit as st
import google.genai as genai
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from modules.utils import safe_api_call, score_with_retry_stream
from modules.database_adapter_v3 import DatabaseAdapterV3

def validate_essay_inputs(theme: str, memo: str, essay: str) -> Tuple[bool, str]:
    """
    小論文入力値を検証します。
    
    Args:
        theme (str): 小論文テーマ
        memo (str): 構成メモ
        essay (str): 清書
    
    Returns:
        Tuple[bool, str]: (有効?, エラーメッセージ)
    """
    if not theme or len(theme.strip()) < 10:
        return False, "小論文テーマが設定されていません。"
    
    if not memo or len(memo.strip()) < 20:
        return False, "構成メモを入力してください（最低20文字）。"
    
    if not essay or len(essay.strip()) < 200:
        return False, "清書を入力してください（最低200文字）。"
    
    # 文字数チェック（上限）
    if len(essay.strip()) > 2000:
        return False, "清書が長すぎます（2000文字以内）。"
    
    return True, ""

def get_essay_themes_samples() -> List[str]:
    """
    サンプルテーマのリストを返します。
    
    Returns:
        List[str]: サンプルテーマのリスト
    """
    return [
        "AI技術の医療分野への導入について、期待と課題を論じなさい。（1000字以内）",
        "超高齢社会における地域医療のあり方について、あなたの考えを述べなさい。（1000字以内）",
        "医療格差の是正に向けた具体的な取り組みについて論じなさい。（1000字以内）",
        "チーム医療の重要性と、そこでの医師の役割について述べなさい。（1000字以内）",
        "患者の自己決定権と医師の職業倫理について、あなたの見解を述べなさい。（1000字以内）"
    ]

def generate_long_essay_theme() -> Dict[str, str]:
    """
    1000字程度の小論文のテーマを生成する。
    
    Returns:
        Dict[str, str]: {
            "theme": str,
            "error": str (optional)
        }
    """
    def _generate_theme():
        """内部のテーマ生成関数"""
        client = genai.Client()
        
        prompt = """# 命令
あなたは医学部・医療関係の小論文出題者です。医学生や研修医志望者向けの1000字以内の小論文テーマを1つ生成してください。

# 目的と目標
- 日本の医療制度、地域医療、医療倫理、医療技術に関連する、時事性と将来性のある小論文テーマを生成する。
- 単なる知識確認ではなく、医学生や研修医志望者の思考力、論述力、および多角的な視点を問うテーマを提供する。
- 1000字以内で深く論述可能な、具体的かつ示唆に富むテーマを設定する。

# 行動とルール
- 必ず「日本の医療制度、地域医療、医療倫理、医療技術」のいずれかに関連するトピックを選ぶこと。
- 「時事性があり、将来の医療従事者として考えるべきテーマ」であること。現代社会の課題や医療の未来を見据えた内容を盛り込むこと。
- 「上記例以外で、新しく時代に即したテーマを1つ生成」すること。提示された例（人生100年時代、デジタルヘルスケア、多職種連携、終末期医療、地方の医師不足）とは異なる、独自のテーマを考案すること。

# 出力形式
- 生成するテーマは1つのみとする。
- テーマは「〜について、あなたの考えを1000字以内で述べなさい。」の形式で簡潔に記述すること。
- テーマの前に余計な説明や前置きは付けないこと。

# トーン
- 厳格かつ専門的な口調で、小論文の出題者としての権威を示す。
- 生成されるテーマは、挑戦的かつ思索を促すものであるように配慮する。
"""
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt
        )
        
        if not response or not response.text:
            raise Exception("テーマ生成で有効な結果が得られませんでした。")
        
        theme = response.text.strip()
        
        # テーマの妥当性チェック
        if len(theme) < 30:
            raise Exception("生成されたテーマが短すぎます。")
        
        # 文字数指定の確認・追加
        if not any(keyword in theme for keyword in ['1000字', '1000文字', '1000字程度']):
            theme += "（1000字程度）"
        
        return {"theme": theme}
    
    # 安全なAPI呼び出し
    success, result = safe_api_call(_generate_theme)
    
    if success:
        return result
    else:
        return {
            "theme": "",
            "error": f"テーマ生成エラー: {result}"
        }

def get_long_essay_scoring_prompt(theme: str, memo: str, essay: str) -> str:
    """
    小論文採点用プロンプトを生成します。
    
    Args:
        theme (str): 小論文テーマ
        memo (str): 構成メモ
        essay (str): 清書
    
    Returns:
        str: 採点用プロンプト
    """
    return f"""あなたは医学部・医療系小論文の経験豊富な採点者です。以下の小論文を厳正かつ公平に採点してください。

【テーマ】
{theme}

【受験者の提出物】
■ 構成メモ
{memo}

■ 清書（1000字以内）
{essay}

【採点基準】
各項目を10点満点で評価してください。

1. **構成メモ (10点満点)**
   - アイデアの質 (4点): テーマに対する着眼点の独創性と深さ
   - 論理構成 (3点): 主張と根拠の明確な関係性
   - 発展性 (3点): 説得力ある小論文への発展可能性

2. **清書 (10点満点)**
   - 構成力 (3点): 序論・本論・結論の明確性と一貫性
   - 論証力 (4点): 具体的根拠による効果的な主張の裏付け
   - 表現力 (2点): 語彙の豊富さと文章の明快性
   - 深化度 (1点): 構成メモからの発展と多角的考察

【出力形式】
必ず以下の形式で出力してください：

**スコア:**
```json
{{
  "構成メモ": [1-10の整数],
  "清書": [1-10の整数]
}}
```

## 総合評価
[20点満点中の得点と全体的なコメント]

## 構成メモの評価
**良い点:**
- [具体的な良い点を記述]

**改善点:**
- [具体的な改善点を記述]

## 清書の評価  
**良い点:**
- [具体的な良い点を記述]

**改善点:**
- [具体的な改善点を記述]

## 学習アドバイス
[今後の小論文作成に向けた具体的なアドバイス]
"""

class EssayError(Exception):
    """小論文処理専用の例外クラス"""
    pass

def score_long_essay_stream(theme: str, memo: str, essay: str, save_to_db: bool = True) -> Any:
    """
    小論文の構成メモと清書を採点し、結果をストリーミングで返す。
    リトライ機能付きで503エラーなどに対応。
    
    Args:
        theme (str): 小論文テーマ
        memo (str): 構成メモ
        essay (str): 清書
        save_to_db (bool): データベースに保存するかどうか
    
    Yields:
        採点結果のストリーミングチャンク
    """
    # 入力検証
    is_valid, error_msg = validate_essay_inputs(theme, memo, essay)
    if not is_valid:
        yield type('ErrorChunk', (), {'text': f"❌ 入力エラー: {error_msg}"})()
        return

    # 採点開始時間記録
    start_time = datetime.now()
    full_response = ""
    
    # リトライ機能付きの採点関数を定義
    def _score_essay_internal():
        try:
            client = genai.Client()
            prompt = get_long_essay_scoring_prompt(theme, memo, essay)
            
            # ストリーミング応答を生成
            response_stream = client.models.generate_content_stream(
                model='gemini-2.5-pro',
                contents=prompt
            )
            
            # レスポンスが有効かチェック
            if not response_stream:
                raise EssayError("AI採点システムから応答が得られませんでした。")
            
            return response_stream
            
        except EssayError as e:
            raise e
        except Exception as e:
            # 予期しないエラーの場合
            error_msg = f"システムエラーが発生しました: {str(e)}"
            if "quota" in str(e).lower():
                error_msg += "\n\nAPI使用量の上限に達している可能性があります。しばらく時間をおいてから再試行してください。"
            elif "authentication" in str(e).lower():
                error_msg += "\n\nAPI認証に問題があります。APIキーの設定を確認してください。"
            
            raise EssayError(error_msg)
    
    # ストリーミング実行とレスポンス収集
    try:
        for chunk in score_with_retry_stream(_score_essay_internal):
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
            parsed_result = parse_essay_score_from_response(full_response)
            
            # 入力データ準備
            inputs = {
                'theme': theme,
                'memo': memo,
                'essay': essay
            }
            
            # データベースに保存
            success = save_essay_scoring_result(
                inputs=inputs,
                scores=parsed_result['scores'],
                feedback=parsed_result['feedback']
            )
            
        except Exception as e:
            print(f"⚠️ 小論文採点結果保存エラー: {e}")
    
    # 採点時間の記録（オプション）
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"⏱️ 小論文採点時間: {duration:.2f}秒")

def parse_essay_score_from_response(response_text: str) -> Dict[str, Any]:
    """
    AI応答から小論文スコアを解析します。
    
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
                "構成メモ": r"構成メモ[：:]\s*(\d+)",
                "清書": r"清書[：:]\s*(\d+)",
                "小論文": r"小論文[：:]\s*(\d+)"
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

def save_essay_scoring_result(inputs: Dict[str, Any], scores: Dict[str, Any], 
                            feedback: str, ai_model: str = 'gemini-2.5-pro') -> bool:
    """
    小論文採点結果をデータベースに保存します。
    
    Args:
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
            'type': 'essay_scoring',  # 新DBに存在するタイプ名
            'date': str(datetime.now()),
            'inputs': inputs,
            'scores': scores,
            'feedback': feedback,
            'duration_seconds': 0  # 採点時間は別途計測が必要
        }
        
        # データベースに保存
        success = db_adapter.save_practice_history(input_data)
        
        if success:
            print(f"✅ 小論文採点結果を保存しました")
        else:
            print(f"❌ 小論文採点結果の保存に失敗しました")
        
        return success
        
    except Exception as e:
        print(f"❌ 小論文採点結果保存エラー: {e}")
        return False

def get_essay_writing_tips() -> Dict[str, List[str]]:
    """
    小論文作成のヒントを返します。
    
    Returns:
        Dict[str, List[str]]: カテゴリ別のヒント
    """
    return {
        "構成メモのコツ": [
            "テーマを複数の視点から検討する",
            "序論・本論・結論の骨子を明確にする", 
            "具体例や根拠となるデータを事前にリストアップ",
            "反対意見への反駁も準備する"
        ],
        "清書のコツ": [
            "1段落1主張の原則を守る",
            "接続詞を効果的に使用して論理関係を明確にする",
            "具体例は簡潔かつ説得力のあるものを選ぶ",
            "結論では将来への展望や提案を含める"
        ],
        "時間配分の目安": [
            "構成メモ: 15分",
            "清書: 40分",
            "見直し: 5分"
        ]
    }
