CREATE TABLE IF NOT EXISTS render_book_job (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL,
    user_id BIGINT NULL,
    template_key VARCHAR(100) NOT NULL,
    template_version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
    template_digest VARCHAR(64) NOT NULL DEFAULT '',
    mode VARCHAR(16) NOT NULL DEFAULT 'final',
    status VARCHAR(16) NOT NULL DEFAULT 'accepted',
    title VARCHAR(200) NOT NULL,
    subtitle VARCHAR(200) NULL,
    subject VARCHAR(100) NULL,
    book_kind VARCHAR(32) NULL,
    solution_mode VARCHAR(32) NULL,
    filters JSON NULL,
    options JSON NULL,
    output_targets JSON NULL,
    render_variants JSON NULL,
    metadata JSON NULL,
    payload_path VARCHAR(500) NULL,
    question_count INT NULL,
    material_count INT NULL,
    output_path VARCHAR(1000) NULL,
    error_message LONGTEXT NULL,
    del_flag BOOLEAN NOT NULL DEFAULT FALSE,
    created_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_time DATETIME(6) NULL DEFAULT NULL,
    UNIQUE KEY uq_render_book_job_job_id (job_id),
    KEY idx_render_book_job_status_created (status, created_time),
    KEY idx_render_book_job_user_created (user_id, created_time),
    KEY idx_render_book_job_template (template_key),
    KEY idx_render_book_job_template_version (template_key, template_version),
    CONSTRAINT ck_render_book_job_mode CHECK (mode IN ('preview','final')),
    CONSTRAINT ck_render_book_job_status CHECK (status IN ('accepted','running','succeeded','failed')),
    CONSTRAINT ck_render_book_job_book_kind CHECK (book_kind IS NULL OR book_kind IN ('module','wrong','exam','custom')),
    CONSTRAINT ck_render_book_job_solution_mode CHECK (
        solution_mode IS NULL OR solution_mode IN ('none','separate','inline','appendix')
    )
) COMMENT='题本渲染任务表';

CREATE TABLE IF NOT EXISTS render_book_job_file (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    render_job_id BIGINT NOT NULL,
    file_kind VARCHAR(32) NOT NULL,
    render_variant VARCHAR(32) NULL,
    storage_type VARCHAR(16) NOT NULL DEFAULT 'local',
    status VARCHAR(16) NOT NULL DEFAULT 'available',
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    size_bytes BIGINT NULL,
    local_path VARCHAR(500) NULL,
    object_key VARCHAR(500) NULL,
    url VARCHAR(1000) NULL,
    error_message LONGTEXT NULL,
    created_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_time DATETIME(6) NULL DEFAULT NULL,
    KEY idx_render_book_job_file_job_kind (render_job_id, file_kind),
    CONSTRAINT fk_render_book_job_file_job FOREIGN KEY (render_job_id) REFERENCES render_book_job(id) ON DELETE CASCADE,
    CONSTRAINT ck_render_book_job_file_kind CHECK (file_kind IN ('question_pdf','solution_pdf','combined_pdf')),
    CONSTRAINT ck_render_book_job_file_variant CHECK (
        render_variant IS NULL OR render_variant IN (
            'questions_only','solutions_only','combined_inline','combined_appendix'
        )
    ),
    CONSTRAINT ck_render_book_job_file_storage CHECK (storage_type IN ('local','oss')),
    CONSTRAINT ck_render_book_job_file_status CHECK (status IN ('available','failed'))
) COMMENT='题本渲染文件表';

CREATE TABLE IF NOT EXISTS render_book_template_preset (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    template_key VARCHAR(100) NOT NULL,
    preset_name VARCHAR(120) NOT NULL,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INT NOT NULL DEFAULT 0,
    payload JSON NULL,
    remark LONGTEXT NULL,
    created_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_time DATETIME(6) NULL DEFAULT NULL,
    UNIQUE KEY uq_render_book_template_preset_name (template_key, preset_name),
    KEY idx_render_book_template_preset_template (template_key, sort_order, created_time),
    KEY idx_render_book_template_preset_active (template_key, is_active)
) COMMENT='题本模板预设表';

INSERT INTO sys_menu (
    title,
    name,
    path,
    sort,
    icon,
    type,
    component,
    perms,
    status,
    display,
    cache,
    link,
    remark,
    parent_id,
    created_time,
    updated_time
)
SELECT
    '题本模板预览',
    'PluginRenderBook',
    '/plugins/render-book',
    90,
    'carbon:book',
    1,
    '/plugins/render_book/views/index',
    NULL,
    1,
    1,
    1,
    '',
    '题本渲染模板预览与参数调试页面',
    (SELECT id FROM sys_menu WHERE name = 'System' LIMIT 1),
    NOW(),
    NULL
WHERE NOT EXISTS (
    SELECT 1
    FROM sys_menu
    WHERE name = 'PluginRenderBook'
);
