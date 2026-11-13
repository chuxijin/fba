"""Prepare v2 tables while preserving rollback-compatible scheduler state.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9

Run in a maintenance window after stopping schedule writers and draining workers.
Downgrade retains additive result columns to avoid deleting new task metadata.
"""

from alembic import op

revision = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None

UPGRADE_SQL = r"""
DO $migration$
DECLARE
    ns text;
    tab text;
    enabled_type text;
    status_type text;
    col text;
    invalid_state boolean;
BEGIN
    SELECT n.nspname INTO ns FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.oid=to_regclass('task_scheduler');
    IF ns IS NULL THEN RAISE EXCEPTION 'Missing task_scheduler baseline'; END IF;
    FOREACH tab IN ARRAY ARRAY['task_scheduler','task_result','sys_opera_log','sys_menu'] LOOP
        IF to_regclass(format('%I.%I',ns,tab)) IS NULL THEN
            RAISE EXCEPTION 'Required migration table missing: %',tab;
        END IF;
    END LOOP;
    EXECUTE format('LOCK TABLE %I.task_scheduler, %I.task_result, %I.sys_opera_log, %I.sys_menu IN ACCESS EXCLUSIVE MODE',ns,ns,ns,ns);
    SELECT udt_name INTO enabled_type FROM information_schema.columns
    WHERE table_schema=ns AND table_name='task_scheduler' AND column_name='enabled';
    SELECT udt_name INTO status_type FROM information_schema.columns
    WHERE table_schema=ns AND table_name='task_scheduler' AND column_name='status';
    IF enabled_type IS NULL AND status_type IS NULL THEN
        RAISE EXCEPTION 'Scheduler has neither enabled nor status';
    END IF;
    IF enabled_type IS NOT NULL AND enabled_type <> 'bool' THEN
        RAISE EXCEPTION 'Unexpected scheduler enabled type';
    END IF;
    IF status_type IS NOT NULL AND status_type <> 'int4' THEN
        RAISE EXCEPTION 'Unexpected scheduler status type';
    END IF;
    IF status_type IS NULL THEN
        EXECUTE format('ALTER TABLE %I.task_scheduler ADD COLUMN status integer',ns);
        EXECUTE format('UPDATE %I.task_scheduler SET status=CASE WHEN enabled THEN 1 ELSE 0 END',ns);
    END IF;
    IF enabled_type IS NULL THEN
        EXECUTE format('ALTER TABLE %I.task_scheduler ADD COLUMN enabled boolean',ns);
        EXECUTE format('UPDATE %I.task_scheduler SET enabled=(status=1)',ns);
    END IF;
    EXECUTE format('SELECT EXISTS(SELECT 1 FROM %I.task_scheduler WHERE status IS NULL OR status NOT IN (0,1) OR enabled IS DISTINCT FROM (status=1))',ns) INTO invalid_state;
    IF invalid_state THEN RAISE EXCEPTION 'Invalid or inconsistent scheduler baseline state'; END IF;
    EXECUTE format('ALTER TABLE %I.task_scheduler ALTER COLUMN enabled SET DEFAULT true, ALTER COLUMN enabled SET NOT NULL, ALTER COLUMN status DROP DEFAULT, ALTER COLUMN status SET NOT NULL',ns);
    EXECUTE format('ALTER TABLE %I.task_scheduler ADD CONSTRAINT ck_fba_v2_scheduler_state CHECK (status IN (0,1) AND enabled=(status=1))',ns);
    EXECUTE format($ddl$
        CREATE FUNCTION %I._fba_v2_sync_scheduler_state() RETURNS trigger
        LANGUAGE plpgsql AS $sync$
        BEGIN
            IF TG_OP='INSERT' THEN
                IF NEW.status IS NULL THEN NEW.status=CASE WHEN NEW.enabled THEN 1 ELSE 0 END;
                ELSE NEW.enabled=(NEW.status=1); END IF;
            ELSE
                IF NEW.status IS DISTINCT FROM OLD.status AND NEW.enabled IS DISTINCT FROM OLD.enabled THEN
                    IF NEW.enabled IS DISTINCT FROM (NEW.status=1) THEN
                        RAISE EXCEPTION 'Conflicting scheduler enabled/status update';
                    END IF;
                ELSIF NEW.status IS DISTINCT FROM OLD.status THEN NEW.enabled=(NEW.status=1);
                ELSIF NEW.enabled IS DISTINCT FROM OLD.enabled THEN NEW.status=CASE WHEN NEW.enabled THEN 1 ELSE 0 END;
                END IF;
            END IF;
            IF NEW.status IS NULL OR NEW.status NOT IN (0,1) THEN
                RAISE EXCEPTION 'Scheduler status must be 0 or 1';
            END IF;
            RETURN NEW;
        END;
        $sync$
    $ddl$,ns);
    EXECUTE format('CREATE TRIGGER _fba_v2_sync_scheduler_state BEFORE INSERT OR UPDATE ON %I.task_scheduler FOR EACH ROW EXECUTE FUNCTION %I._fba_v2_sync_scheduler_state()',ns,ns);
    EXECUTE format($ddl$
        CREATE FUNCTION %I._fba_v2_json_shape(payload jsonb, expected text, row_id bigint)
        RETURNS jsonb LANGUAGE plpgsql AS $parse$
        BEGIN
            IF payload IS NULL OR jsonb_typeof(payload)='null' THEN RETURN payload; END IF;
            IF jsonb_typeof(payload)='string' THEN
                BEGIN payload=(payload #>> '{}')::jsonb;
                EXCEPTION WHEN invalid_text_representation THEN
                    RAISE EXCEPTION 'Invalid encoded JSON at row id=%%; expected %%',row_id,expected;
                END;
            END IF;
            IF jsonb_typeof(payload) IS DISTINCT FROM expected AND jsonb_typeof(payload) <> 'null' THEN
                RAISE EXCEPTION 'Unexpected JSON shape at row id=%%; expected %%',row_id,expected;
            END IF;
            RETURN payload;
        END;
        $parse$
    $ddl$,ns);
    EXECUTE format('ALTER TABLE %I.task_scheduler ALTER COLUMN args TYPE jsonb USING %I._fba_v2_json_shape(args::jsonb,''array'',id), ALTER COLUMN kwargs TYPE jsonb USING %I._fba_v2_json_shape(kwargs::jsonb,''object'',id)',ns,ns,ns);
    EXECUTE format('ALTER TABLE %I.sys_opera_log ALTER COLUMN args TYPE jsonb USING %I._fba_v2_json_shape(args::jsonb,''object'',id)',ns,ns);
    EXECUTE format('DROP FUNCTION %I._fba_v2_json_shape(jsonb,text,bigint)',ns);
    FOREACH col IN ARRAY ARRAY['children','stamps'] LOOP
        IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=ns AND table_name='task_result' AND column_name=col AND udt_name<>'bytea') THEN
            RAISE EXCEPTION 'Unexpected task_result type for %',col;
        END IF;
        EXECUTE format('ALTER TABLE %I.task_result ADD COLUMN IF NOT EXISTS %I bytea',ns,col);
    END LOOP;
    IF to_regclass(format('%I._fba_v2_codegen_menu_backup',ns)) IS NOT NULL THEN
        RAISE EXCEPTION 'Menu backup table already exists; inspect before rerunning migration';
    END IF;
    EXECUTE format('CREATE TABLE %I._fba_v2_codegen_menu_backup(menu_id bigint PRIMARY KEY,status integer NOT NULL)',ns);
    EXECUTE format($sql$
        INSERT INTO %I._fba_v2_codegen_menu_backup
        SELECT id,status FROM %I.sys_menu m
        WHERE concat_ws(' ',to_jsonb(m)->>'path',to_jsonb(m)->>'perms',to_jsonb(m)->>'name') ~* 'code[-_]?gen|代码生成'
    $sql$,ns,ns);
    EXECUTE format('UPDATE %I.sys_menu SET status=0 WHERE id IN (SELECT menu_id FROM %I._fba_v2_codegen_menu_backup)',ns,ns);
END;
$migration$;
"""

