CREATE TABLE IF NOT EXISTS render_book_job (
    id BIGSERIAL PRIMARY KEY,
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
    id BIGSERIAL PRIMARY KEY,
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

CREATE TABLE IF NOT EXISTS render_book_template_preset (
    id BIGSERIAL PRIMARY KEY,
    template_key VARCHAR(100) NOT NULL,
    preset_name VARCHAR(120) NOT NULL,
    description VARCHAR(500) DEFAULT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    payload JSONB DEFAULT NULL,
    remark TEXT DEFAULT NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMPTZ DEFAULT NULL,
    CONSTRAINT uq_render_book_template_preset_name UNIQUE (template_key, preset_name)
);

CREATE INDEX IF NOT EXISTS idx_render_book_template_preset_template
    ON render_book_template_preset(template_key, sort_order, created_time);
CREATE INDEX IF NOT EXISTS idx_render_book_template_preset_active
    ON render_book_template_preset(template_key, is_active);

COMMENT ON TABLE render_book_job IS '题本渲染任务表';
COMMENT ON TABLE render_book_job_file IS '题本渲染文件表';
COMMENT ON TABLE render_book_template_preset IS '题本模板预设表';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM sys_menu
        WHERE name = 'PluginRenderBook'
    ) THEN
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
        VALUES (
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
        );
    END IF;
END $$;
