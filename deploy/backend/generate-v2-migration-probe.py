"""Generate (never execute) a rollback-only development PostgreSQL probe."""

import argparse
import ast
import hashlib
import json

from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', required=True, type=Path, help='New SQL file; existing files are never overwritten')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
path = root / 'backend/alembic/versions/2026-11-13-23_30_00-c5d6e7f8a9b0_upstream_v2_deployment.py'
source = path.read_text(encoding='utf-8')
constants = {
    node.targets[0].id: ast.literal_eval(node.value)
    for node in ast.parse(source).body
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id.endswith('_SQL')
}
sql = r"""
BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='30s';
CREATE SCHEMA fba_v2_probe_20261113;
SET LOCAL search_path=fba_v2_probe_20261113,pg_catalog;
CREATE TABLE task_scheduler(id bigint PRIMARY KEY,enabled boolean NOT NULL,args json,kwargs json);
CREATE TABLE task_result(id bigint PRIMARY KEY,result bytea);
CREATE TABLE sys_opera_log(id bigint PRIMARY KEY,args json);
CREATE TABLE sys_menu(id bigint PRIMARY KEY,status integer NOT NULL,name text,path text,perms text);
INSERT INTO task_scheduler VALUES (1,false,to_json('[1,2]'::text),to_json('{"k":3}'::text)),(2,true,'null','null'),(3,false,NULL,NULL);
INSERT INTO sys_opera_log VALUES (1,to_json('{"dummy":1}'::text)),(2,'null'),(3,NULL);
INSERT INTO sys_menu VALUES (1,1,'codegen','/codegen','codegen:read'),(2,0,'codegen-off','/codegen-off','codegen:read'),(3,1,'ordinary','/ordinary','ordinary:read');
INSERT INTO task_result VALUES (1,decode('8004','hex'));
""" + constants['UPGRADE_SQL'] + r"""
DO $assertions$
DECLARE rejected boolean=false;
BEGIN
 IF (SELECT status FROM task_scheduler WHERE id=1)<>0 THEN RAISE EXCEPTION 'disabled state lost'; END IF;
 IF (SELECT status FROM task_scheduler WHERE id=2)<>1 THEN RAISE EXCEPTION 'enabled state lost'; END IF;
 IF (SELECT jsonb_typeof(args) FROM task_scheduler WHERE id=1)<>'array' THEN RAISE EXCEPTION 'args not unwrapped'; END IF;
 IF (SELECT jsonb_typeof(kwargs) FROM task_scheduler WHERE id=1)<>'object' THEN RAISE EXCEPTION 'kwargs not unwrapped'; END IF;
 IF (SELECT args FROM task_scheduler WHERE id=3) IS NOT NULL THEN RAISE EXCEPTION 'SQL NULL changed'; END IF;
 IF (SELECT jsonb_typeof(args) FROM task_scheduler WHERE id=2)<>'null' THEN RAISE EXCEPTION 'JSON null changed'; END IF;
 IF (SELECT status FROM sys_menu WHERE id=1)<>0 OR (SELECT status FROM sys_menu WHERE id=3)<>1 THEN RAISE EXCEPTION 'menu scope changed'; END IF;
 INSERT INTO task_scheduler(id,enabled,args) VALUES (4,false,'null');
 IF (SELECT status FROM task_scheduler WHERE id=4)<>0 THEN RAISE EXCEPTION 'legacy insert lost disabled flag'; END IF;
 INSERT INTO task_scheduler(id,status,args) VALUES (5,0,'[9]');
 IF (SELECT enabled FROM task_scheduler WHERE id=5) THEN RAISE EXCEPTION 'new insert lost disabled flag'; END IF;
 INSERT INTO task_scheduler(id,args) VALUES (6,'null');
 IF (SELECT status FROM task_scheduler WHERE id=6)<>1 OR NOT (SELECT enabled FROM task_scheduler WHERE id=6) THEN RAISE EXCEPTION 'default insert lost enabled flag'; END IF;
 INSERT INTO task_scheduler(id,status) VALUES (7,1);
 IF NOT (SELECT enabled FROM task_scheduler WHERE id=7) THEN RAISE EXCEPTION 'new enabled insert not synced'; END IF;
 UPDATE task_scheduler SET status=1 WHERE id=1;
 IF NOT (SELECT enabled FROM task_scheduler WHERE id=1) THEN RAISE EXCEPTION 'new update not synced'; END IF;
 UPDATE task_scheduler SET enabled=false WHERE id=1;
 IF (SELECT status FROM task_scheduler WHERE id=1)<>0 THEN RAISE EXCEPTION 'legacy update not synced'; END IF;
 BEGIN UPDATE task_scheduler SET status=77 WHERE id=1;
 EXCEPTION WHEN raise_exception THEN rejected=true; END;
 IF NOT rejected THEN RAISE EXCEPTION 'invalid status accepted'; END IF;
 rejected=false;
 BEGIN UPDATE task_scheduler SET status=1,enabled=NULL WHERE id=1;
 EXCEPTION WHEN raise_exception THEN rejected=true; END;
 IF NOT rejected THEN RAISE EXCEPTION 'conflicting update accepted'; END IF;
 UPDATE task_result SET children=decode('01','hex'),stamps=decode('02','hex');
END;
$assertions$;
""" + constants['DOWNGRADE_SQL'] + r"""
DO $assertions$
BEGIN
 IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='task_scheduler' AND column_name='status') THEN RAISE EXCEPTION 'status column not rolled back'; END IF;
 IF (SELECT json_typeof(args) FROM task_scheduler WHERE id=1)<>'string' THEN RAISE EXCEPTION 'legacy args string not restored'; END IF;
 IF (SELECT (args #>> '{}')::jsonb FROM task_scheduler WHERE id=5)<>'[9]'::jsonb THEN RAISE EXCEPTION 'new argument data lost'; END IF;
 IF (SELECT args FROM task_scheduler WHERE id=3) IS NOT NULL THEN RAISE EXCEPTION 'rollback changed SQL NULL'; END IF;
 IF (SELECT status FROM sys_menu WHERE id=1)<>1 OR (SELECT status FROM sys_menu WHERE id=2)<>0 THEN RAISE EXCEPTION 'menu state not restored'; END IF;
 IF (SELECT children FROM task_result WHERE id=1)<>decode('01','hex') OR (SELECT stamps FROM task_result WHERE id=1)<>decode('02','hex') THEN RAISE EXCEPTION 'result metadata lost'; END IF;
END;
$assertions$;
DO $invalid$
DECLARE rejected boolean; bad_sql text;
BEGIN
 FOREACH bad_sql IN ARRAY ARRAY[
   $bad$UPDATE task_scheduler SET args='{}'::json WHERE id=1$bad$,
   $bad$UPDATE task_scheduler SET args=to_json('not-json'::text) WHERE id=1$bad$,
   $bad$UPDATE task_scheduler SET kwargs='[]'::json WHERE id=1$bad$,
   $bad$UPDATE sys_opera_log SET args='[]'::json WHERE id=1$bad$
 ] LOOP
 rejected=false;
 BEGIN
 EXECUTE bad_sql;
 EXECUTE $upgrade$""" + constants['UPGRADE_SQL'] + r"""$upgrade$;
 EXCEPTION WHEN raise_exception THEN rejected=true;
 END;
 IF NOT rejected THEN RAISE EXCEPTION 'invalid args shape accepted'; END IF;
 IF EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='task_scheduler' AND column_name='status') THEN RAISE EXCEPTION 'failed migration left schema changes'; END IF;
 IF (SELECT status FROM sys_menu WHERE id=1)<>1 THEN RAISE EXCEPTION 'failed migration changed menus'; END IF;
 END LOOP;
END;
$invalid$;
ROLLBACK;
SELECT 'v2_upgrade_downgrade_and_invalid_data_checks_passed' AS result,
 to_regnamespace('fba_v2_probe_20261113') IS NULL AS fixture_schema_rolled_back;
"""
out = args.output.resolve()
record_path = out.with_suffix('.json')
if out.exists() or record_path.exists():
    parser.error('Output or evidence file already exists; choose new paths')
with out.open('x', encoding='utf-8', newline='\n') as stream:
    stream.write(sql)
with record_path.open('x', encoding='utf-8') as stream:
    json.dump({
        'scope': 'Development PostgreSQL only; isolated schema inside one rollback transaction',
        'migrationSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'sqlSha256': hashlib.sha256(out.read_bytes()).hexdigest(),
        'sqlFile': str(out), 'result': 'not yet executed',
    }, stream, indent=2)
print(f'Generated {out}; no database connections were opened')