DOWNGRADE_SQL = r"""
DO $migration$
DECLARE ns text;
BEGIN
    SELECT n.nspname INTO ns FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.oid=to_regclass('task_scheduler');
    IF ns IS NULL THEN RAISE EXCEPTION 'Missing task_scheduler baseline'; END IF;
    EXECUTE format('LOCK TABLE %I.task_scheduler, %I.sys_opera_log, %I.sys_menu IN ACCESS EXCLUSIVE MODE',ns,ns,ns);
    EXECUTE format('UPDATE %I.task_scheduler SET enabled=(status=1)',ns);
    EXECUTE format('DROP TRIGGER _fba_v2_sync_scheduler_state ON %I.task_scheduler',ns);
    EXECUTE format('DROP FUNCTION %I._fba_v2_sync_scheduler_state()',ns);
    EXECUTE format('ALTER TABLE %I.task_scheduler DROP CONSTRAINT ck_fba_v2_scheduler_state, DROP COLUMN status',ns);
    -- Old schedulers json.loads() JSON strings; preserve new argument values too.
    EXECUTE format($sql$
        ALTER TABLE %I.task_scheduler
        ALTER COLUMN args TYPE json USING CASE WHEN jsonb_typeof(args)='array' THEN to_json(args::text) ELSE args::json END,
        ALTER COLUMN kwargs TYPE json USING CASE WHEN jsonb_typeof(kwargs)='object' THEN to_json(kwargs::text) ELSE kwargs::json END
    $sql$,ns);
    EXECUTE format('ALTER TABLE %I.sys_opera_log ALTER COLUMN args TYPE json USING args::json',ns);
    EXECUTE format('UPDATE %I.sys_menu m SET status=b.status FROM %I._fba_v2_codegen_menu_backup b WHERE m.id=b.menu_id AND m.status=0',ns,ns);
    EXECUTE format('DROP TABLE %I._fba_v2_codegen_menu_backup',ns);
    -- Do not drop children/stamps: the old ORM ignores them; preserve new metadata.
END;
$migration$;
"""


def _run(sql: str) -> None:
    if op.get_bind().dialect.name != 'postgresql':
        raise RuntimeError('The v2 deployment migration requires PostgreSQL')
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '5min'")
    op.execute(sql)


def upgrade() -> None:
    _run(UPGRADE_SQL)


def downgrade() -> None:
    _run(DOWNGRADE_SQL)
