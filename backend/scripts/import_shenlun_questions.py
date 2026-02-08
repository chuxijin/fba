#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
申论题目导入脚本 - 直接写入数据库

用法:
1. 确保在 backend 目录下运行
2. python scripts/import_shenlun_questions.py

数据映射:
- expandedMaterials → study_question_material (材料表)
- questions → study_question (题目表)
- questions[].answers → study_question_analysis (解析表，多版本)
"""

import asyncio
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.db import async_db_session


def chinese_number(n: int) -> str:
    """将数字转换为中文序号"""
    nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
    if n <= 10:
        return nums[n]
    elif n < 20:
        return '十' + nums[n - 10]
    else:
        return str(n)


def extract_score_from_content(content: str) -> Decimal:
    """从题目内容中提取分值，如 (15分) → 15"""
    match = re.search(r'[（(](\d+)分[）)]', content)
    if match:
        return Decimal(match.group(1))
    return Decimal('10.0')  # 默认分值


def clean_html_content(content: str) -> str:
    """清理 HTML 内容中的 Angular 属性"""
    if not content:
        return ''
    # 去掉 Angular 的 _ngcontent 属性
    content = re.sub(r'\s*_ngcontent-[^"]*="[^"]*"', '', content)
    content = re.sub(r'\s*class="[^"]*ng-star-inserted[^"]*"', '', content)
    return content



async def get_next_id(session: AsyncSession, table_name: str) -> int:
    """获取表的下一个 ID"""
    result = await session.execute(
        text(f'SELECT COALESCE(MAX(id), 0) + 1 FROM "fba"."{table_name}"')
    )
    return result.scalar()


async def get_next_question_id(session: AsyncSession) -> int:
    """获取下一个题目 ID，同时考虑多个关联表"""
    max_ids = []
    
    # 从 question 表获取最大 ID
    result1 = await session.execute(
        text('SELECT COALESCE(MAX(id), 0) FROM "fba"."study_question"')
    )
    max_ids.append(result1.scalar())
    
    # 从 statistics 表获取最大 question_id
    try:
        result2 = await session.execute(
            text('SELECT COALESCE(MAX(question_id), 0) FROM "fba"."study_question_statistics"')
        )
        max_ids.append(result2.scalar())
    except Exception:
        pass  # 表可能不存在
    
    # 从 analysis 表获取最大 question_id
    try:
        result3 = await session.execute(
            text('SELECT COALESCE(MAX(question_id), 0) FROM "fba"."study_question_analysis"')
        )
        max_ids.append(result3.scalar())
    except Exception:
        pass
    
    # 返回所有表中最大的 + 1
    return max(max_ids) + 1


async def import_data(
    bank_name: str,
    bank_code: str,
    cat_id: int,
    parent_id: int | None,
    data: dict,
) -> None:
    """
    导入数据到数据库

    Args:
        bank_name: 题库名称
        bank_code: 题库编码
        cat_id: 分类 ID
        parent_id: 父级题库 ID
        data: JSON 响应中的 result 对象
    """
    async with async_db_session() as session:
        try:
            # 1. 获取下一个 ID
            bank_id = await get_next_id(session, 'study_question_bank')
            material_start_id = await get_next_id(session, 'study_question_material')
            question_start_id = await get_next_question_id(session)  # 考虑 statistics 表
            analysis_start_id = await get_next_id(session, 'study_question_analysis')

            print(f"题库 ID: {bank_id}")
            print(f"材料起始 ID: {material_start_id}")
            print(f"题目起始 ID: {question_start_id}")
            print(f"解析起始 ID: {analysis_start_id}")

            # 2. 插入题库
            await session.execute(
                text("""
                    INSERT INTO "fba"."study_question_bank" 
                        ("id", "cat_id", "name", "code", "desc", "cover_url", "difficulty", 
                         "parent_id", "status", "scope", "q_count", "total_score", "buy_count", 
                         "created_time", "updated_time", "type")
                    VALUES 
                        (:id, :cat_id, :name, :code, NULL, NULL, NULL, 
                         :parent_id, 1, 1, 0, 0, 0, 
                         NOW(), NULL, 10)
                """),
                {
                    'id': bank_id,
                    'cat_id': cat_id,
                    'name': bank_name,
                    'code': bank_code,
                    'parent_id': parent_id,
                }
            )
            print(f"✓ 插入题库: {bank_name}")

            # 3. 插入材料
            materials = data.get('expandedMaterials', [])
            material_ids = []

            for idx, material_content in enumerate(materials):
                material_id = material_start_id + idx
                material_ids.append(material_id)
                title = f"材料{chinese_number(idx + 1)}"
                clean_content = clean_html_content(material_content)

                await session.execute(
                    text("""
                        INSERT INTO "fba"."study_question_material" 
                            ("id", "bank_id", "title", "content", "category_id", "source", 
                             "year", "sort_order", "is_active", "created_time", "updated_time", 
                             "created_by", "updated_by")
                        VALUES 
                            (:id, :bank_id, :title, :content, NULL, NULL, 
                             NULL, :sort_order, true, NOW(), NULL, 
                             1, NULL)
                    """),
                    {
                        'id': material_id,
                        'bank_id': bank_id,
                        'title': title,
                        'content': clean_content,
                        'sort_order': idx,
                    }
                )
                print(f"  ✓ 插入材料: {title}")

            # 4. 插入题目和解析
            questions = data.get('questions', [])
            question_ids = []
            total_score = Decimal('0')

            for q_idx, question in enumerate(questions):
                question_id = question_start_id + q_idx
                question_ids.append(question_id)

                # 题干 = content + require
                content = question.get('content', '')
                require = question.get('require', '')
                stem = f"{content}\n\n{require}" if require else content
                
                # 提取分值
                score = extract_score_from_content(content)
                total_score += score

                await session.execute(
                    text("""
                        INSERT INTO "fba"."study_question" 
                            ("id", "bank_id", "chapter_id", "type", "stem", "options_data", 
                             "difficulty", "score", "knowledge_point", "source", "year", 
                             "usage", "is_active", "review_status", "created_time", 
                             "updated_time", "created_by", "updated_by")
                        VALUES 
                            (:id, :bank_id, NULL, 'shortAnswer', :stem, NULL, 
                             'medium', :score, NULL, NULL, NULL, 
                             'all', true, 10, NOW(), 
                             NULL, 1, NULL)
                    """),
                    {
                        'id': question_id,
                        'bank_id': bank_id,
                        'stem': stem,
                        'score': score,
                    }
                )
                print(f"  ✓ 插入题目 {q_idx + 1}: {content[:30]}...")

                # 5. 插入解析（多版本）
                answers = question.get('answers', [])
                for a_idx, answer in enumerate(answers):
                    analysis_id = analysis_start_id + q_idx * 100 + a_idx
                    organ = answer.get('organ', '官方')
                    answer_content = answer.get('answer', '')
                    good_count = answer.get('good', 0)
                    no_good_count = answer.get('noGood', 0)

                    # answer_data 结构（只需要 correct）
                    answer_data = {
                        "correct": answer_content,
                    }
                    answer_data_json = json.dumps(answer_data, ensure_ascii=False)

                    # 第一个默认展示
                    is_default = a_idx == 0

                    await session.execute(
                        text("""
                            INSERT INTO "fba"."study_question_analysis" 
                                ("id", "question_id", "answer_data", "content", "type",
                                 "is_default", "view_count", "helpful_count", "unhelpful_count", 
                                 "created_time", "updated_time", "created_by", "updated_by")
                            VALUES 
                                (:id, :question_id, CAST(:answer_data AS jsonb), :content, :type,
                                 :is_default, 0, :helpful_count, :unhelpful_count, 
                                 NOW(), NULL, 1, NULL)
                        """),
                        {
                            'id': analysis_id,
                            'question_id': question_id,
                            'answer_data': answer_data_json,
                            'content': answer_content,
                            'type': organ,  # 机构名称直接存入 type 字段
                            'is_default': is_default,
                            'helpful_count': good_count,
                            'unhelpful_count': no_good_count,
                        }
                    )
                    print(f"    ✓ 插入解析: {organ}")

            # 6. 插入题目-材料关联
            for question_id in question_ids:
                for m_idx, material_id in enumerate(material_ids):
                    await session.execute(
                        text("""
                            INSERT INTO "fba"."study_question_material_relation" 
                                ("question_id", "material_id", "sort_order")
                            VALUES 
                                (:question_id, :material_id, :sort_order)
                        """),
                        {
                            'question_id': question_id,
                            'material_id': material_id,
                            'sort_order': m_idx,
                        }
                    )
            print(f"  ✓ 插入题目-材料关联: {len(question_ids)} 题 x {len(material_ids)} 材料")

            # 7. 更新题库统计
            await session.execute(
                text("""
                    UPDATE "fba"."study_question_bank" 
                    SET "q_count" = :q_count, "total_score" = :total_score
                    WHERE "id" = :id
                """),
                {
                    'id': bank_id,
                    'q_count': len(questions),
                    'total_score': total_score,
                }
            )
            print(f"  ✓ 更新题库统计: {len(questions)} 题, 总分 {total_score}")

            # 所有操作成功，提交事务
            await session.commit()
            
            print("\n" + "=" * 50)
            print("✅ 导入成功！所有数据已提交到数据库")
            print(f"  题库 ID: {bank_id}")
            print(f"  材料数量: {len(material_ids)}")
            print(f"  题目数量: {len(question_ids)}")
            print(f"  解析数量: {sum(len(q.get('answers', [])) for q in questions)}")

        except Exception as e:
            # 发生任何错误，回滚事务
            await session.rollback()
            print("\n" + "=" * 50)
            print("❌ 导入失败！所有数据已回滚，数据库未发生任何变化")
            print(f"错误信息: {e}")
            raise


async def main():
    """主函数"""
    print("=" * 60)
    print("申论题目导入脚本 - 直接写入数据库")
    print("=" * 60)

    # 输入参数
    bank_name = input("请输入题库名称 (如: 2024年国家公考《申论》题（行政执法）): ").strip()
    if not bank_name:
        bank_name = "2024年国家公考《申论》题（行政执法）"

    bank_code = input("请输入题库编码 (如: 2024国家申论): ").strip()
    if not bank_code:
        # 从名称生成编码
        bank_code = bank_name.replace("《", "").replace("》", "").replace("（", "_").replace("）", "")[:30]

    # 固定参数
    cat_id = 1
    parent_id = 3

    # 读取 JSON 数据
    print("\n请选择 JSON 输入方式:")
    print("  1. 直接粘贴 JSON")
    print("  2. 从文件读取")
    input_mode = input("请选择 (默认 1): ").strip()
    
    if input_mode == '2':
        json_file = input("请输入 JSON 文件路径: ").strip()
        with open(json_file, 'r', encoding='utf-8') as f:
            response = json.load(f)
    else:
        print("\n请粘贴 JSON 内容，粘贴完成后输入 END 并回车:")
        lines = []
        while True:
            try:
                line = input()
                if line.strip().upper() == 'END':
                    break
                lines.append(line)
            except EOFError:
                break
        json_content = '\n'.join(lines)
        response = json.loads(json_content)

    # 提取 result
    data = response.get('result', response)

    # 执行导入
    await import_data(
        bank_name=bank_name,
        bank_code=bank_code,
        cat_id=cat_id,
        parent_id=parent_id,
        data=data,
    )


if __name__ == '__main__':
    asyncio.run(main())
