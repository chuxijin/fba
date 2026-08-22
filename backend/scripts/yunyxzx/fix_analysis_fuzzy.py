# -*- coding: utf-8 -*-
import sys, re, unicodedata, json, argparse, difflib
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

def get_engine(env):
    base = Path(r'D:\100_Work\101_Program\Proj\fba')
    if env == 'prod':
        env_cfg = {}
        for line in (base/'backend'/'.env.prod').read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,_,v = line.partition('=')
            env_cfg[k.strip()] = v.strip().strip('"').strip("'")
        url = (f"postgresql+psycopg://{env_cfg['DATABASE_USER']}:{env_cfg['DATABASE_PASSWORD']}"
               f"@{env_cfg['DATABASE_HOST']}:{env_cfg['DATABASE_PORT']}/fba")
    else:
        import os
        os.environ.setdefault('FBA_DEV','1')
        sys.path.insert(0, str(base))
        from backend.core.conf import settings
        driver = 'psycopg' if settings.DATABASE_TYPE=='postgresql' else 'pymysql'
        url = f"{settings.DATABASE_TYPE}+{driver}://{settings.DATABASE_USER}:{settings.DATABASE_PASSWORD}@{settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_SCHEMA}"
    return create_engine(url, pool_pre_ping=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--excel', required=True)
    ap.add_argument('--bank-revision-id', type=int, required=True)
    ap.add_argument('--env', default='prod', choices=['dev','prod'])
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--threshold', type=float, default=0.8, help='模糊匹配置信阈值')
    args = ap.parse_args()

    eng = get_engine(args.env)
    df = pd.read_excel(args.excel, sheet_name=0)
    df = df.where(df.notna(), None)

    with eng.connect() as conn:
        rows = conn.execute(text(
            "SELECT q.id, q.code, q.stem FROM qbank_v2_bank_item bi "
            "JOIN qbank_v2_question q ON q.id = bi.question_id "
            "WHERE bi.bank_revision_id = :rid AND bi.deleted = 0"
        ), {'rid': args.bank_revision_id}).fetchall()

    exist = {}
    for qid, code, stem in rows:
        exist.setdefault(norm(stem), []).append((qid, code))

    # 已精确匹配的集合（此前588题）
    exact = set()
    for _, r in df.iterrows():
        if not r.get('stem'): continue
        if norm(r['stem']) in exist:
            exact.add(norm(r['stem']))

    to_update = []
    for _, r in df.iterrows():
        if not r.get('stem'): continue
        n = norm(r['stem'])
        if n in exact: continue
        best = None; best_score = 0
        for en, lst in exist.items():
            sm = difflib.SequenceMatcher(None, n, en)
            ratio = sm.ratio()
            m = sm.find_longest_match(0, len(n), 0, len(en))
            cover = m.size / max(len(n),1)
            score = max(ratio, cover)
            if score > best_score:
                best_score = score; best = (en, lst[0], ratio, cover, len(lst))
        if best and best_score >= args.threshold:
            to_update.append((r, best, best_score))

    # dry run 输出
    print('高置信可更新数:', len(to_update))
    for r, b, sc in to_update:
        ik = r['item_key']
        print(f'  {ik} -> {b[1][1]} (ratio={b[2]:.2f} cover={b[3]:.2f} dup={b[4]})')
    print('dry_run:', args.dry_run)

    if args.dry_run:
        return

    # 正式更新题干+解析+答案
    with eng.connect() as conn:
        updated = 0
        for r, b, sc in to_update:
            en, (qid, code), ratio, cover, dup = b
            conn.execute(text(
                "UPDATE qbank_v2_question SET stem = :s, content_format = 'html', updated_time = NOW() WHERE id = :qid"
            ), {'s': str(r['stem']).strip(), 'qid': qid})
            exp = str(r.get('explanation_default') or '').strip()
            if exp:
                conn.execute(text(
                    "UPDATE qbank_v2_question_explanation SET content = :c, updated_time = NOW() WHERE question_id = :qid"
                ), {'c': exp, 'qid': qid})
            ans = r.get('answer')
            if ans is not None:
                ad = build_answer(str(r.get('question_type','')).strip(), ans)
                conn.execute(text(
                    "UPDATE qbank_v2_question_answer SET answer_data = CAST(:ad AS jsonb), updated_time = NOW() WHERE question_id = :qid"
                ), {'ad': json.dumps(ad, ensure_ascii=False), 'qid': qid})
            updated += 1
        conn.commit()
        print('COMMITTED updates:', updated)

if __name__ == '__main__':
    main()
