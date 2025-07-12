-- =====================================================
-- 練習タイプ更新SQL - アプリケーション側マッピングとの統一
-- =====================================================

-- まず既存の練習タイプを確認
SELECT type_name, display_name FROM practice_types ORDER BY category_id, sort_order;

-- =====================================================
-- 練習タイプの更新（アプリケーション側に合わせる）
-- =====================================================

-- 小論文対策: essay_writing → essay_practice
UPDATE practice_types 
SET type_name = 'essay_practice'
WHERE type_name = 'essay_writing';

-- 面接系: interview_single → interview_practice_single
UPDATE practice_types 
SET type_name = 'interview_practice_single'
WHERE type_name = 'interview_single';

-- 面接系: interview_session → interview_practice_session
UPDATE practice_types 
SET type_name = 'interview_practice_session'
WHERE type_name = 'interview_session';

-- 英語読解系: standard_reading → english_reading_standard
UPDATE practice_types 
SET type_name = 'english_reading_standard'
WHERE type_name = 'standard_reading';

-- 英語読解系: past_reading_letter → english_reading_letter_style
UPDATE practice_types 
SET type_name = 'english_reading_letter_style'
WHERE type_name = 'past_reading_letter';

-- 英語読解系: past_reading_comment → english_reading_comment_style
UPDATE practice_types 
SET type_name = 'english_reading_comment_style'
WHERE type_name = 'past_reading_comment';

-- 英語読解系: past_reading_standard → english_reading_comprehensive
UPDATE practice_types 
SET type_name = 'english_reading_comprehensive'
WHERE type_name = 'past_reading_standard';

-- 医学部採用試験系: standard_exam → medical_exam_comprehensive
UPDATE practice_types 
SET type_name = 'medical_exam_comprehensive'
WHERE type_name = 'standard_exam';

-- 医学部採用試験系: past_exam_letter → medical_exam_letter_style
UPDATE practice_types 
SET type_name = 'medical_exam_letter_style'
WHERE type_name = 'past_exam_letter';

-- 医学部採用試験系: past_exam_comment → medical_exam_comment_style
UPDATE practice_types 
SET type_name = 'medical_exam_comment_style'
WHERE type_name = 'past_exam_comment';

-- 医学部採用試験系: past_exam_standard → medical_exam_standard (新規追加)
UPDATE practice_types 
SET type_name = 'medical_exam_standard'
WHERE type_name = 'past_exam_standard';

-- =====================================================
-- 不足している練習タイプの追加
-- =====================================================

-- 論文検索関連の目的別タイプを追加
INSERT INTO practice_types (category_id, type_name, display_name, input_schema, score_schema, sort_order) VALUES
(5, 'paper_search_medical_exam', '論文検索（医学部採用試験用）',
 '{"fields": ["search_keywords", "paper_title", "paper_abstract", "purpose"]}',
 '{"categories": ["関連性", "信頼性"]}', 5),

(5, 'paper_search_english_reading', '論文検索（英語読解用）',
 '{"fields": ["search_keywords", "paper_title", "paper_abstract", "purpose"]}',
 '{"categories": ["関連性", "信頼性"]}', 6),

(5, 'paper_search_general', '論文検索（一般用）',
 '{"fields": ["search_keywords", "paper_title", "paper_abstract", "purpose"]}',
 '{"categories": ["関連性", "信頼性"]}', 7)

ON CONFLICT (type_name) DO NOTHING;

-- =====================================================
-- 既存の不適切なデータのクリーンアップ
-- =====================================================

-- 重複または古いキーワード生成タイプの整理
DELETE FROM practice_types 
WHERE type_name IN ('keyword_generation_paper', 'keyword_generation_writing', 'keyword_generation')
AND practice_type_id NOT IN (
    SELECT MIN(practice_type_id) 
    FROM practice_types 
    WHERE type_name IN ('keyword_generation_paper', 'keyword_generation_writing', 'keyword_generation')
    GROUP BY type_name
);

-- =====================================================
-- 制約とインデックスの再作成
-- =====================================================

-- 一意制約を再作成（type_nameの重複を防ぐ）
DROP INDEX IF EXISTS uk_type_name;
CREATE UNIQUE INDEX uk_type_name ON practice_types(type_name);

-- =====================================================
-- 更新結果の確認
-- =====================================================

-- 更新後の練習タイプ一覧を表示
SELECT 
    pc.category_name,
    pc.display_name as category_display,
    pt.type_name,
    pt.display_name,
    pt.sort_order
FROM practice_types pt
JOIN practice_categories pc ON pt.category_id = pc.category_id
ORDER BY pc.sort_order, pt.sort_order;

-- アプリケーション側マッピングとの対応確認
WITH app_mappings AS (
    SELECT unnest(ARRAY[
        'essay_practice',
        'interview_practice_single',
        'interview_practice_session', 
        'english_reading_standard',
        'english_reading_letter_style',
        'english_reading_comment_style',
        'english_reading_comprehensive',
        'medical_exam_comprehensive',
        'medical_exam_letter_style',
        'medical_exam_comment_style',
        'medical_exam_standard',
        'free_writing',
        'paper_search',
        'paper_search_medical_exam',
        'paper_search_english_reading',
        'paper_search_general'
    ]) as expected_type_name
)
SELECT 
    am.expected_type_name,
    CASE 
        WHEN pt.type_name IS NOT NULL THEN '✅ 存在'
        ELSE '❌ 不足'
    END as status
FROM app_mappings am
LEFT JOIN practice_types pt ON am.expected_type_name = pt.type_name
ORDER BY am.expected_type_name;

-- =====================================================
-- 完了メッセージ
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '✅ 練習タイプの更新が完了しました！';
    RAISE NOTICE '📊 現在の練習タイプ数: %', (SELECT COUNT(*) FROM practice_types WHERE is_active = true);
    RAISE NOTICE '🔄 アプリケーション側マッピングとの統一完了';
    RAISE NOTICE '⚡ 新システムでの練習履歴保存の準備が整いました';
END $$; 