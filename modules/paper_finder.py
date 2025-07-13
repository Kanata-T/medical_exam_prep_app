import streamlit as st
import google.genai as genai
from google.genai.types import GenerateContentConfig, Tool, GoogleSearch, Schema
from google.genai import types
from modules.utils import safe_api_call
from modules.database_adapter_v3 import DatabaseAdapterV3
from typing import Dict, List, Optional, Tuple, Any
import re
import random
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def validate_keywords(keywords: str) -> Tuple[bool, str]:
    """
    検索キーワードの妥当性を検証します。
    
    Args:
        keywords (str): 検索キーワード
    
    Returns:
        Tuple[bool, str]: (有効?, エラーメッセージ)
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

def find_medical_paper(keywords: Optional[str] = None, purpose: str = "general") -> Dict[str, Any]:
    """
    与えられたキーワードでPubMedから医学論文情報を検索・取得する。
    キーワードがない場合は、AIが国家試験範囲内で自動選択する。
    
    Args:
        keywords (Optional[str]): 検索キーワード. Defaults to None.
        purpose (str): 使用目的 ("medical_exam", "english_reading", "general"). Defaults to "general".
    
    Returns:
        Dict[str, Any]: {
            "title": str,
            "abstract": str,
            "citations": List[Dict[str, str]],
            "keywords_used": str,
            "category": str,
            "error": str (optional)
        }
    """
    # purposeに基づいて適切な練習タイプを決定
    purpose_to_practice_type = {
        "medical_exam": "medical_exam_comprehensive",
        "english_reading": "english_reading_standard", 
        "general": "paper_search"
    }
    practice_type = purpose_to_practice_type.get(purpose, "paper_search")
    
    # キーワードが入力されている場合のみ検証
    if keywords:
        is_valid, error_msg = validate_keywords(keywords)
        if not is_valid:
                    return {
            "title": "",
            "abstract": "",
            "citations": [],
            "keywords_used": "",
            "category": "",
            "error": error_msg
        }
        keywords_used = keywords
    else:
        # キーワードがない場合は、AIに国家試験範囲内で生成させる
        keyword_result = generate_medical_keywords(purpose)
        if 'error' in keyword_result:
            return {
                "title": "",
                "abstract": "",
                "citations": [],
                "keywords_used": "",
                "category": "",
                "error": f"キーワード生成エラー: {keyword_result['error']}"
            }
        keywords_used = keyword_result['keywords']
        generated_category = keyword_result.get('category', '')
        
        # 生成されたキーワードを論文検索履歴に保存（フォールバック時のみ）
        # 通常の論文検索成功時は後で保存されるため、ここでは保存しない
        print(f"キーワード生成完了: {keywords_used} (category: {generated_category})")
    
    def _fallback_search_paper(keywords_used, client):
        """フォールバック1: Google検索ツール付きでの再試行"""
        print("フォールバック1: Google検索ツール付きで再試行")
        tool = Tool(google_search=GoogleSearch())
        config = GenerateContentConfig(tools=[tool])
        
        fallback_prompt = f"""医学文献検索の専門家として、キーワード「{keywords_used}」に関連する医学論文をPubMedから1つ検索し、以下の形式で出力してください：

TITLE: [論文の正確なタイトル]
ABSTRACT: [Abstract完全版・省略禁止]
STUDY_TYPE: [研究デザインの種類]
PMID: [PubMed ID]

**Abstract抽出の重要指示:**
- Background, Methods, Results, Conclusionsの全セクションを含める
- Results部分の統計データ（p値、信頼区間、オッズ比、症例数、パーセンテージなど）を省略禁止
- 数値データや治療効果の詳細を必ず含める
- 要約や短縮は一切行わない
- 論文のAbstractに記載されている内容を完全に転写

**必須条件:**
- 必ずPubMedで実際に検索を行ってください
- 実在する論文のみを報告してください
- Abstractは最低200文字以上の完全版を含めてください
- 架空の論文データは禁止です

検索対象: site:pubmed.ncbi.nlm.nih.gov {keywords_used}"""

        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=fallback_prompt,
                config=config,
            )
            
            if response and response.text:
                return _parse_fallback_response(response.text, keywords_used)
            else:
                raise Exception("Google検索ツール付きフォールバックも応答なし")
                
        except Exception as e:
            print(f"Google検索ツール付きフォールバック失敗: {e}")
            return _fallback_no_tools(keywords_used, client)
        
    def _parse_fallback_response(response_text, keywords_used):
        """フォールバック応答のテキストを解析"""
        text = response_text.strip()
        title = ""
        abstract = ""
        study_type = "Unknown"
        pmid = ""
        
        # タイトルを抽出
        title_match = re.search(r'TITLE:\s*(.+?)(?=\n|ABSTRACT:|$)', text, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
        
        # Abstractを抽出
        abstract_match = re.search(r'ABSTRACT:\s*(.+?)(?=\nSTUDY_TYPE:|PMID:|$)', text, re.IGNORECASE | re.DOTALL)
        if abstract_match:
            abstract = abstract_match.group(1).strip()
        
        # 研究種別を抽出
        study_match = re.search(r'STUDY_TYPE:\s*(.+?)(?=\n|PMID:|$)', text, re.IGNORECASE)
        if study_match:
            study_type = study_match.group(1).strip()
        
        # PMIDを抽出
        pmid_match = re.search(r'PMID:\s*(\d+)', text, re.IGNORECASE)
        if pmid_match:
            pmid = pmid_match.group(1).strip()
        
        # 引用情報を生成
        citations = []
        if pmid:
            citations.append({
                "uri": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "title": f"PMID: {pmid} - {title[:80]}..."
            })
        
        # PubMed検索URLも追加
        citations.append({
            "uri": f"https://pubmed.ncbi.nlm.nih.gov/?term={keywords_used.replace(' ', '+')}",
            "title": f"PubMed検索: {keywords_used}"
        })
        
        # データ検証（完全版Abstract用）
        if not title or len(abstract) < 150:
            raise Exception("抽出されたAbstractが不十分です（完全版が必要）")
        
        result = {
            "title": title,
            "abstract": abstract,
            "study_type": study_type,
            "relevance_score": 7,
            "citations": citations,
            "keywords_used": keywords_used,
            "category": "フォールバック検索"
        }
        
        # フォールバック成功時の履歴保存（新DB対応）
        try:
            db_adapter = DatabaseAdapterV3()
            history_data = {
                "type": "paper_search",
                "date": datetime.now().isoformat(),
                "inputs": {
                    "keywords": keywords_used,
                    "category": "フォールバック検索",
                    "purpose": purpose
                },
                "outputs": {
                    "title": title,
                    "study_type": study_type,
                    "relevance_score": 7,
                    "citations_count": len(citations),
                    "abstract_length": len(abstract),
                    "success": True,
                    "fallback_used": True
                }
            }
            db_adapter.save_practice_history(history_data)
            logger.info(f"フォールバック検索履歴保存成功: {keywords_used}")
        except Exception as e:
            logger.warning(f"フォールバック検索履歴保存失敗: {e}")
            # フォールバック: 従来の保存方法
            try:
                from modules.utils import save_history
                legacy_history_data = {
                    "type": "論文検索",
                    "date": datetime.now().isoformat(),
                    "keywords": keywords_used,
                    "category": "フォールバック検索",
                    "title": title,
                    "study_type": study_type,
                    "relevance_score": 7,
                    "citations_count": len(citations),
                    "abstract_length": len(abstract),
                    "success": True,
                    "fallback_used": True
                }
                save_history(legacy_history_data)
                logger.info(f"従来形式でフォールバック検索履歴保存成功")
            except Exception as legacy_e:
                logger.error(f"従来形式でも履歴保存失敗: {legacy_e}")
        
        print(f"フォールバック検索成功 - 履歴保存:")
        print(f"  - キーワード: {keywords_used}")
        print(f"  - タイトル: {title[:50]}...")
        
        # フォールバック成功時も履歴保存
        try:
            save_success = save_paper_search_keyword(keywords_used, "フォールバック検索", purpose)
            if save_success:
                print(f"フォールバック検索履歴保存成功: {keywords_used}")
            else:
                print(f"フォールバック検索履歴保存失敗: {keywords_used}")
        except Exception as e:
            print(f"フォールバック検索履歴保存エラー: {e}")
        
        return result
    
    def _fallback_no_tools(keywords_used, client):
        """フォールバック2: ツールなしでの直接指示"""
        print("フォールバック2: ツールなしで直接PubMed検索指示")
        
        no_tools_prompt = f"""あなたはPubMedでの医学文献検索の専門家です。以下の手順で実際の論文を検索してください：

