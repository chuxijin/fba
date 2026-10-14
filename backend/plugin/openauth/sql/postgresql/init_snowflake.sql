-- OpenAuth 雪花主键；仅创建插件自己的表，不触碰旧 skill 表
CREATE TABLE openauth_client (
    id bigint PRIMARY KEY,
    client_id varchar(64) NOT NULL,
    client_secret_hash varchar(255) NOT NULL,
    name varchar(100) NOT NULL,
    client_type varchar(20) NOT NULL DEFAULT 'confidential',
    description varchar(500) DEFAULT NULL,
    icon varchar(500) DEFAULT NULL,
    scopes jsonb NOT NULL DEFAULT '[]'::jsonb,
    redirect_uris jsonb NOT NULL DEFAULT '[]'::jsonb,
    status integer NOT NULL DEFAULT 1,
    created_time timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time timestamptz DEFAULT NULL,
    deleted bigint NOT NULL DEFAULT 0,
    deleted_time timestamptz DEFAULT NULL,
    CONSTRAINT uk_openauth_client_client_id UNIQUE (client_id),
    CONSTRAINT openauth_client_status_check CHECK (status IN (0, 1))
);
CREATE INDEX ix_openauth_client_id ON openauth_client (id);
CREATE INDEX ix_openauth_client_client_id ON openauth_client (client_id);
CREATE INDEX ix_openauth_client_status ON openauth_client (status);
COMMENT ON TABLE openauth_client IS '开放平台客户端注册表';

CREATE TABLE openauth_user_authorization (
    id bigint PRIMARY KEY,
    user_id bigint NOT NULL,
    client_id bigint NOT NULL,
    grant_version varchar(36) NOT NULL,
    scopes jsonb NOT NULL DEFAULT '[]'::jsonb,
    status varchar(20) NOT NULL DEFAULT 'active',
    authorized_time timestamptz DEFAULT NULL,
    last_used_time timestamptz DEFAULT NULL,
    created_time timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_time timestamptz DEFAULT NULL,
    deleted bigint NOT NULL DEFAULT 0,
    deleted_time timestamptz DEFAULT NULL,
    CONSTRAINT uk_openauth_user_auth_user_client UNIQUE (user_id, client_id),
    CONSTRAINT fk_openauth_user_auth_client FOREIGN KEY (client_id) REFERENCES openauth_client (id) ON DELETE CASCADE
);
CREATE INDEX ix_openauth_user_authorization_id ON openauth_user_authorization (id);
CREATE INDEX idx_openauth_user_auth_user ON openauth_user_authorization (user_id);
CREATE INDEX idx_openauth_user_auth_client ON openauth_user_authorization (client_id);
COMMENT ON TABLE openauth_user_authorization IS '用户与开放平台客户端的授权关系表';
