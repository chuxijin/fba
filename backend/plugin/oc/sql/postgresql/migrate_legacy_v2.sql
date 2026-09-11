-- =============================================================================
-- OC 模块 v2 数据迁移脚本（一次性）
-- 源: oc_campus_recruit / oc_intern_recruit（旧爬虫扁平表）
-- 目标: oc_company / oc_company_website / oc_recruit_announcement（公司-网站-公告三表）
--
-- 执行前提:
--   1. 新三表已通过 init.sql（或新代码 create_all）创建
--   2. 新代码已部署（旧爬虫已停写旧表）
--
-- 特性:
--   * 幂等: 全部使用 ON CONFLICT DO NOTHING，可安全重跑；
--     不会覆盖部署后新爬虫已写入的数据
--   * 过期清理（口径 B: 非本季）: 公告仅迁移
--       update_time >= '2026-06-01' 且 (deadline 为空或 >= 执行日)
--     的本季活跃公告；公司/网站全量迁移不受影响
--   * 事务: 建议包在 BEGIN/COMMIT 中执行，出错可整体回滚
--
-- 执行方式:
--   1. 先单独执行下方「预览」段核对三项计数
--   2. 确认后 BEGIN; 执行「迁移」段; 核对; COMMIT;
-- =============================================================================


-- =============================================================================
-- 预览（只读，不写入）
-- =============================================================================

-- 公司数（两表按名去重）
-- 预期约 11,800+
SELECT count(*) AS preview_companies
FROM (
    SELECT company_name FROM oc_campus_recruit
    UNION
    SELECT company_name FROM oc_intern_recruit
) t;

-- 网站数（公司+URL 去重）
-- 预期约 25,400+
SELECT count(*) AS preview_websites
FROM (
    SELECT company_name, apply_link AS url FROM oc_campus_recruit WHERE apply_link IS NOT NULL AND apply_link != ''
    UNION
    SELECT company_name, notice_link FROM oc_campus_recruit WHERE notice_link IS NOT NULL AND notice_link != ''
    UNION
    SELECT company_name, apply_link FROM oc_intern_recruit WHERE apply_link IS NOT NULL AND apply_link != ''
    UNION
    SELECT company_name, notice_link FROM oc_intern_recruit WHERE notice_link IS NOT NULL AND notice_link != ''
) t;

-- 公告数（本季活跃口径）
-- 预期约 2,700+（随执行日与源站置顶变化）
SELECT count(*) AS preview_announcements
FROM (
    SELECT company_name, positions, update_time, deadline FROM oc_campus_recruit
    UNION ALL
    SELECT company_name, positions, update_time, deadline FROM oc_intern_recruit
) t
WHERE t.update_time >= DATE '2026-06-01'
  AND (t.deadline IS NULL OR t.deadline = '' OR t.deadline >= to_char(CURRENT_DATE, 'YYYY-MM-DD'));


-- =============================================================================
-- 迁移（写入，需在事务中执行）
-- =============================================================================

-- BEGIN;

-- -----------------------------------------------------------------------------
-- 1. 公司表：两表 UNION 按名去重
--    代表行选取规则：
--      * 有效信息越多越优先（company_type/industry/company_size 非空计数降序）
--      * 同等信息下取最新（campus 表 row_number 更小 = 更新，因爬虫倒序写入）
--    清洗: '未知' -> NULL, '会员可见' -> NULL, HTML 实体还原
--    幂等: ON CONFLICT (name) DO NOTHING，不覆盖已有公司
-- -----------------------------------------------------------------------------

WITH union_rows AS (
    SELECT
        company_name,
        NULLIF(regexp_replace(company_type, '&(amp|lt|gt|#038|quot);', '', 'g'), '') AS company_type,
        CASE WHEN industry IN ('未知', '') THEN NULL
             ELSE NULLIF(regexp_replace(industry, '&(amp|lt|gt|#038|quot);', '', 'g'), '') END AS industry,
        CASE WHEN company_size IN ('会员可见', '未知', '') THEN NULL
             ELSE NULLIF(regexp_replace(company_size, '&(amp|lt|gt|#038|quot);', '', 'g'), '') END AS company_size,
        update_time,
        1 AS src_priority  -- campus 表优先于 intern（同信息量时）
    FROM oc_campus_recruit
    UNION ALL
    SELECT
        company_name,
        NULLIF(regexp_replace(company_type, '&(amp|lt|gt|#038|quot);', '', 'g'), ''),
        CASE WHEN industry IN ('未知', '') THEN NULL
             ELSE NULLIF(regexp_replace(industry, '&(amp|lt|gt|#038|quot);', '', 'g'), '') END,
        CASE WHEN company_size IN ('会员可见', '未知', '') THEN NULL
             ELSE NULLIF(regexp_replace(company_size, '&(amp|lt|gt|#038|quot);', '', 'g'), '') END,
        update_time,
        2
    FROM oc_intern_recruit
),
ranked AS (
    SELECT
        company_name,
        company_type,
        industry,
        company_size,
        ROW_NUMBER() OVER (
            PARTITION BY company_name
            ORDER BY
                ((company_type IS NOT NULL)::int
                 + (industry IS NOT NULL)::int
                 + (company_size IS NOT NULL)::int) DESC,
                update_time DESC,
                src_priority
        ) AS rn
    FROM union_rows
)
INSERT INTO oc_company (name, company_type, industry, company_size, extra_info)
SELECT
    company_name,
    company_type,
    industry,
    company_size,
    '{}'::jsonb