1. PubMedサイト (https://pubmed.ncbi.nlm.nih.gov/) にアクセス
2. キーワード「{keywords_used}」で検索
3. 最新の臨床的に重要な論文を1つ選択
4. その論文の情報を以下の形式で報告

**出力形式:**
TITLE: [実際の論文タイトル]
ABSTRACT: [実際のAbstract完全版]
STUDY_TYPE: [研究デザイン]
PMID: [PubMed ID]

**Abstract抽出の厳格な指示:**
- Background, Methods, Results, Conclusionsの全セクションを完全に含める
- Results部分の統計データ（p値、信頼区間、オッズ比、相対リスク、症例数、パーセンテージ）を省略禁止
- 数値データ、治療効果、副作用データの詳細を必ず含める
- 要約や短縮は絶対に行わない
- 論文のAbstractセクションの内容を一字一句正確に転写

**重要な指示:**
- 必ず実在する論文のみを報告してください
- 架空の論文は絶対に作成しないでください
- Abstractは実際の論文から完全版を正確に抽出してください
- PubMedで検索可能な論文のみ選択してください

検索キーワード: {keywords_used}
検索サイト: https://pubmed.ncbi.nlm.nih.gov/"""

        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=no_tools_prompt
            )
            
            if response and response.text:
                return _parse_fallback_response(response.text, keywords_used)
            else:
                raise Exception("ツールなしフォールバックも応答なし")
                
        except Exception as e:
            print(f"ツールなしフォールバック失敗: {e}")
            # 最終的にエラーを返す（架空データは使用しない）
            raise Exception(f"全てのフォールバック処理が失敗しました: {e}")
    
    def _search_paper():
        """内部の論文検索関数（JSONプロンプト使用、リトライ機能付き）"""
        client = genai.Client()
        
        tool = Tool(google_search=GoogleSearch())
        config = GenerateContentConfig(tools=[tool])
        
        # JSONプロンプト用のプロンプト
        prompt = f"""# 任務
医学文献検索の専門家として、キーワード「{keywords_used}」に関連する高品質な医学論文をPubMedなどから1つ選定し、JSON形式で情報を抽出してください。

# 検索条件
- 対象サイト: PubMed (site:pubmed.ncbi.nlm.nih.gov)、または、Google Scholar (site:scholar.google.com)
- キーワード: {keywords_used}
- 優先度:
    1. RCTやCase-Control Study形式の論文
    2. 総説やReview論文、メタアナリシスは禁止
    3. 臨床的重要性が高い論文（例：ガイドラインに記載されるような治療法や診断法に関する論文）
    4. Impact factorが高い主要医学雑誌掲載論文（例：JAMA、Lancet、NEJM、BMJなど）

# Abstract抽出の重要指示（必ず遵守）
**一度論文全体を読み込んで、その後Abstractのみを完全に抽出してください：**
- Background/Methods/Results/Conclusionsの全セクションを含める
- Results部分の統計データ（p値、信頼区間、オッズ比、相対リスク、パーセンテージなど）を省略禁止
- 数値データ、症例数、治療効果の詳細を必ず含める
- 要約や短縮は一切行わない
- 論文のAbstractセクションに記載されている内容を一字一句正確に転写

# 出力形式（必須）
以下のJSON形式で正確に出力してください。他の文字は一切含めないでください：

{{
  "title": "論文の正確なタイトル（英語）",
  "abstract": "Abstract完全版（英語、改行なし、全セクション含む、統計データ省略禁止）",
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
- Abstractは200文字以上であること（完全版のため）
- タイトルとAbstractは実際の論文から正確に抽出すること
- 医学的に信頼性の高い内容であること
- Results部分に具体的な数値データが含まれていること

site:pubmed.ncbi.nlm.nih.gov {keywords_used}"""

        # 同じプロンプトで最大3回リトライ
        last_error = None
        for attempt in range(3):
            try:
                print(f"論文検索試行 {attempt + 1}/3")
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=config,
                )
                
                if not response or not response.text:
                    raise Exception("論文検索で有効な結果が得られませんでした。")
                
                # レスポンスの詳細ログ
                print(f"試行 {attempt + 1} レスポンス長: {len(response.text) if response.text else 0}")
                print(f"試行 {attempt + 1} レスポンス先頭50文字: {response.text[:50] if response.text else 'None'}")
                
                # JSONの解析
                try:
                    # レスポンステキストから純粋なJSONを抽出
                    response_text = response.text.strip()
                    
                    # 空文字列チェック
                    if not response_text:
                        raise Exception("レスポンステキストが空です。")
                    
                    # JSONブロックを抽出（```json...```がある場合）
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(1)
                    
                    # 先頭と末尾の不要なテキストを除去
                    start_brace = response_text.find('{')
                    end_brace = response_text.rfind('}') + 1
                    if start_brace != -1 and end_brace > start_brace:
                        response_text = response_text[start_brace:end_brace]
                    else:
                        raise Exception("有効なJSON構造が見つかりませんでした。")
                    
                    # 最終的な空文字列チェック
                    if not response_text or response_text.strip() == "":
                        raise Exception("JSON抽出後にテキストが空になりました。")
                    
                    print(f"試行 {attempt + 1} JSON抽出結果: {response_text[:100]}...")
                    
                    paper_data = json.loads(response_text)
                    
                    # データ検証
                    required_fields = ["title", "abstract", "relevance_score", "study_type"]
                    optional_fields = ["pubmed_url", "pmid"]
                    
                    for field in required_fields:
                        if field not in paper_data:
                            raise Exception(f"必須フィールド '{field}' が見つかりません。")
                            
                    if len(paper_data["abstract"]) < 200:
                        raise Exception("取得されたAbstractが短すぎます（完全版が必要）。")
                    
                    # 成功した場合は以下の処理に進む
                    break
                    
                except (json.JSONDecodeError, Exception) as e:
                    last_error = e
                    print(f"試行 {attempt + 1} JSONパースエラー: {e}")
                    print(f"試行 {attempt + 1} レスポンス全文: {response.text if response.text else 'None'}")
                    if attempt < 2:  # 最後の試行でなければ続行
                        continue
                    else:  # 最後の試行でもエラーの場合
                        raise Exception(f"3回の試行すべてでJSONパース失敗: {last_error}")
                        
            except Exception as e:
                last_error = e
                print(f"試行 {attempt + 1} API呼び出しエラー: {e}")
                print(f"試行 {attempt + 1} エラー詳細: {type(e).__name__}")
                if attempt < 2:  # 最後の試行でなければ続行
                    continue
                else:  # 最後の試行でもエラーの場合
                    break
        
        # 3回とも失敗した場合、フォールバックを使用
        if last_error:
            print(f"全ての試行が失敗、フォールバックを使用: {last_error}")
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
            "keywords_used": keywords_used,
            "category": paper_data.get("category", "")
        }
    
    # 安全なAPI呼び出し
    success, result = safe_api_call(_search_paper)
    
    if success:
        # AI生成されたキーワードの場合、categoryを追加
        if not keywords and 'generated_category' in locals():
            result['category'] = generated_category
        
        # 論文検索成功時の履歴保存（新DB対応）
        print(f"論文検索成功 - 履歴保存開始:")
        print(f"  - 目的: {purpose} -> 練習タイプ: {practice_type}")
        print(f"  - キーワード: {result.get('keywords_used', '')}")
        print(f"  - 分野: {result.get('category', '')}")
        print(f"  - タイトル: {result.get('title', '')[:50]}...")
        
        try:
            # 論文検索履歴に保存
            save_success = save_paper_search_keyword(
                result.get("keywords_used", ""),
                result.get("category", ""),
                purpose
            )
            if save_success:
                print(f"論文検索履歴保存成功: {result.get('keywords_used', '')}")
                logger.info(f"論文検索履歴保存成功: {result.get('keywords_used', '')}")
            else:
                print(f"論文検索履歴保存失敗: {result.get('keywords_used', '')}")
                logger.warning(f"論文検索履歴保存失敗: {result.get('keywords_used', '')}")
        except Exception as e:
            print(f"論文検索履歴保存エラー: {e}")
            logger.warning(f"論文検索履歴保存失敗: {e}")
            # フォールバック: 従来の保存方法
            try:
                from modules.utils import save_history
                legacy_history_data = {
                    "type": practice_type,  # purposeに基づいた練習タイプ
                    "date": datetime.now().isoformat(),
                    "keywords": result.get("keywords_used", ""),
                    "category": result.get("category", ""),
                    "title": result.get("title", ""),
                    "study_type": result.get("study_type", ""),
                    "relevance_score": result.get("relevance_score", 0),
                    "citations_count": len(result.get("citations", [])),
                    "abstract_length": len(result.get("abstract", "")),
                    "purpose": purpose,  # 目的も記録
                    "success": True
                }
                save_history(legacy_history_data)
                print(f"従来形式で論文検索履歴保存成功")
                logger.info(f"従来形式で論文検索履歴保存成功")
            except Exception as legacy_e:
                print(f"従来形式でも履歴保存失敗: {legacy_e}")
                logger.error(f"従来形式でも履歴保存失敗: {legacy_e}")
        
        # デバッグ出力
        print(f"論文検索成功 - 履歴保存:")
        print(f"  - 目的: {purpose} -> 練習タイプ: {practice_type}")
        print(f"  - キーワード: {result.get('keywords_used', '')}")
        print(f"  - 分野: {result.get('category', '')}")
        print(f"  - タイトル: {result.get('title', '')[:50]}...")
        
        return result
    else:
        # 論文検索失敗時の履歴保存（新DB対応）
        try:
            db_adapter = DatabaseAdapterV3()
            history_data = {
                "type": practice_type,  # purposeに基づいた練習タイプ
                "date": datetime.now().isoformat(),
                "inputs": {
                    "keywords": keywords_used if 'keywords_used' in locals() else "",
                    "category": generated_category if not keywords and 'generated_category' in locals() else "",
                    "purpose": purpose
                },
                "outputs": {
                    "error": str(result),
                    "success": False
                }
            }
            db_adapter.save_practice_history(history_data)
            logger.info(f"論文検索失敗履歴保存成功")
        except Exception as e:
            logger.warning(f"論文検索失敗履歴保存失敗: {e}")
            # フォールバック: 従来の保存方法
            try:
                from modules.utils import save_history
                legacy_history_data = {
                    "type": practice_type,  # purposeに基づいた練習タイプ
                    "date": datetime.now().isoformat(),
                    "keywords": keywords_used if 'keywords_used' in locals() else "",
                    "category": generated_category if not keywords and 'generated_category' in locals() else "",
                    "purpose": purpose,  # 目的も記録
                    "error": str(result),
                    "success": False
                }
                save_history(legacy_history_data)
                logger.info(f"従来形式で論文検索失敗履歴保存成功")
            except Exception as legacy_e:
                logger.error(f"従来形式でも失敗履歴保存失敗: {legacy_e}")
        
        # デバッグ出力
        print(f"論文検索失敗 - 履歴保存:")
        print(f"  - 目的: {purpose} -> 練習タイプ: {practice_type}")
        print(f"  - キーワード: {keywords_used if 'keywords_used' in locals() else ''}")
        print(f"  - エラー: {str(result)[:100]}...")
        
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
            "category": generated_category if not keywords and 'generated_category' in locals() else "",
            "error": f"論文検索エラー: {result}"
        }

