CREATE TABLE IF NOT EXISTS plugin_web_analytics_site (
    id BIGSERIAL PRIMARY KEY,
    site_key VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    domains JSONB NOT NULL,
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    heatmap_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    replay_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    replay_sample_rate DOUBLE PRECISION NOT NULL DEFAULT 0.05,
    event_retention_days INTEGER NOT NULL DEFAULT 180,
    replay_retention_days INTEGER NOT NULL DEFAULT 30,
    deleted BIGINT NOT NULL DEFAULT 0,
    deleted_time TIMESTAMPTZ NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_web_analytics_site_key ON plugin_web_analytics_site (site_key);

CREATE TABLE IF NOT EXISTS plugin_web_analytics_session (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL,
    session_key VARCHAR(64) NOT NULL,
    visitor_hash VARCHAR(64) NOT NULL,
    ip_hash VARCHAR(64) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    entry_path VARCHAR(1024) NOT NULL,
    exit_path VARCHAR(1024) NOT NULL,
    referrer VARCHAR(2048) NULL,
    referrer_host VARCHAR(255) NULL,
    utm_source VARCHAR(255) NULL,
    utm_medium VARCHAR(255) NULL,
    utm_campaign VARCHAR(255) NULL,
    country VARCHAR(64) NULL,
    region VARCHAR(64) NULL,
    city VARCHAR(64) NULL,
    browser VARCHAR(128) NULL,
    os VARCHAR(128) NULL,
    device VARCHAR(128) NULL,
    pageviews INTEGER NOT NULL DEFAULT 0,
    event_count INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    deleted BIGINT NOT NULL DEFAULT 0,
    deleted_time TIMESTAMPTZ NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ NULL DEFAULT NOW(),
    CONSTRAINT uq_web_analytics_session_site_key UNIQUE (site_id, session_key)
);
CREATE INDEX IF NOT EXISTS ix_web_analytics_session_site_started ON plugin_web_analytics_session (site_id, started_at);
CREATE INDEX IF NOT EXISTS ix_web_analytics_session_site_visitor ON plugin_web_analytics_session (site_id, visitor_hash);

CREATE TABLE IF NOT EXISTS plugin_web_analytics_event (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL,
    event_key VARCHAR(64) NOT NULL,
    session_key VARCHAR(64) NOT NULL,
    visitor_hash VARCHAR(64) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    path VARCHAR(1024) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    event_name VARCHAR(128) NULL,
    title VARCHAR(512) NULL,
    referrer VARCHAR(2048) NULL,
    properties JSONB NULL,
    screen_width INTEGER NULL,
    screen_height INTEGER NULL,
    viewport_width INTEGER NULL,
    viewport_height INTEGER NULL,
    deleted BIGINT NOT NULL DEFAULT 0,
    deleted_time TIMESTAMPTZ NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ NULL DEFAULT NOW(),
    CONSTRAINT uq_web_analytics_event_site_key UNIQUE (site_id, event_key)
);
CREATE INDEX IF NOT EXISTS ix_web_analytics_event_site_time ON plugin_web_analytics_event (site_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_web_analytics_event_site_type_time ON plugin_web_analytics_event (site_id, event_type, occurred_at);

CREATE TABLE IF NOT EXISTS plugin_web_analytics_daily (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL,
    stats_date DATE NOT NULL,
    pv INTEGER NOT NULL DEFAULT 0,
    uv INTEGER NOT NULL DEFAULT 0,
    sessions INTEGER NOT NULL DEFAULT 0,
    events INTEGER NOT NULL DEFAULT 0,
    bounces INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    deleted BIGINT NOT NULL DEFAULT 0,
    deleted_time TIMESTAMPTZ NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ NULL DEFAULT NOW(),
    CONSTRAINT uq_web_analytics_daily_site_date UNIQUE (site_id, stats_date)
);
CREATE INDEX IF NOT EXISTS ix_web_analytics_daily_site_date ON plugin_web_analytics_daily (site_id, stats_date);

CREATE TABLE IF NOT EXISTS plugin_web_analytics_replay_session (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL,
    replay_key VARCHAR(64) NOT NULL,
    session_key VARCHAR(64) NOT NULL,
    visitor_hash VARCHAR(64) NOT NULL,
    path VARCHAR(1024) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    last_event_at TIMESTAMPTZ NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    total_bytes INTEGER NOT NULL DEFAULT 0,
    deleted BIGINT NOT NULL DEFAULT 0,
    deleted_time TIMESTAMPTZ NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ NULL DEFAULT NOW(),
    CONSTRAINT uq_web_analytics_replay_site_key UNIQUE (site_id, replay_key)
);
CREATE INDEX IF NOT EXISTS ix_web_analytics_replay_site_started ON plugin_web_analytics_replay_session (site_id, started_at);

CREATE TABLE IF NOT EXISTS plugin_web_analytics_replay_chunk (
    id BIGSERIAL PRIMARY KEY,
    site_id BIGINT NOT NULL,
    replay_key VARCHAR(64) NOT NULL,
    sequence INTEGER NOT NULL,
    payload TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    encoding VARCHAR(16) NOT NULL DEFAULT 'json',
    event_count INTEGER NOT NULL DEFAULT 0,
    deleted BIGINT NOT NULL DEFAULT 0,
    deleted_time TIMESTAMPTZ NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ NULL DEFAULT NOW(),
    CONSTRAINT uq_web_analytics_replay_chunk_sequence UNIQUE (site_id, replay_key, sequence)
);
CREATE INDEX IF NOT EXISTS ix_web_analytics_replay_chunk_lookup ON plugin_web_analytics_replay_chunk (site_id, replay_key, sequence);

DO $$
DECLARE
    root_id BIGINT;
BEGIN
    SELECT id INTO root_id FROM sys_menu WHERE name = 'PluginWebAnalytics';
    IF root_id IS NULL THEN
        INSERT INTO sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time)
        VALUES ('web_analytics.menu', 'PluginWebAnalytics', '/plugins/web-analytics', 45, 'carbon:analytics', 0, NULL, NULL, 1, 1, 1, NULL, '网站访问与行为统计', NULL, NOW())
        RETURNING id INTO root_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM sys_menu WHERE name = 'PluginWebAnalyticsOverview') THEN
        INSERT INTO sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time) VALUES
        ('web_analytics.overview', 'PluginWebAnalyticsOverview', '/plugins/web-analytics', 1, 'carbon:chart-line-data', 1, '/plugins/web_analytics/views/overview', NULL, 1, 1, 1, NULL, '网站统计流量总览', root_id, NOW()),
        ('web_analytics.behavior', 'PluginWebAnalyticsBehavior', '/plugins/web-analytics/behavior', 2, 'carbon:heat-map', 1, '/plugins/web_analytics/views/behavior', NULL, 1, 1, 1, NULL, '热力图与会话回放', root_id, NOW()),
        ('web_analytics.sites', 'PluginWebAnalyticsSites', '/plugins/web-analytics/sites', 3, 'carbon:web-services-container', 1, '/plugins/web_analytics/views/sites', NULL, 1, 1, 1, NULL, '统计站点配置', root_id, NOW());
    END IF;
END $$;
