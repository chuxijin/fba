#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import os
import sys
from datetime import datetime, date

# 将项目根目录添加到 python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from backend.app.task.tasks.gongkao.tasks import fetch_news_list, process_content_with_ai
from backend.app.gongkao.crud.crud_shizhen import shizhen_dao
from backend.app.gongkao.schema.shizhen import CreateShizhenParam
from backend.database.db import async_db_session


async def main():
    target_start_date = date(2026, 1, 1)
    page_num = 1
    page_size = 10
    
    print(f"开始抓取新闻，目标其实日期: {target_start_date}")
    
    async with async_db_session() as db:
        while True:
            print(f"正在获取第 {page_num} 页...")
            try:
                data = await fetch_news_list(page_num, page_size)
            except Exception as e:
                print(f"获取列表失败: {e}")
                break
                
            if not data or data.get('code') != 0:
                print(f"API返回错误: {data}")
                break
                
            records = data.get('result', {}).get('records', [])
            if not records:
                print("未获取到记录，停止。")
                break
            
            stop_fetching = False
            processed_count = 0
            
            for record in records:
                title = record.get('title', '无标题')
                add_time = record.get('addTime')
                
                if not add_time:
                    print(f"跳过无日期记录: {title}")
                    continue
                    
                try:
                    record_date = datetime.strptime(add_time, '%Y-%m-%d').date()
                except ValueError:
                    print(f"日期格式错误: {add_time}")
                    continue
                
                if record_date < target_start_date:
                    print(f"记录日期 {record_date} 早于目标日期 {target_start_date}，停止抓取。")
                    stop_fetching = True
                    break
                    
                # 检查数据库是否已存在
                existing = await shizhen_dao.get_by_date(db, record_date)
                if existing:
                    print(f"[已存在] {record_date} {title} - 正在重新获取并覆盖...")
                    # 删除旧记录以便重新生成
                    await shizhen_dao.delete(db, [existing.id])
                    await db.flush()
                
                print(f"[处理中] {record_date} {title}...")
                
                # 调用 AI 处理
                intro = record.get('intro', '')
                try:
                    ai_result = await process_content_with_ai(db, intro)
                    
                    obj = CreateShizhenParam(
                        daily_date=record_date,
                        original=ai_result['original'],
                        summary=ai_result['summary']
                    )
                    
                    await shizhen_dao.create(db, obj, created_by=1)
                    await db.commit() # 防止长事务，每条提交一次
                    processed_count += 1
                    print(f"[成功] {record_date} 已保存")
                    
                except Exception as e:
                    print(f"[错误] 处理 {title} 失败: {e}")
            
            print(f"第 {page_num} 页处理完成，新增 {processed_count} 条。")
            
            if stop_fetching:
                break
                
            page_num += 1
            # 简单的防封禁/防过快延时
            await asyncio.sleep(1)

if __name__ == '__main__':
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
