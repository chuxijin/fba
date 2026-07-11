#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seed resource type dict

Revision ID: c3e2d4f6a789
Revises: b8f4c6d9a123
Create Date: 2026-07-05 15:00:00.000000

"""
from alembic import op


revision = 'c3e2d4f6a789'
down_revision = 'b8f4c6d9a123'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """写入资源类型字典"""
    op.execute(
        """
        DO $$
        DECLARE
            resource_type_id bigint;
            dict_type_seq text;
            dict_data_seq text;
        BEGIN
            SELECT id INTO resource_type_id
            FROM sys_dict_type
            WHERE code = 'resource_type' AND deleted = 0
            ORDER BY id
            LIMIT 1;

            IF resource_type_id IS NULL THEN
                SELECT COALESCE(MAX(id), 0) + 1 INTO resource_type_id
                FROM sys_dict_type;

                INSERT INTO sys_dict_type (id, name, code, remark, created_time, updated_time, deleted)
                VALUES (resource_type_id, '资源类型', 'resource_type', '资源管理资源类型', now(), null, 0);
            END IF;

            WITH seed(label, value, color, sort, remark) AS (
                VALUES
                ('课程', '课程', 'blue', 1, '课程资源'),
                ('电子书', '电子书', 'green', 2, '电子书资源'),
                ('笔记', '笔记', 'cyan', 3, '笔记资源'),
                ('软件', '软件', 'purple', 4, '软件资源'),
                ('真题', '真题', 'orange', 5, '真题资源'),
                ('其他', '其他', 'default', 6, '其他资源')
            ),
            missing AS (
                SELECT seed.*
                FROM seed
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM sys_dict_data
                    WHERE type_code = 'resource_type'
                      AND label = seed.label
                      AND deleted = 0
                )
            ),
            numbered AS (
                SELECT
                    (SELECT COALESCE(MAX(id), 0) FROM sys_dict_data)
                        + ROW_NUMBER() OVER (ORDER BY sort) AS id,
                    *
                FROM missing
            )
            INSERT INTO sys_dict_data (
                id, type_code, label, value, color, sort, status, remark, type_id,
                created_time, updated_time, deleted
            )
            SELECT
                id, 'resource_type', label, value, color, sort, 1, remark, resource_type_id,
                now(), null, 0
            FROM numbered;

            SELECT pg_get_serial_sequence('sys_dict_type', 'id') INTO dict_type_seq;
            IF dict_type_seq IS NOT NULL THEN
                EXECUTE format(
                    'SELECT setval(%L, (SELECT COALESCE(MAX(id), 0) FROM sys_dict_type), true)',
                    dict_type_seq
                );
            END IF;

            SELECT pg_get_serial_sequence('sys_dict_data', 'id') INTO dict_data_seq;
            IF dict_data_seq IS NOT NULL THEN
                EXECUTE format(
                    'SELECT setval(%L, (SELECT COALESCE(MAX(id), 0) FROM sys_dict_data), true)',
                    dict_data_seq
                );
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """移除资源类型字典"""
    op.execute(
        """
        DELETE FROM sys_dict_data
        WHERE type_code = 'resource_type'
          AND deleted = 0
          AND label IN ('课程', '电子书', '笔记', '软件', '真题', '其他');

        DELETE FROM sys_dict_type
        WHERE code = 'resource_type'
          AND deleted = 0
          AND NOT EXISTS (
              SELECT 1
              FROM sys_dict_data
              WHERE type_code = 'resource_type' AND deleted = 0
          );
        """
    )
