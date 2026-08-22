# -*- coding: utf-8 -*-
import sys, re, unicodedata, json, argparse
sys.path.insert(0, r'D:\100_Work\101_Program\Proj\fba')
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

def norm(s):
    s = unicodedata.normalize('NFKC', str(s))
    s = re.sub(r'[\s\u3000]+', '', s)
    s = re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', s)
    return s.lower()

def build_answer(qtype, ans):
    if qtype == 'single_choice':
        codes = re.findall(r'[A-Za-z]', str(ans or '').upper())
        return {'correct': codes[0]} if codes else {'correct': str(ans or '')}
    if qtype == 'multiple_choice':
        codes = re.findall(r'[A-Za-z]', str(ans or '').upper())
        return {'correct': sorted(set(codes))} if codes else {'correct': [str(ans or '')]}
    if qtype == 'true_false':
        low = str(ans or '').lower()
        return {'correct': any(k in low for k in ('对','正确','true','t','是','1','a'))}
    parts = [p.strip() for p in str(ans or '').replace('，',',').split(',') if p.strip()]
    return {'correct': parts if parts else [str(ans or '')]}

def main():
    ap = argparse.ArgumentParser(description='用考研兔新数据修正U题库拔高篇解析+答案（按stem匹配）')
    ap.add_argument('--excel', required=True)
    ap.add_argument('--bank-revision-id', type=int, required=True)
    ap.add_argument('--env', default='prod', choices=['dev','prod'])
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    env_cfg = {}
    base = Path(r'D:\100_Work\101_Program\Proj\fba')
    envfile = base / 'backend' / ('.env.prod' if args.env=='prod' else '.env')
    if args.env == 'dev':
        import os
        os.environ.setdefault('FBA_DEV','1')
        sys.path.insert(0, str(base))
        from backend.core.conf import settings
        driver = 'psycopg' if settings.DATABASE_TYPE=='postgresql' else 'pymysql'
        url = f"{settings.DATABASE_TYPE}+{driver}://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_SCHEMA}"
    else:
        for line in envfile.read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,_,v = line.partition('=')
            env_cfg[k.strip()] = v.strip().strip('"').strip("'")
        url = (f"postgresql+psycopg://{env_cfg['DATABASE_USER']}:{env_cfg['DATABASE_PASSWORD']}"
               f"@{env_cfg['DATABASE_HOST']}:{env_cfg['DATABASE_PORT']}/fba")
    eng = create_engine(url, pool_pre_ping=True)

    df = pd.read_excel(args.excel, sheet_name=0)
    df = df.where(df.notna(), None)

    # 新数据按 norm stem 索引
    new_map = {}
    for _, r in df.iterrows():
        if not r.get('stem'): continue
        n = norm(r['stem'])
        new_map[n] = {
            'answer': r.get('answer'),
            'qtype': str(r.get('question_type','')).strip(),
            'explanation': str(r.get('explanation_default') or '').strip() or None,
        }

    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT q.id, q.code, q.stem, q.question_type FROM qbank_v2_bank_item bi "
            "JOIN qbank_v2_question q ON q.id = bi.question_id "
            "WHERE bi.bank_revision_id = :rid AND bi.deleted = 0"
        ), {'rid': args.bank_revision_id}).fetchall()

        matched = 0
        no_match = 0
        no_explanation = 0
        for qid, code, stem, qtype in rows:
            n = norm(stem)
            new = new_map.get(n)
            if not new:
                no_match += 1
                continue
            matched += 1
            if not new['explanation']:
                no_explanation += 1
            if args.dry_run:
                continue
            # 更新解析
            if new['explanation']:
                conn.execute(text(
                    "UPDATE qbank_v2_question_explanation SET content = :c, updated_time = NOW() "
                    "WHERE question_id = :qid"
                ), {'c': new['explanation'], 'qid': qid})
            # 更新答案
            if new['answer'] is not None:
                ad = build_answer(new['qtype'], new['answer'])
                conn.execute(text(
                    "UPDATE qbank_v2_question_answer SET answer_data = CAST(:ad AS jsonb), updated_time = NOW() "
                    "WHERE question_id = :qid"
                ), {'ad': json.dumps(ad, ensure_ascii=False), 'qid': qid})
        if not args.dry_run:
            conn.commit()
        print(json.dumps({
            'env': args.env, 'bank_revision_id': args.bank_revision_id,
            'total_in_bank': len(rows), 'matched': matched,
            'no_match': no_match, 'matched_no_explanation': no_explanation,
            'action': 'DRY-RUN(no write)' if args.dry_run else 'COMMITTED',
        }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
