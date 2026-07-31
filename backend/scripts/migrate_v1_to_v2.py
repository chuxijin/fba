#!/usr/bin/env python3
"""Migrate v1 question bank data to v2 (skip user data)."""

import asyncio
import json
import logging
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.database.db import get_database_url

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('migrate_v1_to_v2')

QTYPE_MAP = {
    'single': 'single_choice', 'multiple': 'multiple_choice',
    'judgement': 'true_false', 'fill': 'fill_blank', 'shortAnswer': 'short_answer',
}
BANK_KIND = {1: 'practice', 2: 'paper'}
V1_STATUS = {0: 'disabled', 1: 'active', 10: 'active', 20: 'archived'}
PUBLIC = 'public'


async def migrate():
    engine = create_async_engine(get_database_url(), echo=False, pool_pre_ping=True)
    async with engine.connect() as conn:
        await conn.execute(text('SET session_replication_role = replica'))
        await conn.commit()
        try:
            # 1. Collections
            logger.info('=== Migrate collections ===')
            rows = (await conn.execute(text(
                'SELECT id, code, name, parent_id, owner_id, "desc", sort_order, status, '
                "created_by, updated_by, created_time, updated_time, deleted "
                "FROM study_question_bank WHERE bank_type = 3 AND deleted = 0"
            ))).mappings().all()
            logger.info('  Found %d collections', len(rows))
            for r in rows:
                sql = text(
                    "INSERT INTO qbank_v2_collection (id, code, name, parent_id, owner_id, description, "
                    "visibility, status, sort_order, created_by, updated_by, created_time, updated_time, deleted) "
                    "VALUES (:id, :code, :name, :parent_id, :owner_id, :description, "
                    ":visibility, :status, :sort_order, :created_by, :updated_by, :created_time, :updated_time, :deleted) "
                    "ON CONFLICT (id) DO NOTHING"
                )
                await conn.execute(sql, {
                    'id': r['id'], 'code': r['code'] or f'v1col_{r["id"]}',
                    'name': r['name'], 'parent_id': r['parent_id'],
                    'owner_id': r['owner_id'], 'description': r['desc'],
                    'visibility': PUBLIC, 'status': V1_STATUS.get(r['status'], 'active'),
                    'sort_order': r['sort_order'],
                    'created_by': r['created_by'] or 0, 'updated_by': r['updated_by'],
                    'created_time': r['created_time'], 'updated_time': r['updated_time'],
                    'deleted': r['deleted'],
                })
            await conn.commit()

            # 2. Collection bank mounts
            logger.info('=== Migrate collection-bank mounts ===')
            mounts = (await conn.execute(text(
                "SELECT id, collection_id, item_id, sort_order, status, created_by, created_time "
                "FROM study_question_bank_mount WHERE deleted = 0"
            ))).mappings().all()
            logger.info('  Found %d mounts', len(mounts))
            sql_mount = text(
                "INSERT INTO qbank_v2_collection_bank (id, collection_id, bank_id, follow_latest, "
                "sort_order, is_active, created_by, created_time, deleted) "
                "VALUES (:id, :collection_id, :item_id, true, :sort_order, :is_active, "
                ":created_by, :created_time, 0) ON CONFLICT (id) DO NOTHING"
            )
            for m in mounts:
                await conn.execute(sql_mount, {
                    'id': m['id'], 'collection_id': m['collection_id'],
                    'item_id': m['item_id'], 'sort_order': m['sort_order'],
                    'is_active': m['status'] == 1,
                    'created_by': m['created_by'] or 0, 'created_time': m['created_time'],
                })
            await conn.commit()

            # 3. Banks (non-collection) -> QbBank + QbBankRevision
            logger.info('=== Migrate banks ===')
            banks = (await conn.execute(text(
                'SELECT id, code, name, owner_id, "desc", cover_url, difficulty, bank_type, '
                "sort_order, scene_mask, q_count_cache, total_score_cache, "
                "status, created_by, updated_by, created_time, updated_time, deleted "
                "FROM study_question_bank WHERE bank_type IN (1, 2) AND deleted = 0"
            ))).mappings().all()
            logger.info('  Found %d banks', len(banks))

            sql_bank = text(
                "INSERT INTO qbank_v2_bank (id, code, owner_id, current_revision_id, "
                "visibility, status, created_by, updated_by, created_time, updated_time, deleted) "
                "VALUES (:id, :code, :owner_id, NULL, :visibility, :status, "
                ":created_by, :updated_by, :created_time, :updated_time, :deleted) "
                "ON CONFLICT (id) DO NOTHING"
            )
            sql_rev = text(
                "INSERT INTO qbank_v2_bank_revision (bank_id, revision_no, name, description, bank_kind, "
                "cover_url, question_count, total_score, settings, "
                "status, published_by, published_time, created_by, updated_by, created_time, updated_time, deleted) "
                "VALUES (:bank_id, 1, :name, :desc, :bank_kind, :cover_url, :q_count, :total_score, :settings, "
                "'published', :pb, :pt, :cb, :ub, :ct, :ut, :d) "
                "ON CONFLICT (bank_id, revision_no) DO NOTHING"
            )
            for b in banks:
                await conn.execute(sql_bank, {
                    'id': b['id'], 'code': b['code'] or f'v1bnk_{b["id"]}',
                    'owner_id': b['owner_id'], 'visibility': PUBLIC,
                    'status': V1_STATUS.get(b['status'], 'active'),
                    'created_by': b['created_by'] or 0, 'updated_by': b['updated_by'],
                    'created_time': b['created_time'], 'updated_time': b['updated_time'],
                    'deleted': b['deleted'],
                })
                cby = b['created_by'] or 0
                ut = b['updated_time']
                await conn.execute(sql_rev, {
                    'bank_id': b['id'], 'name': b['name'], 'desc': b['desc'],
                    'bank_kind': BANK_KIND.get(b['bank_type'], 'practice'),
                    'cover_url': b['cover_url'],
                    'q_count': b['q_count_cache'] or 0,
                    'total_score': b['total_score_cache'] or Decimal('0'),
                    'settings': json.dumps({'scene_mask': b['scene_mask']}),
                    'pb': cby, 'pt': b['created_time'],
                    'cb': cby, 'ub': b['updated_by'],
                    'ct': b['created_time'], 'ut': ut,
                    'd': b['deleted'],
                })
            await conn.commit()

            sql_update = text(
                "UPDATE qbank_v2_bank b SET current_revision_id = r.id "
                "FROM qbank_v2_bank_revision r WHERE r.bank_id = b.id AND r.revision_no = 1 "
                "AND b.current_revision_id IS NULL"
            )
            await conn.execute(sql_update)
            await conn.commit()

            # 4. Chapters -> sections
            logger.info('=== Migrate chapters ===')
            chapters = (await conn.execute(text(
                "SELECT id, bank_id, name, parent_id, code, level, sort_order, deleted "
                "FROM study_question_chapter WHERE deleted = 0"
            ))).mappings().all()
            logger.info('  Found %d chapters', len(chapters))
            sql_sec = text(
                "INSERT INTO qbank_v2_bank_section (id, bank_revision_id, code, name, "
                "parent_id, depth, sort_order, deleted) "
                "VALUES (:id, :rev_id, :code, :name, :parent_id, :depth, :sort_order, :deleted) "
                "ON CONFLICT (id) DO NOTHING"
            )
            for ch in chapters:
                rev = (await conn.execute(text(
                    "SELECT id FROM qbank_v2_bank_revision "
                    "WHERE bank_id = :bank_id AND revision_no = 1 AND deleted = 0"
                ), {'bank_id': ch['bank_id']})).mappings().first()
                if not rev:
                    continue
                await conn.execute(sql_sec, {
                    'id': ch['id'], 'rev_id': rev['id'],
                    'code': ch['code'] or f'ch_{ch["id"]}',
                    'name': ch['name'], 'parent_id': ch['parent_id'],
                    'depth': ch['level'], 'sort_order': ch['sort_order'],
                    'deleted': ch['deleted'],
                })
            await conn.commit()

            # 5. Questions
            logger.info('=== Migrate questions ===')
            qs = (await conn.execute(text(
                "SELECT q.id, q.type, q.stem, q.difficulty, q.default_score, q.options, q.content_status, "
                "q.created_by, q.created_time, q.updated_time, q.deleted, "
                "qa.answer_data, qa.content AS analysis_content, qa.type AS analysis_type "
                "FROM study_question q "
                "LEFT JOIN study_question_analysis qa ON qa.question_id = q.id AND qa.is_default = true "
                "WHERE q.deleted = 0"
            ))).mappings().all()
            logger.info('  Found %d questions', len(qs))

            sql_q = text(
                "INSERT INTO qbank_v2_question (id, code, question_type, stem, difficulty, default_score, "
                "option_data, content_format, visibility, status, origin_type, "
                "created_by, created_time, updated_time, deleted) "
                "VALUES (:id, :code, :qtype, :stem, :difficulty, :default_score, "
                ":options, :content_format, :visibility, :status, 'curated', "
                ":created_by, :created_time, :updated_time, :deleted) "
                "ON CONFLICT (id) DO NOTHING"
            )
            sql_ans = text(
                "INSERT INTO qbank_v2_question_answer (question_id, answer_data, grading_method, grading_config, "
                "created_by, updated_by, created_time, updated_time) "
                "VALUES (:qid, :answer_data, 'exact', '{}'::jsonb, :cb, :cb, :ct, :ct) "
                "ON CONFLICT (question_id) DO NOTHING"
            )
            sql_exp = text(
                "INSERT INTO qbank_v2_question_explanation (question_id, content, explanation_type, is_default, "
                "status, created_by, updated_by, created_time, updated_time) "
                "VALUES (:qid, :content, :etype, true, 'published', :cb, :cb, :ct, :ct) ON CONFLICT DO NOTHING"
            )

            for q in qs:
                qtype = QTYPE_MAP.get(q['type'], q['type'])
                opts = q['options']
                if opts is not None and not isinstance(opts, str):
                    opts = json.dumps(opts)
                await conn.execute(sql_q, {
                    'id': q['id'], 'code': f'q_{q["id"]}',
                    'qtype': qtype, 'stem': q['stem'],
                    'difficulty': q['difficulty'],
                    'default_score': q['default_score'] or Decimal('1.00'),
                    'options': opts, 'content_format': 'html',
                    'visibility': PUBLIC,
                    'status': V1_STATUS.get(q['content_status'], 'active'),
                    'created_by': q['created_by'] or 0,
                    'created_time': q['created_time'],
                    'updated_time': q['updated_time'], 'deleted': q['deleted'],
                })
                if q.get('answer_data'):
                    try:
                        ad = q['answer_data']
                        await conn.execute(sql_ans, {'qid': q['id'], 'answer_data': json.dumps(ad) if not isinstance(ad, str) else ad, 'cb': q['created_by'] or 0, 'ct': q['created_time']})
                    except Exception as e:
                        logger.warning('  Answer insert failed for q=%d: %s', q['id'], e)
                if q.get('analysis_content'):
                    etype = q.get('analysis_type') if q.get('analysis_type') in ('analysis', 'hint') else 'default'
                    try:
                        await conn.execute(sql_exp, {'qid': q['id'], 'content': q['analysis_content'], 'etype': etype, 'cb': q['created_by'] or 0, 'ct': q['created_time']})
                    except Exception as e:
                        logger.warning('  Explanation insert failed for q=%d: %s', q['id'], e)
            await conn.commit()

            # 6. Placements -> bank items
            logger.info('=== Migrate placements ===')
            placements = (await conn.execute(text(
                "SELECT p.id, p.question_id, p.bank_id, p.chapter_id, "
                "p.sort_order, p.score, p.is_active, p.created_by, p.created_time, p.deleted "
                "FROM study_question_placement p WHERE p.deleted = 0"
            ))).mappings().all()
            logger.info('  Found %d placements', len(placements))

            sql_item = text(
                "INSERT INTO qbank_v2_bank_item (id, bank_revision_id, item_key, question_id, section_id, "
                "score, sort_order, is_active, is_required, settings, created_by, created_time, deleted) "
                "VALUES (:id, :rev_id, :item_key, :qid, :section_id, :score, :sort_order, "
                ":is_active, true, '{}'::jsonb, :created_by, :created_time, :deleted) "
                "ON CONFLICT (id) DO NOTHING"
            )

            for p in placements:
                rev = (await conn.execute(text(
                    "SELECT id FROM qbank_v2_bank_revision "
                    "WHERE bank_id = :bank_id AND revision_no = 1 AND deleted = 0"
                ), {'bank_id': p['bank_id']})).mappings().first()
                if not rev:
                    continue
                await conn.execute(sql_item, {
                    'id': p['id'], 'rev_id': rev['id'], 'item_key': f'p_{p["id"]}',
                    'qid': p['question_id'], 'section_id': p['chapter_id'],
                    'score': p['score'] or Decimal('1.00'), 'sort_order': p['sort_order'],
                    'is_active': p['is_active'],
                    'created_by': p['created_by'] or 0, 'created_time': p['created_time'],
                    'deleted': p['deleted'],
                })
            await conn.commit()

            # 7. Materials
            logger.info('=== Migrate materials ===')
            mats = (await conn.execute(text(
                "SELECT id, title, content, source, created_by, created_time, deleted "
                "FROM study_question_material WHERE deleted = 0"
            ))).mappings().all()
            logger.info('  Found %d materials', len(mats))

            sql_mat = text(
                "INSERT INTO qbank_v2_material (id, code, current_revision_id, status, "
                "created_by, updated_by, created_time, updated_time, deleted) "
                "VALUES (:id, :code, NULL, 'active', :cb, :cb, :ct, :ct, :deleted) "
                "ON CONFLICT (id) DO NOTHING"
            )
            sql_mrev = text(
                "INSERT INTO qbank_v2_material_revision (material_id, revision_no, title, content, "
                "content_format, source_name, structured_data, status, published_by, published_time, "
                "created_by, updated_by, created_time, updated_time, deleted) "
                "VALUES (:mid, 1, :title, :content, 'html', :source, "
                "'{}'::jsonb, 'published', :pb, :pt, :cb, :cb, :ct, :ct, :d) "
                "ON CONFLICT (material_id, revision_no) DO NOTHING"
            )
            for m in mats:
                await conn.execute(sql_mat, {'id': m['id'], 'code': f'm_{m["id"]}', 'cb': m['created_by'] or 0, 'ct': m['created_time'], 'deleted': m['deleted']})
                cb = m['created_by'] or 0
                await conn.execute(sql_mrev, {
                    'mid': m['id'], 'title': m['title'] or '', 'content': m['content'] or '',
                    'source': m['source'],
                    'pb': cb, 'pt': m['created_time'],
                    'cb': cb, 'ct': m['created_time'],
                    'd': m['deleted'],
                })
            await conn.commit()

            sql_m_upd = text(
                "UPDATE qbank_v2_material m SET current_revision_id = r.id "
                "FROM qbank_v2_material_revision r "
                "WHERE r.material_id = m.id AND r.revision_no = 1 AND m.current_revision_id IS NULL"
            )
            await conn.execute(sql_m_upd)
            await conn.commit()

            # 8. Bank categories
            logger.info('=== Migrate bank-category associations ===')
            cats = (await conn.execute(text(
                "SELECT id AS bank_id, cat_id FROM study_question_bank "
                "WHERE bank_type IN (1, 2) AND deleted = 0 AND cat_id > 0"
            ))).mappings().all()
            logger.info('  Found %d associations', len(cats))
            sql_cat = text(
                "INSERT INTO qbank_v2_bank_category (bank_id, category_id, is_primary, sort_order, "
                "created_by, created_time, deleted) "
                "VALUES (:bank_id, :cat_id, true, 0, 0, NOW(), 0) ON CONFLICT DO NOTHING"
            )
            for c in cats:
                await conn.execute(sql_cat, {'bank_id': c['bank_id'], 'cat_id': c['cat_id']})
            await conn.commit()

        except Exception as e:
            logger.error('Migration error: %s', e)
            raise
        finally:
            try:
                await conn.execute(text('SET session_replication_role = origin'))
                await conn.commit()
            except Exception:
                pass
    await engine.dispose()
    logger.info('=== Migration complete ===')


if __name__ == '__main__':
    asyncio.run(migrate())