FROM ranked
WHERE rn = 1
ON CONFLICT (name) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 2. 公司网站表：全量链接按 (公司, URL) 去重
--    命名按来源区分（apply 优先）:
--      apply_link  -> {公司名}投递入口
--      notice_link -> {公司名}招聘公告（仅当与该公司投递链接 URL 不同时）
--    注意: URL 需清理 HTML 实体（如 &#038;），清理后相同视为同一网站
--    幂等: ON CONFLICT (company_id, url) DO NOTHING
-- -----------------------------------------------------------------------------

WITH all_links AS (
    SELECT company_name, apply_link AS url, 'apply' AS src
    FROM oc_campus_recruit WHERE apply_link IS NOT NULL AND apply_link != ''
    UNION ALL
    SELECT company_name, notice_link, 'notice'
    FROM oc_campus_recruit WHERE notice_link IS NOT NULL AND notice_link != ''
    UNION ALL
    SELECT company_name, apply_link, 'apply'
    FROM oc_intern_recruit WHERE apply_link IS NOT NULL AND apply_link != ''
    UNION ALL
    SELECT company_name, notice_link, 'notice'
    FROM oc_intern_recruit WHERE notice_link IS NOT NULL AND notice_link != ''
),
cleaned AS (
    SELECT
        company_name,
        regexp_replace(url, '&(amp|lt|gt|#038|quot);', '', 'g') AS url,
        src
    FROM all_links
),
dedup AS (
    -- 同 URL 只保留一条，'apply' 字典序在前优先于 'notice'
    SELECT DISTINCT ON (company_name, url) company_name, url, src
    FROM cleaned
    ORDER BY company_name, url, src
)
INSERT INTO oc_company_website (company_id, url, name)
SELECT
    c.id,
    d.url,
    c.name || CASE WHEN d.src = 'notice' THEN '招聘公告' ELSE '投递入口' END
FROM dedup d
JOIN oc_company c ON c.name = d.company_name
WHERE d.url IS NOT NULL AND d.url != ''
ON CONFLICT (company_id, url) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 3. 招聘公告表：一帖一公告，全量字段迁移（仅本季活跃）
--    过滤（口径 B）:
--      update_time >= DATE '2026-06-01'
--      AND (deadline 为空 OR >= 执行日)
--    字段映射:
--      title        = {公司名}公告详情
--      source_key   = campus:{id} / intern:{id}（源站 ID 跨表冲突，必须带前缀）
--      end_time     = deadline（实测 100% 为 YYYY-MM-DD）
--      exam_info    = '会员可见' -> NULL
--      remark       = '源站更新: {update_time}'，非默认投递状态附加保留
--      HTML 实体清理: positions / recruitment_type / recruit_target / location / exam_info
--    幂等: ON CONFLICT (source_key) DO NOTHING，不覆盖新爬虫已更新的公告
-- -----------------------------------------------------------------------------

WITH union_jobs AS (
    SELECT
        'campus' AS src,
        id,
        company_name,
        recruitment_type,
        recruit_target,
        positions,
        deadline,
        location,
        exam_info,
        referral_code,
        update_time,
        application_status
    FROM oc_campus_recruit
    UNION ALL
    SELECT
        'intern',
        id,
        company_name,
        recruitment_type,
        recruit_target,
        positions,
        deadline,
        location,
        NULL AS exam_info,
        referral_code,
        update_time,
        application_status
    FROM oc_intern_recruit
),
filtered AS (
    SELECT *
    FROM union_jobs
    WHERE update_time >= DATE '2026-06-01'
      AND (deadline IS NULL OR deadline = '' OR deadline >= to_char(CURRENT_DATE, 'YYYY-MM-DD'))
)
INSERT INTO oc_recruit_announcement (
    company_id, title, recruitment_type, recruit_target, positions,
    start_time, end_time, location, exam_info, referral_code, source_key, remark
)
SELECT
    c.id,
    c.name || '公告详情',
    NULLIF(regexp_replace(f.recruitment_type, '&(amp|lt|gt|#038|quot);', '', 'g'), '') AS recruitment_type,
    NULLIF(regexp_replace(NULLIF(f.recruit_target, ''), '&(amp|lt|gt|#038|quot);', '', 'g'), '') AS recruit_target,
    NULLIF(regexp_replace(f.positions, '&(amp|lt|gt|#038|quot);', '', 'g'), '') AS positions,
    NULL AS start_time,
    NULLIF(f.deadline, '') AS end_time,
    NULLIF(regexp_replace(f.location, '&(amp|lt|gt|#038|quot);', '', 'g'), '') AS location,
    CASE WHEN f.exam_info IN ('会员可见', '') THEN NULL
         ELSE NULLIF(regexp_replace(f.exam_info, '&(amp|lt|gt|#038|quot);', '', 'g'), '') END AS exam_info,
    NULLIF(regexp_replace(f.referral_code, '&(amp|lt|gt|#038|quot);', '', 'g'), '') AS referral_code,
    f.src || ':' || f.id AS source_key,
    '源站更新: ' || to_char(f.update_time, 'YYYY-MM-DD')
        || CASE WHEN f.application_status IS NOT NULL AND f.application_status NOT IN ('', '未投递')
                THEN ' | 投递状态: ' || f.application_status
                ELSE '' END
    AS remark
FROM filtered f
JOIN oc_company c ON c.name = f.company_name
ON CONFLICT (source_key) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 4. 迁移结果核对
-- -----------------------------------------------------------------------------

SELECT
    (SELECT count(*) FROM oc_company) AS companies,
    (SELECT count(*) FROM oc_company_website) AS websites,
    (SELECT count(*) FROM oc_recruit_announcement) AS announcements,
    (SELECT count(*) FROM oc_recruit_announcement WHERE source_key IS NOT NULL) AS announcements_from_migration,
    (SELECT count(*) FROM oc_recruit_announcement WHERE source_key IS NULL) AS announcements_manual;

-- 确认无误后提交:
-- COMMIT;
-- 出错回滚:
-- ROLLBACK;
