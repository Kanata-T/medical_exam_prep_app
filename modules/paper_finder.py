import streamlit as st
import google.genai as genai
from google.genai.types import GenerateContentConfig, Tool, GoogleSearch, Schema
from modules.utils import safe_api_call
import re
import random
import json

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
    与えられたキーワードでPubMedから医学論文情報を検索・取得する。
    キーワードがない場合は、AIが国家試験範囲内で自動選択する。
    
    Args:
        keywords (str, optional): 検索キーワード. Defaults to None.
    
    Returns:
        dict: {
            "title": str,
            "abstract": str,
            "citations": list,
            "keywords_used": str,
            "error": str (optional)
        }
    """
    # キーワードが入力されている場合のみ検証
    if keywords:
        is_valid, error_msg = validate_keywords(keywords)
        if not is_valid:
            return {
                "title": "",
                "abstract": "",
                "citations": [],
                "keywords_used": "",
                "error": error_msg
            }
        keywords_used = keywords
    else:
        # キーワードがない場合は、AIに国家試験範囲内で生成させる
        keyword_result = generate_medical_keywords()
        if 'error' in keyword_result:
            return {
                "title": "",
                "abstract": "",
                "citations": [],
                "keywords_used": "",
                "error": f"キーワード生成エラー: {keyword_result['error']}"
            }
        keywords_used = keyword_result['keywords']
    
    def _search_paper():
        """内部の論文検索関数（構造化出力使用）"""
        client = genai.Client()
        
        # 構造化出力のスキーマ定義
        paper_schema = Schema(
            type="object",
            properties={
                "title": Schema(
                    type="string",
                    description="論文のタイトル（英語）"
                ),
                "abstract": Schema(
                    type="string",
                    description="論文のAbstract全文（英語）"
                ),
                "relevance_score": Schema(
                    type="integer",
                    description="検索キーワードとの関連度（1-10）",
                    minimum=1,
                    maximum=10
                ),
                "study_type": Schema(
                    type="string",
                    description="研究の種類（例: RCT, Meta-analysis, Cohort study等）"
                )
            },
            required=["title", "abstract", "relevance_score", "study_type"]
        )
        
        tool = Tool(google_search=GoogleSearch())
        config = GenerateContentConfig(
            tools=[tool],
            response_schema=paper_schema
        )
        
        # 構造化出力用のプロンプト
        prompt = f"""# 任務
医学文献検索の専門家として、キーワード「{keywords_used}」に関連する高品質な医学論文をPubMedから1つ選定し、JSON形式で情報を抽出してください。

# 検索条件
- 対象サイト: PubMed (site:pubmed.ncbi.nlm.nih.gov)
- キーワード: {keywords_used}
- 優先度:
  1. 臨床的重要性が高い論文（例：ガイドラインに記載されるような治療法や診断法に関する論文（例：ARNi, SGLT2阻害薬, GLP-1受容体作動薬, 安定狭心症に対するPCIなど））
  2. Impact factorが高い主要医学雑誌掲載論文

# 出力要件
以下のJSON形式で正確に出力してください：
- title: 論文の正確なタイトル（英語）
- abstract: Abstract全文（英語、改行なし）
- relevance_score: キーワードとの関連度（1-10の整数）
- study_type: 研究デザインの種類

# 品質基準
- Abstractは100文字以上であること
- タイトルとAbstractは実際の論文から正確に抽出すること
- 医学的に信頼性の高い内容であること

