CREATE TABLE IF NOT EXISTS render_book_job (
    id BIGINT PRIMARY KEY,
    job_id VARCHAR(64) NOT NULL,
    user_id BIGINT DEFAULT NULL,
    template_key VARCHAR(100) NOT NULL,
    mode VARCHAR(16) NOT NULL DEFAULT 'final',
    status VARCHAR(16) NOT NULL DEFAULT 'accepted',
    title VARCHAR(200) NOT NULL,
    subtitle VARCHAR(200) DEFAULT NULL,
    subject VARCHAR(100) DEFAULT NULL,
    book_kind VARCHAR(32) DEFAULT NULL,
    solution_mode VARCHAR(32) DEFAULT NULL,
    filters JSONB DEFAULT NULL,
    options JSONB DEFAULT NULL,
    output_targets JSONB DEFAULT NULL,
    render_variants JSONB DEFAULT NULL,
    metadata JSONB DEFAULT NULL,
    payload_path VARCHAR(500) DEFAULT NULL,
    question_count INTEGER DEFAULT NULL,
    material_count INTEGER DEFAULT NULL,
    output_path VARCHAR(1000) DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    del_flag BOOLEAN NOT NULL DEFAULT FALSE,
    created_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMPTZ DEFAULT NULL,
    CONSTRAINT ck_render_book_job_mode CHECK (mode IN ('preview','final')),
    CONSTRAINT ck_render_book_job_status CHECK (status IN ('accepted','running','succeeded','failed')),
    CONSTRAINT ck_render_book_job_book_kind CHECK (
        book_kind IS NULL OR book_kind IN ('module','wrong','exam','custom')
    ),
    CONSTRAINT ck_render_book_job_solution_mode CHECK (
        solution_mode IS NULL OR solution_mode IN ('none','separate','inline','appendix')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_render_book_job_job_id ON render_book_job(job_id);
CREATE INDEX IF NOT EXISTS idx_render_book_job_status_created ON render_book_job(status, created_time);
CREATE INDEX IF NOT EXISTS idx_render_book_job_user_created ON render_book_job(user_id, created_time);
CREATE INDEX IF NOT EXISTS idx_render_book_job_template ON render_book_job(template_key);

CREATE TABLE IF NOT EXISTS render_book_job_file (
    id BIGINT PRIMARY KEY,
    render_job_id BIGINT NOT NULL REFERENCES render_book_job(id) ON DELETE CASCADE,
    file_kind VARCHAR(32) NOT NULL,
    render_variant VARCHAR(32) DEFAULT NULL,
    storage_type VARCHAR(16) NOT NULL DEFAULT 'local',
    status VARCHAR(16) NOT NULL DEFAULT 'available',
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100) NOT NULL DEFAULT 'application/pdf',
    size_bytes BIGINT DEFAULT NULL,
    local_path VARCHAR(500) DEFAULT NULL,
    object_key VARCHAR(500) DEFAULT NULL,
    url VARCHAR(1000) DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMPTZ DEFAULT NULL,
    CONSTRAINT ck_render_book_job_file_kind CHECK (file_kind IN ('question_pdf','solution_pdf','combined_pdf')),
    CONSTRAINT ck_render_book_job_file_variant CHECK (
        render_variant IS NULL OR render_variant IN (
            'questions_only','solutions_only','combined_inline','combined_appendix'
        )
    ),
    CONSTRAINT ck_render_book_job_file_storage CHECK (storage_type IN ('local','oss')),
    CONSTRAINT ck_render_book_job_file_status CHECK (status IN ('available','failed'))
);

CREATE INDEX IF NOT EXISTS idx_render_book_job_file_job_kind ON render_book_job_file(render_job_id, file_kind);

COMMENT ON TABLE render_book_job IS '题本渲染任务表';
COMMENT ON TABLE render_book_job_file IS '题本渲染文件表';
