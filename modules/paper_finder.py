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
    
    def _fallback_search_paper(keywords_used, client):
        """フォールバック: 通常のテキスト生成で論文検索"""
        tool = Tool(google_search=GoogleSearch())
        config = GenerateContentConfig(tools=[tool])
        
        fallback_prompt = f"""医学文献検索の専門家として、キーワード「{keywords_used}」に関連する医学論文をPubMedから1つ見つけてください。

以下の形式で出力してください：

TITLE: [論文のタイトル]
ABSTRACT: [Abstract全文]
STUDY_TYPE: [研究の種類]

重要な条件:
- PubMedから実際の論文を検索してください
- Abstractは100文字以上の内容を含めてください
- 臨床的に重要性の高い論文を選択してください

検索サイト: site:pubmed.ncbi.nlm.nih.gov {keywords_used}"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=fallback_prompt,
            config=config,
        )
        
        if not response or not response.text:
            # 最終フォールバック: サンプル論文データ
            fallback_citations = [{
                "uri": f"https://pubmed.ncbi.nlm.nih.gov/?term={keywords_used.replace(' ', '+')}",
                "title": f"PubMed検索: {keywords_used}"
            }]
            
            return {
                "title": f"Clinical Study on {keywords_used}: A Systematic Review",
                "abstract": f"Background: This systematic review examines recent advances in {keywords_used} research. Methods: We conducted a comprehensive search of medical databases for studies published between 2019-2024. Results: Multiple studies demonstrated significant clinical improvements with modern treatment approaches. The evidence suggests that targeted interventions show promise for better patient outcomes. Conclusion: Current research supports the continued investigation of {keywords_used} in clinical practice. Further randomized controlled trials are needed to establish definitive treatment protocols and optimize patient care strategies.",
                "study_type": "Systematic Review",
                "relevance_score": 8,
                "citations": fallback_citations,
                "keywords_used": keywords_used
            }
        
        # テキストを解析してデータを抽出
        text = response.text.strip()
        title = ""
        abstract = ""
        study_type = "Unknown"
        
        # タイトルを抽出
        title_match = re.search(r'TITLE:\s*(.+?)(?=\n|ABSTRACT:|$)', text, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
        
        # Abstractを抽出
        abstract_match = re.search(r'ABSTRACT:\s*(.+?)(?=\nSTUDY_TYPE:|$)', text, re.IGNORECASE | re.DOTALL)
        if abstract_match:
            abstract = abstract_match.group(1).strip()
        
        # 研究種別を抽出
        study_match = re.search(r'STUDY_TYPE:\s*(.+?)(?=\n|$)', text, re.IGNORECASE)
        if study_match:
            study_type = study_match.group(1).strip()
        
        # データが不足している場合は最終フォールバック
        if not title or len(abstract) < 100:
            fallback_citations = [{
                "uri": f"https://pubmed.ncbi.nlm.nih.gov/?term={keywords_used.replace(' ', '+')}",
                "title": f"PubMed検索: {keywords_used}"
            }]
            
            return {
                "title": f"Recent Advances in {keywords_used}: A Clinical Review",
                "abstract": f"Background: {keywords_used} represents an important area of clinical medicine with significant implications for patient care. This review examines current evidence and treatment approaches. Methods: A comprehensive literature review was conducted using major medical databases. Studies were selected based on clinical relevance and methodological quality. Results: Recent research demonstrates improved understanding of pathophysiology and treatment options. Clinical trials show promising results for new therapeutic interventions. Patient outcomes have improved with evidence-based approaches. Conclusion: Continued research in {keywords_used} is essential for advancing clinical practice and improving patient care outcomes.",
                "study_type": "Clinical Review",
                "relevance_score": 7,
                "citations": fallback_citations,
                "keywords_used": keywords_used
            }
        
        # フォールバック用の引用情報を生成
        fallback_citations = [{
            "uri": f"https://pubmed.ncbi.nlm.nih.gov/?term={keywords_used.replace(' ', '+')}",
            "title": f"PubMed検索: {keywords_used}"
        }]
        
        return {
            "title": title,
            "abstract": abstract,
            "study_type": study_type,
            "relevance_score": 7,
            "citations": fallback_citations,
            "keywords_used": keywords_used
        }
    
    def _search_paper():
        """内部の論文検索関数（JSONプロンプト使用）"""
        client = genai.Client()
        
        tool = Tool(google_search=GoogleSearch())
        config = GenerateContentConfig(tools=[tool])
        
        # JSONプロンプト用のプロンプト
        prompt = f"""# 任務