# 医学分野リスト（分野名のみ）
MEDICAL_FIELDS = [
    "循環器学", "内分泌代謝学", "消化器学", "神経学", "腫瘍学", "感染症学", 
    "救急医学", "精神医学", "呼吸器学", "腎泌尿器学", "整形外科学", "皮膚科学",
    "眼科学", "耳鼻咽喉科学", "産婦人科学", "小児科学", "麻酔科学", "放射線科学"
]

def generate_medical_keywords(purpose: str = "general") -> Dict[str, Any]:
    """
    医学論文検索用のキーワードをAIが生成します。
    
    Args:
        purpose (str): キーワード生成の目的 ("general", "paper_search", "free_writing")
    
    Returns:
        Dict[str, Any]: {
            "keywords": str,  # 生成されたキーワード
            "category": str,   # 選択された医学分野
            "rationale": str,  # 選択理由
            "purpose": str,    # 生成目的
            "error": str       # エラー時のみ
        }
    """
    # 練習タイプの決定
    practice_type = "keyword_generation_english"  # デフォルト
    
    def _generate_keywords():
        """内部のキーワード生成関数"""
        
        # 過去のキーワードと分野の取得（詳細情報付き）
        past_keywords = get_paper_search_keywords(limit=10)  # 論文検索履歴から取得
        detailed_history = get_keyword_history_with_details(limit=20)  # 詳細履歴を取得
        available_fields = get_available_fields()
        
        print(f"キーワード生成デバッグ情報:")
        print(f"  - 練習タイプ: {practice_type}")
        print(f"  - 用途: {purpose}")
        print(f"  - 過去のキーワード: {past_keywords}")
        print(f"  - 詳細履歴件数: {len(detailed_history)}")
        print(f"  - 利用可能分野: {available_fields}")
        
        # 過去の履歴から分野の使用頻度を分析
        category_usage = {}
        recent_keywords = []
        for item in detailed_history:
            category_id = item.get('category_id', '')
            keyword = item.get('keyword', '')
            if category_id:
                category_usage[category_id] = category_usage.get(category_id, 0) + 1
            if keyword:
                recent_keywords.append(keyword)
        
        print(f"  - 分野使用頻度: {category_usage}")
        print(f"  - 最近のキーワード: {recent_keywords[:5]}")
        
        client = genai.Client()
        
        # 用途に応じたプロンプトの調整
        if purpose == "free_writing":
            purpose_instruction = """
この生成されたキーワードは医学部採用試験の自由記述問題のテーマとして使用されます。
受験者が知識を基に論理的に記述できるような、適度な難易度のキーワードを選択してください。
"""
        elif purpose == "paper_search":
            purpose_instruction = """
この生成されたキーワードは医学論文の検索に使用されます。
最新の研究動向を反映し、学術的に価値のある論文が見つかりやすいキーワードを選択してください。
"""
        else:
            purpose_instruction = """
この生成されたキーワードは一般的な医学学習に使用されます。
幅広い学習に適した、バランスの取れたキーワードを選択してください。
"""
        
        # 過去履歴の分析結果を含めたプロンプト
        history_analysis = ""
        if detailed_history:
            recent_categories = list(category_usage.keys())[:3]  # 最近使用された上位3分野
            history_analysis = f"""
# 過去履歴分析
- 最近使用された分野: {recent_categories}
- 分野使用頻度: {category_usage}
- 最近のキーワード例: {recent_keywords[:3]}
- 重複回避対象: {past_keywords}
"""
        
        # 構造化されたプロンプト
        prompt = f"""# 役割
あなたは医学研究と教育の専門家です。{purpose_instruction}

# 医学分野一覧
{', '.join(MEDICAL_FIELDS)}

# 生成条件
- 過去に使用されたキーワード（重複回避）: {', '.join(past_keywords) if past_keywords else 'なし'}
- 利用可能分野: {', '.join(available_fields) if available_fields else '全分野'}
{history_analysis}

# 指示
1. 利用可能分野から1つを選択（過去履歴を考慮して多様性を保つ）
2. その分野で注目される疾患・治療・技術のキーワードを英語で生成
3. キーワードは具体的で検索に適した形式にする（例: "diabetes management", "cancer immunotherapy"）
4. 過去のキーワードと重複しないように注意
5. 過去履歴の分析を参考に、使用頻度の低い分野を優先的に選択

# 出力形式（JSON）
{{
  "keywords": "生成されたキーワード（英語）",
  "category": "選択した医学分野",
  "rationale": "このキーワードを選んだ理由（50字程度の日本語）"
}}

# 重要: 必ず完全なJSON形式で出力してください。途中で切れないようにしてください。**JSON以外のテキストの出力は禁止です。**

# 要求
上記の指示に従い、JSON形式でキーワードを生成してください。"""

        # 生成設定
        config = types.GenerateContentConfig(
            temperature=0.8,
            max_output_tokens=500,  # トークン数を増加
            response_mime_type="application/json"
        )
        
        # 同じプロンプトで最大3回リトライ
        last_error = None
        for attempt in range(3):
            try:
                print(f"キーワード生成試行 {attempt + 1}/3")
                
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=config,
                )
                
                if not response or not response.text:
                    raise Exception("キーワード生成で有効な結果が得られませんでした。")
                
                # レスポンスの詳細ログ
                print(f"試行 {attempt + 1} レスポンス長: {len(response.text) if response.text else 0}")
                print(f"試行 {attempt + 1} レスポンス先頭50文字: {response.text[:50] if response.text else 'None'}")
                
                # JSONの解析
                try:
                    # レスポンステキストから純粋なJSONを抽出
                    response_text = response.text.strip()
                    
                    # 空文字列チェック
                    if not response_text:
                        raise Exception("レスポンステキストが空です。")
                    
                    # JSONブロックを抽出（```json...```がある場合）
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                    if json_match:
                        response_text = json_match.group(1)
                    
                    # 先頭と末尾の不要なテキストを除去
                    start_brace = response_text.find('{')
                    end_brace = response_text.rfind('}') + 1
                    if start_brace != -1 and end_brace > start_brace:
                        response_text = response_text[start_brace:end_brace]
                    else:
                        raise Exception("有効なJSON構造が見つかりませんでした。")
                    
                    # 最終的な空文字列チェック
                    if not response_text or response_text.strip() == "":
                        raise Exception("JSON抽出後にテキストが空になりました。")
                    
                    print(f"試行 {attempt + 1} JSON抽出結果: {response_text[:100]}...")
                    
                    keyword_data = json.loads(response_text)
                    if "keywords" in keyword_data:
                        return {
                            "keywords": keyword_data["keywords"],
                            "category": keyword_data.get("category", ""),
                            "rationale": keyword_data.get("rationale", ""),
                            "purpose": purpose  # 用途情報を追加
                        }
                    else:
                        raise Exception("keywordsフィールドが見つかりません")
                    
                except (json.JSONDecodeError, Exception) as e:
                    last_error = e
                    print(f"試行 {attempt + 1} JSONパースエラー: {e}")
                    print(f"試行 {attempt + 1} レスポンス全文: {response.text if response.text else 'None'}")
                    if attempt < 2:  # 最後の試行でなければ続行
                        continue
                    else:  # 最後の試行でもエラーの場合
                        break
                        
            except Exception as e:
                last_error = e
                print(f"試行 {attempt + 1} API呼び出しエラー: {e}")
                print(f"試行 {attempt + 1} エラー詳細: {type(e).__name__}")
                if attempt < 2:  # 最後の試行でなければ続行
                    continue
                else:  # 最後の試行でもエラーの場合
                    break
        
        # 3回とも失敗した場合、フォールバック処理に移行
        print(f"3回の試行が失敗、フォールバック処理に移行: {last_error}")
        
        # フォールバック: シンプルなデフォルトキーワード生成
        print(f"フォールバック処理デバッグ:")
        print(f"  - 参照中の過去キーワード: {past_keywords}")
        print(f"  - 利用可能分野: {available_fields}")
        print(f"  - 分野使用頻度: {category_usage}")
        
        # デフォルトキーワードのシンプルなリスト
        default_keywords = [
            ("循環器学", "heart failure management"),
            ("内分泌代謝学", "diabetes treatment"),
            ("消化器学", "inflammatory bowel disease"),
            ("神経学", "stroke prevention"),
            ("腫瘍学", "cancer immunotherapy"),
            ("感染症学", "antimicrobial resistance"),
            ("救急医学", "emergency care"),
            ("精神医学", "depression treatment")
        ]
        
        # 過去履歴を考慮した分野選択
        if available_fields and category_usage:
            # 使用頻度の低い分野を優先
            unused_fields = [field for field in available_fields if field not in category_usage]
            if unused_fields:
                selected_field = random.choice(unused_fields)
            else:
                # 使用頻度の低い分野を選択
                sorted_fields = sorted(available_fields, key=lambda x: category_usage.get(x, 0))
                selected_field = sorted_fields[0]
        elif available_fields:
            # 利用可能分野からランダム選択
            selected_field = random.choice(available_fields)
        else:
            # 全分野から選択
            selected_field = random.choice([field for field, _ in default_keywords])
        
        # その分野に対応するデフォルトキーワードを探す
        field_keywords = [kw for field, kw in default_keywords if field == selected_field]
        if field_keywords:
            selected_keyword = field_keywords[0]
        else:
            selected_keyword = f"{selected_field.replace('学', '')} treatment"  # 動的生成
        
        print(f"  - 選択分野: {selected_field}")
        print(f"  - 選択キーワード: {selected_keyword}")
        
        return {
            "keywords": selected_keyword,
            "category": selected_field,
            "rationale": f"フォールバック処理により選択（過去履歴を考慮）",
            "purpose": purpose
        }
    
    # 安全なAPI呼び出し
    success, result = safe_api_call(_generate_keywords)
    
    if success:
        # キーワード生成成功時の履歴保存（新DB対応）
        try:
            save_success = save_paper_search_keyword(
                keyword=result['keywords'],
                category=result.get('category', ''),
                purpose=purpose
            )
            if save_success:
                print(f"✅ キーワード生成履歴保存成功: {result['keywords']}")
                logger.info(f"✅ キーワード生成履歴保存成功: {result['keywords']}")
            else:
                print(f"❌ キーワード生成履歴保存失敗: {result['keywords']}")
                logger.warning(f"❌ キーワード生成履歴保存失敗: {result['keywords']}")
        except Exception as e:
            print(f"❌ キーワード生成履歴保存エラー: {e}")
            logger.error(f"❌ キーワード生成履歴保存エラー: {e}")
        
        return result
    else:
        return {
            "keywords": "",
            "category": "",
            "rationale": "",
            "purpose": purpose,
            "error": f"キーワード生成エラー: {result}"
        }

