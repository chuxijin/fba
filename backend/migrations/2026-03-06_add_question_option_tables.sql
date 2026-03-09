-- Add normalized option tables (MySQL)
-- Date: 2026-03-06

CREATE TABLE IF NOT EXISTS study_option_content (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'primary key',
    content_hash VARCHAR(64) NOT NULL COMMENT 'content hash',
    content LONGTEXT NOT NULL COMMENT 'option content',
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    updated_time DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'updated time',
    PRIMARY KEY (id),
    UNIQUE KEY uq_study_option_content_hash (content_hash),
    KEY idx_study_option_content_hash (content_hash)
) COMMENT='option content table';

CREATE TABLE IF NOT EXISTS study_question_option (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'primary key',
    question_id BIGINT NOT NULL COMMENT 'question id',
    option_code VARCHAR(16) NOT NULL COMMENT 'option code',
    content_id BIGINT NOT NULL COMMENT 'option content id',
    sort_order INT NOT NULL DEFAULT 0 COMMENT 'sort order',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'is active',
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    updated_time DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'updated time',
    PRIMARY KEY (id),
    UNIQUE KEY uq_study_question_option_question_code (question_id, option_code),
    KEY idx_study_question_option_question_sort (question_id, sort_order),
    CONSTRAINT fk_study_question_option_question FOREIGN KEY (question_id) REFERENCES study_question(id) ON DELETE CASCADE,
    CONSTRAINT fk_study_question_option_content FOREIGN KEY (content_id) REFERENCES study_option_content(id) ON DELETE RESTRICT
) COMMENT='question option table';

CREATE TABLE IF NOT EXISTS study_question_option_stats (
    id BIGINT NOT NULL AUTO_INCREMENT COMMENT 'primary key',
    placement_id BIGINT NOT NULL COMMENT 'placement id',
    question_id BIGINT NOT NULL COMMENT 'question id',
    option_id BIGINT NOT NULL COMMENT 'option id',
    option_code VARCHAR(16) NOT NULL COMMENT 'option code',
    selected_count INT NOT NULL DEFAULT 0 COMMENT 'selected count',
    correct_selected_count INT NOT NULL DEFAULT 0 COMMENT 'selected count when answer is correct',
    wrong_selected_count INT NOT NULL DEFAULT 0 COMMENT 'selected count when answer is wrong',
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'created time',
    updated_time DATETIME DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP COMMENT 'updated time',
    PRIMARY KEY (id),
    UNIQUE KEY uq_study_question_option_stats_placement_code (placement_id, option_code),
    KEY idx_study_question_option_stats_question (question_id),
    KEY idx_study_question_option_stats_option (option_id),
    CONSTRAINT fk_study_question_option_stats_placement FOREIGN KEY (placement_id) REFERENCES study_question_placement(id) ON DELETE CASCADE,
    CONSTRAINT fk_study_question_option_stats_question FOREIGN KEY (question_id) REFERENCES study_question(id) ON DELETE CASCADE,
    CONSTRAINT fk_study_question_option_stats_option FOREIGN KEY (option_id) REFERENCES study_question_option(id) ON DELETE CASCADE
) COMMENT='question option stats table';

-- Backfill option content dictionary from legacy study_question.options_data JSON.
INSERT INTO study_option_content (content_hash, content, created_time)
SELECT DISTINCT
    SHA2(TRIM(JSON_UNQUOTE(JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.content')))), 256) AS content_hash,
    TRIM(JSON_UNQUOTE(JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.content')))) AS content,
    NOW()
FROM study_question q
JOIN JSON_TABLE(
    JSON_KEYS(q.options_data),
    '$[*]' COLUMNS (
        option_code VARCHAR(16) PATH '$'
    )
) AS keys_tbl
WHERE q.options_data IS NOT NULL
  AND JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.content')) IS NOT NULL
  AND TRIM(JSON_UNQUOTE(JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.content')))) <> ''
ON DUPLICATE KEY UPDATE content = VALUES(content);

-- Backfill question options from legacy study_question.options_data JSON.
INSERT INTO study_question_option (
    question_id,
    option_code,
    content_id,
    sort_order,
    is_active,
    created_time
)
SELECT
    q.id AS question_id,
    UPPER(TRIM(COALESCE(
        JSON_UNQUOTE(JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.code'))),
        keys_tbl.option_code
    ))) AS option_code,
    c.id AS content_id,
    CASE
        WHEN UPPER(TRIM(COALESCE(
            JSON_UNQUOTE(JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.code'))),
            keys_tbl.option_code
        ))) REGEXP '^[A-Z]$' THEN ASCII(UPPER(TRIM(COALESCE(
            JSON_UNQUOTE(JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.code'))),
            keys_tbl.option_code
        )))) - 64
        ELSE 999
    END AS sort_order,
    TRUE AS is_active,
    NOW() AS created_time
FROM study_question q
JOIN JSON_TABLE(
    JSON_KEYS(q.options_data),
    '$[*]' COLUMNS (
        option_code VARCHAR(16) PATH '$'
    )
) AS keys_tbl
JOIN study_option_content c
    ON c.content_hash = SHA2(
        TRIM(JSON_UNQUOTE(JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.content')))),
        256
    )
WHERE q.options_data IS NOT NULL
  AND JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.content')) IS NOT NULL
  AND TRIM(JSON_UNQUOTE(JSON_EXTRACT(q.options_data, CONCAT('$.', keys_tbl.option_code, '.content')))) <> ''
ON DUPLICATE KEY UPDATE
    content_id = VALUES(content_id),
    sort_order = VALUES(sort_order),
    is_active = VALUES(is_active);