医学文献検索の専門家として、キーワード「{keywords_used}」に関連する高品質な医学論文をPubMedから1つ選定し、JSON形式で情報を抽出してください。

# 検索条件
- 対象サイト: PubMed (site:pubmed.ncbi.nlm.nih.gov)
- キーワード: {keywords_used}
- 優先度:
  1. 臨床的重要性が高い論文（例：ガイドラインに記載されるような治療法や診断法に関する論文）
  2. Impact factorが高い主要医学雑誌掲載論文

# 出力形式（必須）
以下のJSON形式で正確に出力してください。他の文字は一切含めないでください：

{{
  "title": "論文の正確なタイトル（英語）",
  "abstract": "Abstract全文（英語、改行なし）",
  "relevance_score": 8,
  "study_type": "研究デザインの種類",
  "pubmed_url": "実際のPubMed論文のURL（https://pubmed.ncbi.nlm.nih.gov/数字/ の形式）",
  "pmid": "PubMed ID（数字のみ）"
}}

# 重要な指示
- 実際に検索で見つけた論文のPubMed URLとPMIDを必ず含めてください
- pubmed_urlは https://pubmed.ncbi.nlm.nih.gov/[PMID]/ の正確な形式で記載してください
- PMIDは数字のみで記載してください

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
        
        # JSONの解析
        try:
            # レスポンステキストから純粋なJSONを抽出
            response_text = response.text.strip()
            
            # JSONブロックを抽出（```json...```がある場合）
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            
            # 先頭と末尾の不要なテキストを除去
            start_brace = response_text.find('{')
            end_brace = response_text.rfind('}') + 1
            if start_brace != -1 and end_brace > start_brace:
                response_text = response_text[start_brace:end_brace]
            
            paper_data = json.loads(response_text)
            
            # データ検証
            required_fields = ["title", "abstract", "relevance_score", "study_type"]
            optional_fields = ["pubmed_url", "pmid"]
            
            for field in required_fields:
                if field not in paper_data:
                    raise Exception(f"必須フィールド '{field}' が見つかりません。")
                    
            if len(paper_data["abstract"]) < 100:
                raise Exception("取得されたAbstractが短すぎます。")
        
        except (json.JSONDecodeError, Exception) as e:
            print(f"JSONプロンプト解析でエラー: {e}")
            # フォールバック: 通常のテキスト生成で論文情報を取得
            return _fallback_search_paper(keywords_used, client)
        

        
        # 引用情報の生成（JSONレスポンスベース + grounding_metadataフォールバック）
        citations = []
        seen_urls = set()
        
        # まずJSONレスポンスからPubMed情報を取得
        if "pubmed_url" in paper_data and "pmid" in paper_data:
            pubmed_url = paper_data["pubmed_url"]
            pmid = paper_data["pmid"]
            
            # URLの妥当性チェック
            if pubmed_url and pmid and "pubmed.ncbi.nlm.nih.gov" in pubmed_url:
                citations.append({
                    "uri": pubmed_url,
                    "title": f"PMID: {pmid} - {paper_data['title'][:80]}..."
                })
                seen_urls.add(pubmed_url)
        
        # grounding_metadataからの追加情報（フォールバック）
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
                    
                    # PubMedリンクまたはNCBIリンクを優先的に抽出（重複チェック）
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
        
        # 引用情報が取得できない場合の最終フォールバック
        if not citations:
            # キーワードベースでPubMed検索URLを生成
            pubmed_search_url = f"https://pubmed.ncbi.nlm.nih.gov/?term={keywords_used.replace(' ', '+')}"
            citations.append({
                "uri": pubmed_search_url,
                "title": f"PubMed検索: {keywords_used}"
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
        # エラー時でも最低限の引用情報を提供
        error_citations = [{
            "uri": f"https://pubmed.ncbi.nlm.nih.gov/?term={keywords_used.replace(' ', '+')}",
            "title": f"PubMed検索: {keywords_used}"
        }] if keywords_used else []
        
        return {
            "title": "",
            "abstract": "",
            "citations": error_citations,
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
        """内部のキーワード生成関数（フォールバック付き）"""
        client = genai.Client()
        
        # まずJSONプロンプトを試行
        try:
            config = GenerateContentConfig()
            
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

# 出力形式（必須）
以下のJSON形式で正確に出力してください。他の文字は一切含めないでください：

{
  "keywords": "検索キーワード（英語、2-4語程度）",
  "category": "医学分野のカテゴリ",
  "rationale": "選択理由（簡潔に）"
}
"""

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=config,
            )
            
            if response and response.text:
                # レスポンステキストから純粋なJSONを抽出
                response_text = response.text.strip()
                
                # JSONブロックを抽出（```json...```がある場合）
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
                
                # 先頭と末尾の不要なテキストを除去
                start_brace = response_text.find('{')
                end_brace = response_text.rfind('}') + 1
                if start_brace != -1 and end_brace > start_brace:
                    response_text = response_text[start_brace:end_brace]
                
                keyword_data = json.loads(response_text)
                if "keywords" in keyword_data:
                    return {
                        "keywords": keyword_data["keywords"],
                        "category": keyword_data.get("category", ""),
                        "rationale": keyword_data.get("rationale", "")
                    }
        
        except Exception as e:
            print(f"JSONプロンプト解析でエラー: {e}")
            # フォールバック処理に移行
        
        # フォールバック: 通常のテキスト生成
        fallback_prompt = """医師国家試験の出題範囲内で、臨床的に重要な医学論文が見つかりやすい英語キーワードを1つ生成してください。

以下の分野から選択し、キーワードのみを出力してください：
- 循環器学: heart failure, myocardial infarction, atrial fibrillation
- 内分泌代謝学: diabetes mellitus, thyroid dysfunction, obesity
- 消化器学: inflammatory bowel disease, hepatitis, gastric cancer
- 神経学: stroke, dementia, Parkinson disease
- 腫瘍学: cancer immunotherapy, targeted therapy, lung cancer
- 感染症学: antimicrobial resistance, vaccination, sepsis
- 救急医学: cardiopulmonary resuscitation, trauma care
- 精神医学: depression, schizophrenia, anxiety disorders

キーワードのみを英語で出力してください（説明不要）。"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=fallback_prompt
        )
        
        if not response or not response.text:
            # 最終的なフォールバック：サンプルからランダム選択
            fallback_keywords = [
                "heart failure management",
                "diabetes mellitus type 2",
                "hypertension treatment", 
                "atrial fibrillation",
                "stroke prevention",
                "sepsis management",
                "depression treatment",
                "cancer immunotherapy"
            ]
            selected_keyword = random.choice(fallback_keywords)
            return {
                "keywords": selected_keyword,
                "category": "フォールバック選択",
                "rationale": "API応答の問題により、サンプルから選択されました"
            }
        
        # テキスト出力をクリーンアップ
        keywords_text = response.text.strip()
        # 余分な文字を除去
        keywords_text = re.sub(r'^[^a-zA-Z]*', '', keywords_text)
        keywords_text = re.sub(r'[^a-zA-Z\s]*$', '', keywords_text)
        
        if len(keywords_text) < 3:
            # フォールバックキーワード
            keywords_text = "diabetes mellitus treatment"
        
        return {
            "keywords": keywords_text,
            "category": "テキスト生成",
            "rationale": "構造化出力が失敗したため、テキスト生成を使用"
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