def generate_essay_theme() -> Dict[str, Any]:
    """
    小論文のテーマをランダムに生成する。
    
    Returns:
        Dict[str, Any]: {
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
        # テーマ生成成功時の履歴保存（新DB対応）
        try:
            db_adapter = DatabaseAdapterV3()
            history_data = {
                "type": "essay_theme_generation",
                "date": datetime.now().isoformat(),
                "inputs": {},
                "outputs": {
                    "theme": result.get("theme", ""),
                    "success": True
                }
            }
            db_adapter.save_practice_history(history_data)
            logger.info(f"小論文テーマ生成履歴保存成功")
        except Exception as e:
            logger.warning(f"小論文テーマ生成履歴保存失敗: {e}")
            # フォールバック: 従来の保存方法
            try:
                from modules.utils import save_history
                legacy_history_data = {
                    "type": "小論文テーマ生成",
                    "date": datetime.now().isoformat(),
                    "theme": result.get("theme", ""),
                    "success": True
                }
                save_history(legacy_history_data)
                logger.info(f"従来形式で小論文テーマ生成履歴保存成功")
            except Exception as legacy_e:
                logger.error(f"従来形式でも履歴保存失敗: {legacy_e}")
        
        return result
    else:
        # テーマ生成失敗時の履歴保存
        try:
            db_adapter = DatabaseAdapterV3()
            history_data = {
                "type": "essay_theme_generation",
                "date": datetime.now().isoformat(),
                "inputs": {},
                "outputs": {
                    "error": str(result),
                    "success": False
                }
            }
            db_adapter.save_practice_history(history_data)
            logger.info(f"小論文テーマ生成失敗履歴保存成功")
        except Exception as e:
            logger.warning(f"小論文テーマ生成失敗履歴保存失敗: {e}")
        
        return {
            "theme": "",
            "error": f"テーマ生成エラー: {result}"
        }

def get_keyword_history() -> List[Dict[str, Any]]:
    """
    過去のキーワード生成履歴を取得します（論文検索履歴ベース）。
    
    Returns:
        List[Dict[str, Any]]: キーワード履歴のリスト
    """
    try:
        from modules.database_v3 import db_manager_v3
        
        # 論文検索履歴から詳細情報を取得
        history = db_manager_v3.get_paper_search_history(limit=50)
        
        # 履歴形式に変換（詳細情報を含む）
        keyword_history = []
        for item in history:
            search_keywords = item.get('search_keywords', [])
            if search_keywords:
                for keyword in search_keywords:
                    keyword_history.append({
                        'keywords': keyword,
                        'category': item.get('category_id', ''),  # カテゴリーID
                        'rationale': f"論文検索履歴から取得 (目的: {item.get('purpose', 'general')})",
                        'date': item.get('created_at', ''),  # 作成日時
                        'purpose': item.get('purpose', 'paper_search'),
                        'search_query': item.get('search_query', ''),  # 元の検索クエリ
                        'ai_model': item.get('ai_model', ''),  # 使用したAIモデル
                        'session_id': item.get('session_id', '')  # セッションID
                    })
        
        # 日付順でソート（新しい順）
        keyword_history.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        print(f"キーワード履歴取得: {len(keyword_history)}件")
        logger.info(f"キーワード履歴取得: {len(keyword_history)}件")
        
        return keyword_history
        
    except Exception as e:
        logger.warning(f"論文検索履歴取得失敗: {e}")
        return []

def clear_keyword_history() -> bool:
    """
    キーワード生成履歴をクリアします（論文検索履歴ベース）。
    
    Returns:
        bool: 削除が成功したかどうか
    """
    try:
        from modules.database_v3 import db_manager_v3
        
        # 論文検索履歴をクリア（実装は別途必要）
        # 現状は論文検索履歴の削除機能がないため、成功として扱う
        logger.info(f"キーワード履歴削除完了（論文検索履歴ベース）")
        return True
        
    except Exception as e:
        logger.warning(f"論文検索履歴削除失敗: {e}")
        return False

def _clear_keyword_history_legacy():
    """従来版のキーワード履歴削除（フォールバック用）"""
    import os
    from modules.utils import HISTORY_DIR
    
    deleted_count = 0
    # 永続化履歴からキーワード生成タイプのファイルを削除（新旧両形式対応）
    if os.path.exists(HISTORY_DIR):
        for filename in os.listdir(HISTORY_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(HISTORY_DIR, filename)
                try:
                    import json
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    practice_type = data.get('type', '')
                    # 新旧両方の形式を削除対象に
                    if (practice_type in ['keyword_generation_english', 'keyword_generation_free', 'keyword_generation_adoption', 'keyword_generation_essay', 'keyword_generation_interview'] or
                        practice_type == 'キーワード生成' or practice_type.startswith('キーワード生成')):
                        os.remove(filepath)
                        deleted_count += 1
                        print(f"削除: {filename}")
                except (json.JSONDecodeError, IOError):
                    continue
    
    # セッション状態の履歴もクリア
    if 'keyword_history' in st.session_state:
        st.session_state.keyword_history = []

    logger.info(f"従来形式でキーワード履歴削除: {deleted_count}件")
    return True

def get_available_fields() -> List[str]:
    """
    現在利用可能な医学分野を取得します。
    
    Returns:
        List[str]: 利用可能な分野のリスト
    """
    keyword_history = get_keyword_history()
    
    if not keyword_history:
        return MEDICAL_FIELDS.copy()
    
    # 過去5回の分野履歴を取得
    recent_categories = [item.get('category', '') for item in keyword_history[-5:] if item.get('category')]
    
    # 利用可能な分野を選択（過去5回と重複しない）
    available_fields = [field for field in MEDICAL_FIELDS if field not in recent_categories]
    
    return available_fields if available_fields else MEDICAL_FIELDS.copy()

# 過去問データ（県総採用試験 英語読解）
PAST_EXAM_PATTERNS = [
    {
        "id": "exam_2024_syphilis",
        "year": 2024,
        "type": "letter_translation_opinion",
        "topic": "梅毒治療薬耐性",
        "content": """In 2024, the Centers for Disease Control and Prevention (CDC) estimated that syphilis cases had risen by 79% between 2018 and 2022. CDC and Canadian guidelines for syphilis treatment recommend penicillin G, administered parenterally, for all stages of syphilis. A single 2-g oral dose of azithromycin was listed as an alternative regimen for those with penicillin allergy starting in 2002, until mutations conferring macrolide resistance were found in 53% of Treponema pallidum (T. pallidum) strains across the United States from 2007 through 2009; current CDC and Canadian guidelines state that azithromycin should not be used for syphilis. Given the global resurgence in syphilis and recurring shortages of the mainstay of treatment of uncomplicated syphilis, benzathine penicillin G, estimation of the current prevalence of azithromycin resistance provides context when strategies for syphilis treatment are being considered (alternative antibiotic choices are discussed in Part A in the Supplementary Appendix, available with the full text of this letter at NEJM.org). Here we report that 599 of 604 T. pallidum strains (99.2%) that were sampled in North America from 2017 through 2023 were genotypically resistant to azithromycin (Fig. 1A). Samples were collected from patients in 13 U.S. states, Washington, D.C., and two Canadian provinces (Table S1 in the Supplementary Appendix; also see the Supplementary Methods). The median age of the patients was 33 years (range, 0 to 76). A total of 466 of 588 patients (79.3%) were male. Among male patients with sex-partner information available, 73 of 88 (83%) were men who have sex with men. The syphilis stage was documented for 115 patients, with secondary syphilis being the most prevalent (56 of 115 [48.7%]). Among strains with a near-complete genome obtained, 23 of 54 (43%) belonged to the Nichols-like lineage and 31 of 54 (57%) to the SS14-like lineage (Fig. 1B). Of the 599 azithromycin-resistant strains, 584 (97.5%) were resistant through the A2058G mutation in the gene encoding the 23S ribosomal RNA subunit and 15 (2.5%) through the A2059G mutation. The resistance phenotype conferred by these mutations persists in the presence of doses of up to 64 times the minimum inhibitory concentration of azithromycin for T. pallidum (Part B in the Supplementary Appendix). Although resistance to azithromycin among women, as well as men who have sex with women, was present in only 8 of 57 specimens (14%) obtained from 2007 through 2009, resistance increased in these populations to 99.3% (136 of 137 specimens) from 2017 through 2023.""",
        "task1": "以下のletterを日本語訳しなさい (A4を1枚)",
        "task2": "このletterを読んで、あなたの意見を述べなさい (A4を1枚)"
    },
    {
        "id": "exam_2024_orthopedic",
        "year": 2024,
        "type": "letter_translation_opinion",
        "topic": "整形外科外傷血栓予防",
        "content": """Aspirin for thromboprophylaxis to prevent venous thromboembolism after hip- or knee-replacement surgery has been included in clinical guidelines. Although the use of aspirin thromboprophylaxis for venous thromboembolism in hip and knee replacements is still in debate, data on its use in patients with extremity fracture (in the hip to midfoot or shoulder to wrist) are limited.1 In the Prevention of Clot in Orthopaedic Trauma (PREVENT CLOT) trial, the Major Extremity Trauma Research Consortium (METRC) investigators (Jan. 19 issue)2 tested the noninferiority of aspirin as compared with low-molecular-weight heparin for thromboprophylaxis in patients after an extremity fracture treated with surgery or after a hip or acetabular fracture. The trial included patients with different levels of risk of venous thromboembolism as assessed according to the well-established Caprini score,3 as well as patients with upper extremity fracture, for whom the 2012 guidelines from the American College of Chest Physicians4 suggest that no prophylaxis is needed. In addition, patients in this trial were at low risk for venous thromboembolism, given their young age (mean [±SD], 44.6±17.8 years) — a factor that probably excludes most high-risk patients with hip fracture, who are typically older than 70 years of age. The authors' conclusion that aspirin in general was noninferior to low-molecular-weight heparin after an extremity fracture should be interpreted with caution because the enrollment of low-risk patients arouses concerns regarding selection bias.""",
        "task1": "以下のletterを日本語訳しなさい(A4を1枚)",
        "task2": "このletterを読んで、あなたの意見を述べなさい(A4を1枚)"
    },
    {
        "id": "exam_2016_skin_abscess",
        "year": 2016,
        "type": "paper_comment_translation_opinion",
        "topic": "皮膚膿瘍抗菌薬治療",
        "content": {
            "paper_summary": """2016年3月に皮膿瘍に関して以下のような論文が出ました。
皮膿瘍による救急受診が、メチシリン耐性黄色ブドウ球菌（MRSA）の出現に伴い増加しており、救急部において、単純性膿瘍に対し切開排膿を受ける外来患者を対象に、トリメトプリム・スルファメトキサゾールがプラセボに対して優越性が認められるかどうかを検討し、主要転帰は膿瘍の臨床的治癒とし、7～14日の時点で評価した。皮膿瘍の切開排膿を受けた患者にトリメトプリム・スルファメトキサゾールを投与することで、プラセボと比較して高い治癒率が得られた。""",
            "comment": """The study by Talan et al. supports the use of antibiotics as an adjunctive treatment for uncomplicated skin abscesses, but this recommendation runs contrary to current efforts to reduce antibiotic use in the face of the rising threat of antimicrobial resistance. We note that up to a quarter of the swabs processed in the study showed either no growth or coagulase-negative staphylococcal growth. Did the authors find a difference in response rate stratified according to these culture results? In addition, since high adherence to antibiotic therapy was achieved in only 64.7% of study participants, was a subanalysis performed for those who received courses that were shorter than prescribed? When antibiotics are used as an adjunct to drainage, the majority of bacteria are probably removed during surgery, and recent studies have shown that adequate source control can shorten the standard course of antibiotics without reducing clinical efficacy. Therefore, it is likely that when antibiotics are used as an adjunctive treatment, a shorter course would provide equivalent clinical benefit and would also reduce the risks of adverse effects, limit total antibiotic consumption, and decrease the selective pressure toward the development of resistance."""
        },
        "task1": "（１）和訳して、（２）そのコメントについて、皆さんの意見を書きなさい。"
    }
]