site:pubmed.ncbi.nlm.nih.gov {keywords_used}"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config,
        )
        
        if not response or not response.text:
            raise Exception("論文検索で有効な結果が得られませんでした。")
        
        # 構造化出力の解析
        try:
            paper_data = json.loads(response.text)
        except json.JSONDecodeError:
            # フォールバック: テキストから抽出を試行
            raise Exception("構造化出力の解析に失敗しました。")
        
        # データ検証
        required_fields = ["title", "abstract", "relevance_score", "study_type"]
        for field in required_fields:
            if field not in paper_data:
                raise Exception(f"必須フィールド '{field}' が見つかりません。")
        
        if len(paper_data["abstract"]) < 100:
            raise Exception("取得されたAbstractが短すぎます。")
        
        # 引用情報の抽出（改善版）
        citations = []
        seen_urls = set()
        
        if (response.candidates and
            len(response.candidates) > 0 and
            hasattr(response.candidates[0], 'grounding_metadata') and
            response.candidates[0].grounding_metadata and
            hasattr(response.candidates[0].grounding_metadata, 'grounding_chunks') and
            response.candidates[0].grounding_metadata.grounding_chunks):

            for chunk in response.candidates[0].grounding_metadata.grounding_chunks:
                if (hasattr(chunk, 'web') and chunk.web and
                    hasattr(chunk.web, 'uri') and chunk.web.uri):

                    uri = chunk.web.uri
                    title = chunk.web.title if hasattr(chunk.web, 'title') and chunk.web.title else uri
                    
                    # PubMedリンクまたはNCBIリンクを優先的に抽出
                    if ('pubmed' in uri.lower() or 'ncbi.nlm.nih.gov' in uri.lower()) and uri not in seen_urls:
                        seen_urls.add(uri)
                        
                        # タイトルをクリーンアップ
                        if title == uri:
                            pmid_match = re.search(r'/(\d+)/?$', uri)
                            if pmid_match:
                                title = f"PubMed ID: {pmid_match.group(1)}"
                        
                        citations.append({
                            "uri": uri,
                            "title": title
                        })
        
        return {
            "title": paper_data["title"],
            "abstract": paper_data["abstract"],
            "study_type": paper_data["study_type"],
            "relevance_score": paper_data["relevance_score"],
            "citations": citations[:3],
            "keywords_used": keywords_used
        }
    
    # 安全なAPI呼び出し
    success, result = safe_api_call(_search_paper)
    
    if success:
        return result
    else:
        return {
            "title": "",
            "abstract": "",
            "citations": [],
            "keywords_used": keywords_used,
            "error": f"論文検索エラー: {result}"
        }

def generate_medical_keywords():
    """
    医師国家試験範囲内の医学キーワードをAIが自動生成する。
    
    Returns:
        dict: {
            "keywords": str,
            "error": str (optional)
        }
    """
    def _generate_keywords():
        """内部のキーワード生成関数"""
        client = genai.Client()
        
        # 構造化出力のスキーマ定義
        keywords_schema = Schema(
            type="object",
            properties={
                "keywords": Schema(
                    type="string",
                    description="医学論文検索用のキーワード（英語）"
                ),
                "category": Schema(
                    type="string",
                    description="医学分野のカテゴリ（例: 循環器学、消化器学等）"
                ),
                "rationale": Schema(
                    type="string",
                    description="このキーワードを選択した理由"
                )
            },
            required=["keywords", "category", "rationale"]
        )
        
        config = GenerateContentConfig(response_schema=keywords_schema)
        
        prompt = """# 任務
医師国家試験の出題範囲内で、臨床的に重要かつ最新の医学論文が見つかりやすいキーワードを1つ生成してください。

# 選択基準
1. 医師国家試験の出題範囲内であること
2. 臨床現場で頻繁に遭遇する疾患・治療法であること
3. 近年の医学的進歩が著しい分野であること
4. PubMedで高品質な論文が見つかりやすいこと

# 対象分野（例）
- 循環器学: 心不全、冠動脈疾患、不整脈
- 内分泌代謝学: 糖尿病、甲状腺疾患
- 消化器学: 炎症性腸疾患、肝疾患
- 神経学: 脳卒中、認知症、パーキンソン病
- 腫瘍学: がん免疫療法、分子標的治療
- 感染症学: 抗菌薬耐性、ワクチン、感染症動向、感染症の予防
- 救急医学: 敗血症、心肺蘇生
- 精神医学: うつ病、統合失調症

# 出力要件
JSON形式で以下を出力：
- keywords: 検索キーワード（英語、2-4語程度）
- category: 医学分野のカテゴリ
- rationale: 選択理由（簡潔に）

重要度が高く、論文が豊富で、国家試験でも重要な分野から選択してください。"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=config,
        )
        
        if not response or not response.text:
            raise Exception("キーワード生成で有効な結果が得られませんでした。")
        
        try:
            keyword_data = json.loads(response.text)
        except json.JSONDecodeError:
            raise Exception("構造化出力の解析に失敗しました。")
        
        if "keywords" not in keyword_data:
            raise Exception("キーワードが生成されませんでした。")
        
        return {
            "keywords": keyword_data["keywords"],
            "category": keyword_data.get("category", ""),
            "rationale": keyword_data.get("rationale", "")
        }
    
    # 安全なAPI呼び出し
    success, result = safe_api_call(_generate_keywords)
    
    if success:
        return result
    else:
        return {
            "keywords": "",
            "error": f"キーワード生成エラー: {result}"
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
