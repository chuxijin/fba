#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
词语数据增强脚本

使用 AI 批量完善词语的 meaning、pinyin、example、category、source、emotion 字段
只补充为空的字段，保留已有值

使用方法:
    cd backend && python ../scripts/enrich_ciyu.py

断点续传:
    脚本会自动从 meaning 或 pinyin 为空的词语开始处理
    可通过 --start-id 参数指定起始 ID
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

# 添加 backend 到路径
backend_path = Path(__file__).resolve().parent.parent / 'backend'
sys.path.insert(0, str(backend_path.parent))

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.model.ciyu import GkCiyu
from backend.database.db import async_db_session

# ==================== 配置 ====================
API_BASE_URL = 'https://api.5202030.xyz/v1'
API_KEY = 'sk-iNO8DjjOf9o7x6k_OPh0VQn9V1e9XjNb7A1V8alyHsq1C9hK4JCtFCVQUpA'
MODEL = 'gpt-4o'
BATCH_SIZE = 10
REQUEST_TIMEOUT = 60.0

# 需要填充的字段
FIELDS_TO_FILL = ['meaning', 'pinyin', 'example', 'category', 'source', 'emotion']


# ==================== AI 调用 ====================
async def call_ai(client: httpx.AsyncClient, word: str, existing_data: dict) -> dict | None:
    """
    调用 AI 获取词语补充信息

    :param client: HTTP 客户端
    :param word: 词语
    :param existing_data: 已有数据（用于提示 AI）
    :return:
    """
    # 构建已有信息提示
    existing_info = []
    if existing_data.get('meaning'):
        existing_info.append(f"已有释义：{existing_data['meaning']}")
    if existing_data.get('pinyin'):
        existing_info.append(f"已有拼音：{existing_data['pinyin']}")

    existing_hint = '\n'.join(existing_info) if existing_info else '暂无已有信息'

    prompt = f"""请为以下词语提供详细信息，以 JSON 格式返回：

词语：{word}
{existing_hint}

请返回以下字段（JSON 格式，不要包含 markdown 代码块）：
{{
    "meaning": "词义解释（简洁准确，50字以内）",
    "pinyin": "拼音（带声调，如：cí yǔ）",
    "example": "一个使用该词语的例句（15-30字）",
    "category": "词语分类（只能是以下之一：成语、词语）",
    "source": "出处或来源（如：《成语词典》、《论语》、常用语等）",
    "emotion": "感情色彩（只能是以下之一：褒义、贬义、中性）"
}}

注意：
1. 如果已有释义，请参考但可以优化
2. 拼音请使用带声调的格式
3. 只返回 JSON，不要其他内容"""

    try:
        response = await client.post(
            f'{API_BASE_URL}/chat/completions',
            headers={
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': MODEL,
                'messages': [
                    {'role': 'system', 'content': '你是一个专业的汉语词典编辑，擅长提供准确的词语释义、拼音和例句。'},
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.3,
                'max_tokens': 500,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        content = data['choices'][0]['message']['content'].strip()

        # 尝试清理可能的 markdown 代码块
        if content.startswith('```'):
            lines = content.split('\n')
            content = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

        # 第一次尝试直接解析
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # 修复 AI 返回中值内部的中文引号和未转义引号
            # 将中文引号替换为空（它们通常出现在释义中）
            fixed = content.replace('\u201c', '').replace('\u201d', '')
            fixed = fixed.replace('\u300a', '《').replace('\u300b', '》')
            # 尝试用正则按 key 提取值
            result = {}
            for key in ['meaning', 'pinyin', 'example', 'category', 'source', 'emotion']:
                match = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', fixed)
                if match:
                    result[key] = match.group(1)
            if not result:
                raise json.JSONDecodeError('无法提取任何字段', content, 0)

        # 验证并修正字段
        valid_categories = ['成语', '词语']
        if result.get('category') not in valid_categories:
            result['category'] = '词语'

        valid_emotions = ['褒义', '贬义', '中性']
        if result.get('emotion') not in valid_emotions:
            result['emotion'] = '中性'

        return result

    except httpx.HTTPStatusError as e:
        print(f'❌ API 错误: {e.response.status_code}')
        print(f'   响应内容: {e.response.text}')  # 增加这一行打印详细错误信息
        return None
    except json.JSONDecodeError as e:
        print(f'❌ JSON 解析失败: {e}')
        # print(f'   原始内容: {data}') # 如果需要调试可以打开
        try:
            print(f'   响应文本: {response.text[:200]}...') # 打印前200个字符看看是啥
        except:
            pass
        return None
    except Exception as e:
        print(f'❌ 错误: {e}')
        return None


# ==================== 数据库操作 ====================
async def get_pending_ciyu(session: AsyncSession, start_id: int, limit: int) -> list[GkCiyu]:
    """
    获取待处理的词语（meaning 或 pinyin 为空）

    :param session: 数据库会话
    :param start_id: 起始 ID
    :param limit: 数量限制
    :return:
    """
    stmt = (
        select(GkCiyu)
        .where(GkCiyu.id >= start_id)
        .where(
            (GkCiyu.meaning.is_(None)) | (GkCiyu.meaning == '') |
            (GkCiyu.pinyin.is_(None)) | (GkCiyu.pinyin == '')
        )
        .order_by(GkCiyu.id)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_ciyu(session: AsyncSession, ciyu: GkCiyu, ai_data: dict) -> bool:
    """
    更新词语信息（只更新为空的字段）

    :param session: 数据库会话
    :param ciyu: 词语对象
    :param ai_data: AI 返回的数据
    :return:
    """
    try:
        update_values = {}

        # 只更新为空的字段
        if not ciyu.meaning and ai_data.get('meaning'):
            update_values['meaning'] = ai_data['meaning']
        if not ciyu.pinyin and ai_data.get('pinyin'):
            update_values['pinyin'] = ai_data['pinyin']
        if not ciyu.example and ai_data.get('example'):
            update_values['example'] = ai_data['example']
        if not ciyu.category and ai_data.get('category'):
            update_values['category'] = ai_data['category']
        if not ciyu.source and ai_data.get('source'):
            update_values['source'] = ai_data['source']
        if not ciyu.emotion and ai_data.get('emotion'):
            update_values['emotion'] = ai_data['emotion']

        if not update_values:
            return True  # 无需更新

        stmt = update(GkCiyu).where(GkCiyu.id == ciyu.id).values(**update_values)
        await session.execute(stmt)
        await session.commit()
        return True
    except Exception as e:
        print(f'❌ 数据库更新失败: {e}')
        await session.rollback()
        return False


async def get_total_pending(session: AsyncSession) -> int:
    """获取待处理词语总数"""
    stmt = select(func.count()).select_from(GkCiyu).where(
        (GkCiyu.meaning.is_(None)) | (GkCiyu.meaning == '') |
        (GkCiyu.pinyin.is_(None)) | (GkCiyu.pinyin == '')
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


# ==================== 主流程 ====================
async def main(start_id: int = 1):
    """主函数"""
    print('=' * 60)
    print('       词语数据增强脚本')
    print('=' * 60)
    print(f'📋 配置信息:')
    print(f'   API: {API_BASE_URL}')
    print(f'   模型: {MODEL}')
    print(f'   批次大小: {BATCH_SIZE}')
    print(f'   起始 ID: {start_id}')
    print(f'   填充字段: {", ".join(FIELDS_TO_FILL)}')
    print('=' * 60)
    print()

    success_count = 0
    error_count = 0
    last_id = start_id

    async with httpx.AsyncClient() as client:
        while True:
            async with async_db_session() as session:
                # 获取待处理总数（仅首次）
                if last_id == start_id:
                    total = await get_total_pending(session)
                    print(f'📊 待处理词语总数: {total}')
                    if total == 0:
                        print('✅ 无需处理，所有词语已完整！')
                        return
                    print()

                # 获取一批待处理词语
                ciyu_list = await get_pending_ciyu(session, last_id, BATCH_SIZE)

                if not ciyu_list:
                    print()
                    print('✅ 所有词语处理完成！')
                    break

                print(f'📦 处理批次: ID {ciyu_list[0].id} - {ciyu_list[-1].id}')

                for ciyu in ciyu_list:
                    last_id = ciyu.id + 1

                    # 构建已有数据
                    existing_data = {
                        'meaning': ciyu.meaning,
                        'pinyin': ciyu.pinyin,
                    }

                    # 显示缺失字段
                    missing = []
                    if not ciyu.meaning:
                        missing.append('义')
                    if not ciyu.pinyin:
                        missing.append('音')
                    if not ciyu.example:
                        missing.append('例')
                    if not ciyu.category:
                        missing.append('类')
                    if not ciyu.source:
                        missing.append('源')
                    if not ciyu.emotion:
                        missing.append('情')

                    missing_str = ','.join(missing) if missing else '无'
                    print(f'  [{ciyu.id}] {ciyu.word} (缺:{missing_str})...', end=' ')

                    # 调用 AI
                    result = await call_ai(client, ciyu.word, existing_data)

                    if result is None:
                        error_count += 1
                        print('跳过')
                        continue

                    # 更新数据库
                    if await update_ciyu(session, ciyu, result):
                        success_count += 1
                        emotion = result.get('emotion', '?')
                        category = result.get('category', '?')
                        print(f'✅ [{category}/{emotion}]')
                    else:
                        error_count += 1
                        print('❌')
                    
                    # 速率限制：50 RPM 意味着每次请求间隔至少 1.2s
                    # 这里设置为 1.5s 以确保安全
                    await asyncio.sleep(1.5)

                # 批次间隔
                print(f'  📈 进度: 成功 {success_count}, 失败 {error_count}')
                print()

                # 短暂延迟避免 API 限流
                await asyncio.sleep(0.5)

    print('=' * 60)
    print(f'🎉 处理完成!')
    print(f'   ✅ 成功: {success_count}')
    print(f'   ❌ 失败: {error_count}')
    print(f'   📍 最后 ID: {last_id}')
    print('=' * 60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='词语数据增强脚本')
    parser.add_argument('--start-id', type=int, default=1, help='起始 ID（用于断点续传）')
    args = parser.parse_args()

    try:
        asyncio.run(main(args.start_id))
    except KeyboardInterrupt:
        print()
        print('⚠️ 用户中断，可使用 --start-id 参数继续')
