-- Merge sys_user_role_expiry into sys_user_role (PostgreSQL)
-- Date: 2026-03-22

BEGIN;

-- 1) Add expiry columns to sys_user_role
ALTER TABLE sys_user_role
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS status INTEGER NOT NULL DEFAULT 1;

UPDATE sys_user_role
SET status = 1
WHERE status IS NULL;

-- 2) Migrate data from old table when it exists
DO
$$
BEGIN
    IF to_regclass('sys_user_role_expiry') IS NULL THEN
        RETURN;
    END IF;

    -- 2.1 update existing user-role rows
    UPDATE sys_user_role ur
    SET valid_from = e.valid_from,
        valid_to = e.valid_to,
        status = COALESCE(e.status, 1)
    FROM sys_user_role_expiry e
    WHERE ur.user_id = e.user_id
      AND ur.role_id = e.role_id;

    -- 2.2 insert rows that do not exist in sys_user_role
    INSERT INTO sys_user_role (user_id, role_id, valid_from, valid_to, status)
    SELECT e.user_id, e.role_id, e.valid_from, e.valid_to, COALESCE(e.status, 1)
    FROM sys_user_role_expiry e
             LEFT JOIN sys_user_role ur
                       ON ur.user_id = e.user_id
                           AND ur.role_id = e.role_id
    WHERE ur.id IS NULL;
END
$$;

-- 3) Remove duplicate user_id + role_id rows, keep latest id
WITH duplicate_rows AS (
    SELECT ctid,
           ROW_NUMBER() OVER (PARTITION BY user_id, role_id ORDER BY id DESC) AS rn
    FROM sys_user_role
)
DELETE
FROM sys_user_role t
    USING duplicate_rows d
WHERE t.ctid = d.ctid
  AND d.rn > 1;

-- 4) Add constraints
ALTER TABLE sys_user_role
    DROP CONSTRAINT IF EXISTS ck_sys_user_role_status;

ALTER TABLE sys_user_role
    ADD CONSTRAINT ck_sys_user_role_status CHECK (status IN (0, 1, 2));

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
                 JOIN pg_class t ON t.oid = c.conrelid
                 JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE c.contype = 'u'
          AND n.nspname = current_schema()
          AND t.relname = 'sys_user_role'
          AND c.conname = 'uq_sys_user_role_user_role'
    ) THEN
        ALTER TABLE sys_user_role
            ADD CONSTRAINT uq_sys_user_role_user_role UNIQUE (user_id, role_id);
    END IF;
END
$$;

-- 5) Add indexes
CREATE INDEX IF NOT EXISTS ix_sys_user_role_user_status ON sys_user_role (user_id, status);
CREATE INDEX IF NOT EXISTS ix_sys_user_role_role_status ON sys_user_role (role_id, status);
CREATE INDEX IF NOT EXISTS ix_sys_user_role_valid_to ON sys_user_role (valid_to);

-- 6) Drop old table
DROP TABLE IF EXISTS sys_user_role_expiry;

COMMIT;
