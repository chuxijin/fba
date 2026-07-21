ALTER TABLE render_book_job
    ADD COLUMN template_version VARCHAR(32) NOT NULL DEFAULT '1.0.0' AFTER template_key;

ALTER TABLE render_book_job
    ADD COLUMN template_digest VARCHAR(64) NOT NULL DEFAULT '' AFTER template_version;

CREATE INDEX idx_render_book_job_template_version
    ON render_book_job(template_key, template_version);
