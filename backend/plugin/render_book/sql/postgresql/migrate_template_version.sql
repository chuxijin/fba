ALTER TABLE render_book_job
    ADD COLUMN IF NOT EXISTS template_version VARCHAR(32) NOT NULL DEFAULT '1.0.0';

ALTER TABLE render_book_job
    ADD COLUMN IF NOT EXISTS template_digest VARCHAR(64) NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_render_book_job_template_version
    ON render_book_job(template_key, template_version);
