-- 系统分类文档关联表
-- schema = fba
-- 前置依赖：fba.sys_category 已存在

BEGIN;

CREATE TABLE IF NOT EXISTS fba.sys__doc_binding (
  id BIGSERIAL NOT NULL,
  category_id BIGINT NOT NULL,
  halo_project_name VARCHAR(64) NOT NULL,
  halo_project_version_name VARCHAR(64) NOT NULL,
  halo_tree_name VARCHAR(64) NOT NULL,
  halo_doc_name VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL,
  relation_type VARCHAR(32) NOT NULL DEFAULT 'teaching',
  category_code VARCHAR(64),
  category_path VARCHAR(512),
  halo_doc_path VARCHAR(255),
  halo_permalink VARCHAR(512),
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  sort_order INTEGER NOT NULL DEFAULT 0,
  extra_data JSONB,
  created_by INTEGER NOT NULL,
  updated_by INTEGER,
  created_time TIMESTAMP WITH TIME ZONE NOT NULL,
  updated_time TIMESTAMP WITH TIME ZONE,
  deleted BIGINT NOT NULL DEFAULT '0',
  deleted_time TIMESTAMP WITH TIME ZONE,
  PRIMARY KEY (id),
  CONSTRAINT uq_sys_doc_binding_category_tree_deleted UNIQUE (
    category_id, relation_type, halo_tree_name, deleted
  ),
  CONSTRAINT fk_sys_doc_binding_category FOREIGN KEY(category_id)
    REFERENCES fba.sys_category (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_sys_doc_binding_id ON fba.sys__doc_binding (id);
CREATE INDEX IF NOT EXISTS idx_sys_doc_binding_category_enabled
  ON fba.sys__doc_binding (category_id, enabled, sort_order);
CREATE INDEX IF NOT EXISTS idx_sys_doc_binding_halo_tree ON fba.sys__doc_binding (halo_tree_name);
CREATE INDEX IF NOT EXISTS idx_sys_doc_binding_halo_doc ON fba.sys__doc_binding (halo_doc_name);

COMMENT ON TABLE fba.sys__doc_binding IS '系统分类文档关联表';
COMMENT ON COLUMN fba.sys__doc_binding.category_id IS '系统分类 ID';
COMMENT ON COLUMN fba.sys__doc_binding.relation_type IS '关联类型';
COMMENT ON COLUMN fba.sys__doc_binding.halo_tree_name IS 'DocTree 节点资源名称';
COMMENT ON COLUMN fba.sys__doc_binding.halo_doc_name IS 'Doc 正文资源名称';

COMMIT;
