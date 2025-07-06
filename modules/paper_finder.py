import streamlit as st
import google.genai as genai
from google.genai.types import GenerateContentConfig, Tool, GoogleSearch
from modules.utils import safe_api_call
import re
import random

def validate_keywords(keywords):
    """
    検索キーワードの妥当性を検証します。
    
    Args:
        keywords (str): 検索キーワード
    
    Returns:
        tuple: (bool, str) - (有効?, エラーメッセージ)
    """
    if not keywords or not keywords.strip():
        return False, "検索キーワードを入力してください。"
    
    # 最小文字数チェック
    if len(keywords.strip()) < 2:
        return False, "検索キーワードは2文字以上で入力してください。"
    
    # 特殊文字のみでないかチェック
    if re.match(r'^[^\w\s]+$', keywords.strip()):
        return False, "有効な検索キーワードを入力してください。"
    
    return True, ""

def find_medical_paper(keywords=None):
    """
    与えられたキーワードでPubMedから医学論文のAbstractを検索・取得する。
    キーワードがない場合は、典型的な分野からランダムに検索する。
    
    Args:
        keywords (str, optional): 検索キーワード. Defaults to None.
    
    Returns:
        dict: {
            "abstract": str,
            "citations": list,
            "error": str (optional)
        }
    """
    # キーワードが入力されている場合のみ検証
    if keywords:
        is_valid, error_msg = validate_keywords(keywords)
        if not is_valid:
            return {
                "abstract": "",
                "citations": [],
                "error": error_msg
            }
    else:
        # キーワードがない場合は、サンプルからランダムに選択
        keywords = random.choice(get_sample_keywords())
    
    def _search_paper():
        """内部の論文検索関数"""
        client = genai.Client()
        
        tool = Tool(google_search=GoogleSearch())
        config = GenerateContentConfig(tools=[tool])
        
        # より具体的で効果的なプロンプト
        prompt = f"""# 命令
あなたは医学文献検索の専門家として、以下の条件に合致する最適な医学論文をPubMedから1つだけ見つけ、そのAbstract（要旨）のみを出力してください。

# 検索条件
- キーワード: {keywords}
- 対象: 査読済みのPubMed掲載論文
- 論文の優先度:
  1. 臨床的に極めて重要で、画期的な治療薬や診断法に関する研究（例: ARNi, SGLT2阻害薬, GLP-1受容体作動薬, 免疫チェックポイント阻害薬など）
  2. 過去5年以内の最新研究
  3. メタアナリシスまたはランダム化比較試験
  4. 主要な医学雑誌に掲載された論文

# 出力ルール (!!最重要・厳守!!)
- 論文の選定理由、思考プロセス、タイトル、著者名、ジャーナル名、発行日など、Abstract本文以外の情報は**一切含めないでください**。
- 「以下にAbstractを示します。」のような前置きや、補足説明も**絶対に禁止**です。
- 出力は、Abstractの英文の最初の単語から始まり、最後の単語（またはピリオド）で終わる必要があります。
- Abstract本文のみを、完全な英語で出力してください。

# 実行開始
site:pubmed.ncbi.nlm.nih.gov {keywords}"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config,
        )
        
        if not response or not response.text:
            raise Exception("論文検索で有効な結果が得られませんでした。")
        
        abstract_text = response.text.strip()
        
        # Abstract形式の検証
        if len(abstract_text) < 100:
            raise Exception("取得されたAbstractが短すぎます。より具体的なキーワードを試してください。")
        
        # 引用情報の抽出
        citations = []
        if (response.candidates and
            len(response.candidates) > 0 and
            hasattr(response.candidates[0], 'grounding_metadata') and
            response.candidates[0].grounding_metadata and
            hasattr(response.candidates[0].grounding_metadata, 'grounding_chunks') and
            response.candidates[0].grounding_metadata.grounding_chunks):

            for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                if (hasattr(chunk, 'web') and chunk.web and
                    hasattr(chunk.web, 'uri') and chunk.web.uri and
                    hasattr(chunk.web, 'title') and chunk.web.title):

                    # PubMedリンクのみを抽出
                    if 'pubmed' in chunk.web.uri.lower():
                        citations.append({
                            "uri": chunk.web.uri,
                            "title": chunk.web.title
                        })
        
        return {
            "abstract": abstract_text,
            "citations": citations[:3]  # 最大3つまで
        }
    
    # 安全なAPI呼び出し
    success, result = safe_api_call(_search_paper)
    
    if success:
        return result
    else:
        return {
            "abstract": "",
            "citations": [],
            "error": f"論文検索エラー: {result}"
        }

def generate_essay_theme():
    """
    小論文のテーマをランダムに生成する。
    
    Returns:
        dict: {
            "theme": str,
            "error": str (optional)
        }
    """
    def _generate_theme():
        """内部のテーマ生成関数"""
        client = genai.Client()
        
        # より構造化されたプロンプト
        prompt = """役割
あなたは、地域医療の未来を担う人材を見極めたい、経験豊富な医学部採用試験の出題者です。単なる知識量だけでなく、将来医師となる者の人間性、倫理観、そして複雑な課題に対する思考の深さを測ることを重視しています。

# 指示
これから研修医を目指す意欲ある志望者の資質を多角的に評価するため、以下の要件をすべて満たす、質の高い小論文テーマを1つ、創造的に生成してください。

# 要件
テーマの核心: 現代日本の医療が直面する、光と影を映し出すようなテーマ。例えば、医療技術の進歩がもたらす新たな倫理的ジレンマ、社会構造の変化（例: SNSの普及、価値観の多様化）が医療現場に与える影響など、多角的な視点から考察できるもの。
問われる資質: 専門知識の有無に偏ることなく、むしろ受験者の共感力、誠実さ、そして社会に対する当事者意識や責任感を問える内容であること。
論述の深度: 600字という限られた字数の中で、賛成・反対の二元論に留まらない、独自の視点と論理的な思考を展開できる、具体的かつ開かれた問いであること。

# テーマの例
超高齢社会における終末期医療のあり方
地方における医師不足の解決策
医療分野へのAI導入の是非
医療格差の是正策
患者の自己決定権とインフォームド・コンセント

出力形式
小論文テーマのみを、「（テーマ）について、あなたの考えを600字以内で述べなさい。」という形式で記述してください。

タスク
以上の役割、指示、要件をすべて踏まえ、これまでにない独創的で示唆に富んだ小論文テーマを1つ生成してください。"""

        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt
        )
        
        if not response or not response.text:
            raise Exception("テーマ生成で有効な結果が得られませんでした。")
        
        theme = response.text.strip()
        
        # テーマの妥当性チェック
        if len(theme) < 20:
            raise Exception("生成されたテーマが短すぎます。")
        
        if not any(keyword in theme for keyword in ['について', 'に関して', '述べなさい', '論じなさい']):
            theme += "について、あなたの意見を600字程度で述べなさい。"
        
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

def get_sample_keywords():
    """
    サンプルキーワードのリストを返します。
    
    Returns:
        list: サンプルキーワードのリスト
    """
    return [
        "ARNi (angiotensin receptor-neprilysin inhibitor)",
        "SGLT2 inhibitors",
        "GLP-1 receptor agonist",
        "cancer immunotherapy",
        "regenerative medicine",
        "CRISPR-Cas9",
        "Alzheimer disease diagnosis",
        "COVID-19 vaccine",
        "hypertension management",
        "type 2 diabetes treatment",
        "atrial fibrillation",
        "chronic kidney disease progression"
    ]
