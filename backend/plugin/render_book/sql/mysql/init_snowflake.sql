CREATE TABLE IF NOT EXISTS render_book_job (
    id BIGINT NOT NULL PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL,
    user_id BIGINT NULL,
    template_key VARCHAR(100) NOT NULL,
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
    created_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_time DATETIME(6) NULL DEFAULT NULL,
    UNIQUE KEY uq_render_book_job_job_id (job_id),
    KEY idx_render_book_job_status_created (status, created_time),
    KEY idx_render_book_job_user_created (user_id, created_time),
    KEY idx_render_book_job_template (template_key),
    CONSTRAINT ck_render_book_job_mode CHECK (mode IN ('preview','final')),
    CONSTRAINT ck_render_book_job_status CHECK (status IN ('accepted','running','succeeded','failed')),
    CONSTRAINT ck_render_book_job_book_kind CHECK (book_kind IS NULL OR book_kind IN ('module','wrong','exam','custom')),
    CONSTRAINT ck_render_book_job_solution_mode CHECK (
        solution_mode IS NULL OR solution_mode IN ('none','separate','inline','appendix')
    )
) COMMENT='题本渲染任务表';

CREATE TABLE IF NOT EXISTS render_book_job_file (
    id BIGINT NOT NULL PRIMARY KEY,
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