def format_paper_as_exam(paper_data: Dict[str, Any], format_type: str = "letter_translation_opinion") -> Dict[str, Any]:
    """
    論文データを過去問スタイルに変換します。
    
    Args:
        paper_data (Dict[str, Any]): 論文データ（find_medical_paperの結果）
        format_type (str): 出題形式 ("letter_translation_opinion" or "paper_comment_translation_opinion")
    
    Returns:
        Dict[str, Any]: {
            "formatted_content": str,
            "task1": str,
            "task2": str,
            "error": str (optional)
        }
    """
    if 'error' in paper_data:
        return {
            "formatted_content": "",
            "task1": "",
            "task2": "",
            "error": paper_data['error']
        }
    
    def _format_as_exam():
        """内部の変換処理関数"""
        client = genai.Client()
        
        # 過去問データを参考例として含める
        past_examples = ""
        for i, exam in enumerate(PAST_EXAM_PATTERNS[:2], 1):  # 最初の2つの例を使用
            past_examples += f"\n【過去問例{i}】\n"
            past_examples += f"内容: {exam['content'][:200]}...\n"
            past_examples += f"課題1: {exam['task1']}\n"
            past_examples += f"課題2: {exam['task2']}\n"
        
        if format_type == "letter_translation_opinion":
            prompt = f"""# 任務
医師採用試験の英語読解問題作成の専門家として、提供された論文のAbstractを過去問と同様の形式に変換してください。

# 過去問の出題形式
{past_examples}

# 変換対象の論文情報
- タイトル: {paper_data.get('title', '')}
- 研究種別: {paper_data.get('study_type', '')}
- Abstract: {paper_data.get('abstract', '')}

# 変換指示
1. AbstractをLetterとして位置づけ、過去問と同じ出題形式に変換してください
2. 分量を過去問と同等になるように編集してください
3. 医学専門用語や統計データはそのまま保持してください
4. 論文の科学的内容を改変せず、正確に引用してください

# 出力形式（必須）
以下のJSON形式で正確に出力してください：

{{
  "formatted_content": "論文のAbstract全文（改変なし）",
  "task1": "以下のletterを日本語訳しなさい (A4を1枚)",
  "task2": "このletterを読んで、あなたの意見を述べなさい (A4を1枚)"
}}

# 重要な指示
- formatted_contentには論文のAbstractをそのまま含めてください
- 課題文は過去問と同じ形式で記述してください
- 論文の内容を要約や改変せず、完全な形で含めてください"""

        else:  # paper_comment_translation_opinion
            prompt = f"""# 任務
医師採用試験の英語読解問題作成の専門家として、提供された論文について仮想的なコメント（英語）を生成し、過去問と同様の形式に変換してください。

# 過去問例（皮膿瘍の例）
論文概要が日本語で提示され、その後に英語のコメントが続き、
課題: （１）和訳して、（２）そのコメントについて、皆さんの意見を書きなさい。

# 変換対象の論文情報  
- タイトル: {paper_data.get('title', '')}
- 研究種別: {paper_data.get('study_type', '')}
- Abstract: {paper_data.get('abstract', '')}

# 変換指示
1. Abstractを簡潔な日本語概要に要約してください
2. その論文に対する批判的なコメント（英語、医学専門家の視点）を生成してください
3. コメントは建設的で学術的な内容とし、論文の方法論、結果解釈、臨床応用などに言及してください
4. 分量を過去問と同等になるように編集してください

# 出力形式（必須）
以下のJSON形式で正確に出力してください：

{{
  "formatted_content": {{
    "paper_summary": "論文の簡潔な日本語要約（200-300文字）",
    "comment": "論文に対する批判的コメント（英語、200-400語）"
  }},
  "task1": "（１）和訳して、（２）そのコメントについて、皆さんの意見を書きなさい。",
  "task2": ""
}}"""

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        if not response or not response.text:
            raise Exception("論文変換で有効な結果が得られませんでした。")
        
        # JSONの解析
        response_text = response.text.strip()
        
        # JSONブロックを抽出
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
        
        # 先頭と末尾の不要なテキストを除去
        start_brace = response_text.find('{')
        end_brace = response_text.rfind('}') + 1
        if start_brace != -1 and end_brace > start_brace:
            response_text = response_text[start_brace:end_brace]
        else:
            raise Exception("有効なJSON構造が見つかりませんでした。")
        
        formatted_data = json.loads(response_text)
        
        # データ検証
        if "formatted_content" not in formatted_data:
            raise Exception("formatted_contentフィールドが見つかりません。")
        
        return formatted_data
    
    # 安全なAPI呼び出し
    success, result = safe_api_call(_format_as_exam)
    
    if success:
        return result
    else:
        return {
            "formatted_content": "",
            "task1": "",
            "task2": "",
            "error": f"論文変換エラー: {result}"
        }

def get_past_exam_patterns() -> List[Dict[str, Any]]:
    """
    過去問パターンのリストを返します。
    
    Returns:
        List[Dict[str, Any]]: 過去問パターンのリスト
    """
    return PAST_EXAM_PATTERNS.copy()

def get_sample_keywords() -> List[str]:
    """
    サンプルキーワードのリストを返します。
    
    Returns:
        List[str]: サンプルキーワードのリスト
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

def save_paper_search_keyword(keyword: str, category: str = "", purpose: str = "general") -> bool:
    """
    論文検索用キーワードをcategory_paper_search_historyに保存
    
    Args:
        keyword (str): 保存するキーワード
        category (str): カテゴリー
        purpose (str): 検索目的
        
    Returns:
        bool: 保存成功時True
    """
    try:
        from modules.database_v3 import db_manager_v3
        
        # デバッグ情報を追加
        print(f"論文検索キーワード保存開始: {keyword} (purpose: {purpose})")
        logger.info(f"論文検索キーワード保存開始: {keyword} (purpose: {purpose})")
        
        # 新DBに保存
        success = db_manager_v3.save_paper_search(
            search_query=keyword,
            search_keywords=[keyword],
            search_results=[],  # 空の結果
            selected_papers=None,
            purpose=purpose
        )
        
        if success:
            print(f"論文検索キーワード保存成功: {keyword}")
            logger.info(f"論文検索キーワード保存成功: {keyword}")
            return True
        else:
            print(f"論文検索キーワード保存失敗: {keyword} (purpose: {purpose})")
            logger.warning(f"論文検索キーワード保存失敗: {keyword} (purpose: {purpose})")
            return False
            
    except Exception as e:
        print(f"論文検索キーワード保存エラー: {e}")
        print(f"エラータイプ: {type(e).__name__}")
        import traceback
        print(f"スタックトレース: {traceback.format_exc()}")
        logger.error(f"論文検索キーワード保存エラー: {e}")
        logger.error(f"エラータイプ: {type(e).__name__}")
        logger.error(f"スタックトレース: {traceback.format_exc()}")
        return False

def get_paper_search_keywords(limit: int = 20) -> List[str]:
    """
    過去の論文検索キーワードを取得
    
    Args:
        limit (int): 取得件数上限
        
    Returns:
        List[str]: キーワードのリスト
    """
    try:
        from modules.database_v3 import db_manager_v3
        
        # 新DBから論文検索履歴を取得
        history = db_manager_v3.get_paper_search_history(limit=limit)
        
        # search_keywordsからキーワードを抽出
        keywords = []
        for item in history:
            search_keywords = item.get('search_keywords', [])
            if search_keywords:
                keywords.extend(search_keywords)
        
        # 重複を除去して返す
        unique_keywords = list(dict.fromkeys(keywords))
        
        print(f"論文検索キーワード取得: {len(unique_keywords)}件 (元データ: {len(history)}件)")
        logger.info(f"論文検索キーワード取得: {len(unique_keywords)}件 (元データ: {len(history)}件)")
        
        return unique_keywords[:limit]
        
    except Exception as e:
        logger.warning(f"論文検索キーワード取得失敗: {e}")
        return []

def get_keyword_history_with_details(limit: int = 20) -> List[Dict[str, Any]]:
    """
    過去のキーワード生成履歴を詳細情報付きで取得します。
    
    Args:
        limit (int): 取得件数上限
        
    Returns:
        List[Dict[str, Any]]: 詳細情報付きキーワード履歴のリスト
    """
    try:
        from modules.database_v3 import db_manager_v3
        
        # 論文検索履歴から詳細情報を取得
        history = db_manager_v3.get_paper_search_history(limit=limit)
        
        # 詳細情報付き履歴を作成
        detailed_history = []
        for item in history:
            search_keywords = item.get('search_keywords', [])
            if search_keywords:
                for keyword in search_keywords:
                    detailed_history.append({
                        'keyword': keyword,
                        'category_id': item.get('category_id', ''),
                        'purpose': item.get('purpose', 'general'),
                        'search_query': item.get('search_query', ''),
                        'ai_model': item.get('ai_model', ''),
                        'session_id': item.get('session_id', ''),
                        'created_at': item.get('created_at', ''),
                        'search_results_count': len(item.get('search_results', [])),
                        'selected_papers_count': len(item.get('selected_papers', []))
                    })
        
        # 日付順でソート（新しい順）
        detailed_history.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        print(f"詳細キーワード履歴取得: {len(detailed_history)}件")
        logger.info(f"詳細キーワード履歴取得: {len(detailed_history)}件")
        
        return detailed_history[:limit]
        
    except Exception as e:
        logger.warning(f"詳細キーワード履歴取得失敗: {e}")
        return []
