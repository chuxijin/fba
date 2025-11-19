#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import requests
import sys
import os
from pathlib import Path
from datetime import datetime
import json
import re
from typing import List, Dict, Any
import time

# 设置控制台编码为UTF-8，避免Windows编码问题
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入项目依赖
try:
    from backend.database.db import async_db_session
    from backend.app.job.model.job_posting import JobPosting
    from backend.app.job.model.internship_posting import InternshipPosting
    HAS_DB_ACCESS = True
    print("[成功] 数据库连接成功")
except ImportError as e:
    print(f"[失败] 数据库导入失败: {e}")
    HAS_DB_ACCESS = False


class GiveMeOCAPI:
    """GiveMeOC招聘信息API客户端"""
    
    def __init__(self):
        self.base_url = "https://www.givemeoc.com/wp-admin/admin-ajax.php"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://www.givemeoc.com',
            'Referer': 'https://www.givemeoc.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Cookie': 'wordpress_sec_ce5e4d2c76be9325f50ac09dcde8fe73=mpweixin_34829874%7C1760082627%7C9vHtO8Wj6HWzyLMqZbeCGffUcY0v5PRvIOmHclHwHc0%7C1dca2387264d951e1c1980bde0171c8763c4f0de8c6bdfbd77d4dd19819e138a; wordpress_logged_in_ce5e4d2c76be9325f50ac09dcde8fe73=mpweixin_34829874%7C1760082627%7C9vHtO8Wj6HWzyLMqZbeCGffUcY0v5PRvIOmHclHwHc0%7Cfd7f36e777ac0079a46aabf11e0182727129a327c3d3cefd48f56bf6cdc5ccab; online_count=307; online_count_time=1759477895; shuaidi_OC=64'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def get_page_data(self, page: int = 1, data_type: str = 'campus', **filters) -> Dict[str, Any]:
        """
        获取指定页面的招聘数据
        
        :param page: 页码
        :param data_type: 数据类型 ('campus'=校招, 'internship'=实习)
        :param filters: 过滤条件
        :return: API响应数据
        """
        if data_type == 'internship':
            # 实习生数据
            data = {
                'action': 'int_filter_companies',
                'nonce': 'f7d50512ac',  # 实习生的nonce
                'paged': str(page),
                'company_name': filters.get('company_name', ''),
                'company_type': filters.get('company_type', ''),
                'location': filters.get('location', ''),
                'recruitment_type': filters.get('recruitment_type', ''),
                'target_candidates': filters.get('target_candidates', ''),
                'position': filters.get('position', ''),
                'progress_status': filters.get('progress_status', '')
            }
        else:
            # 校招数据
            data = {
                'action': 'filter_companies',
                'nonce': '07da4e6e26',  # 校招的nonce
                'paged': str(page),
                'company_name': filters.get('company_name', ''),
                'company_type': filters.get('company_type', ''),
                'location': filters.get('location', ''),
                'recruitment_type': filters.get('recruitment_type', ''),
                'target_candidates': filters.get('target_candidates', ''),
                'position': filters.get('position', ''),
                'progress_status': filters.get('progress_status', ''),
                'should_increment_counter': '1'
            }
        
        try:
            response = self.session.post(self.base_url, data=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"[失败] 请求第 {page} 页失败: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"[失败] 解析第 {page} 页JSON失败: {e}")
            return {}
    
    def parse_html_to_jobs(self, html: str, data_type: str = 'campus') -> List[Dict[str, Any]]:
        """
        解析HTML内容为招聘信息列表
        
        :param html: HTML内容
        :param data_type: 数据类型 ('campus'=校招, 'internship'=实习)
        :return: 招聘信息列表
        """
        jobs = []
        
        # 根据数据类型选择CSS class前缀
        prefix = 'int' if data_type == 'internship' else 'crt'
        
        # 匹配表格行 <tr data-id="...">
        tr_pattern = r'<tr data-id="(\d+)".*?>(.*?)</tr>'
        tr_matches = re.findall(tr_pattern, html, re.DOTALL)
        
        for data_id, tr_content in tr_matches:
            job_data = {
                "id": int(data_id) if data_id.isdigit() else None,
                "company_name": "",
                "company_type": None,
                "industry": None,
                "recruitment_type": None,
                "work_location": None,
                "recruitment_object": None,
                "position": "",
                "delivery_start": None,
                "delivery_end": None,
                "delivery_link": None,
                "recruitment_announcement": None,
                "referral_code": None,
                "remark": None,
                "salary_range": None,
                "is_exempt_from_written_test": False,
                "logo_url": None
            }
            
            # 提取公司名称
            company_match = re.search(rf'<td class="{prefix}-col-company"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if company_match:
                job_data["company_name"] = re.sub(r'<[^>]+>', '', company_match.group(1)).strip()
            
            # 提取公司类型
            type_match = re.search(rf'<span class="{prefix}-badge {prefix}-type-([^"]*)"[^>]*>([^<]*)</span>', tr_content)
            if type_match:
                job_data["company_type"] = type_match.group(2).strip()
            
            # 提取行业（第二个col-company）
            company_matches = re.findall(rf'<td class="{prefix}-col-company"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if len(company_matches) >= 2:
                job_data["industry"] = re.sub(r'<[^>]+>', '', company_matches[1]).strip()
            
            # 提取招聘类型
            recruitment_match = re.search(rf'<span class="{prefix}-badge {prefix}-recruitment-([^"]*)"[^>]*>([^<]*)</span>', tr_content)
            if recruitment_match:
                job_data["recruitment_type"] = recruitment_match.group(2).strip()
            
            # 提取工作地点
            location_match = re.search(rf'<td class="{prefix}-col-location"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if location_match:
                job_data["work_location"] = re.sub(r'<[^>]+>', '', location_match.group(1)).strip()
            
            # 提取招聘对象
            target_match = re.search(rf'<span class="{prefix}-badge {prefix}-target-([^"]*)"[^>]*>([^<]*)</span>', tr_content)
            if target_match:
                job_data["recruitment_object"] = target_match.group(2).strip()
            
            # 提取岗位信息
            position_match = re.search(rf'<span class="{prefix}-position-tag"[^>]*>(.*?)</span>', tr_content, re.DOTALL)
            if position_match:
                job_data["position"] = re.sub(r'<[^>]+>', '', position_match.group(1)).strip()
            
            # 提取更新时间（作为开始时间）
            update_time_match = re.search(rf'<td class="{prefix}-col-update-time"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if update_time_match:
                update_time_text = re.sub(r'<[^>]+>', '', update_time_match.group(1)).strip()
                if update_time_text:
                    try:
                        parsed_date = datetime.strptime(update_time_text, '%Y-%m-%d').date()
                        job_data["delivery_start"] = parsed_date
                    except:
                        pass
            
            # 提取截止日期
            deadline_match = re.search(rf'<td class="{prefix}-col-deadline"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if deadline_match:
                deadline_text = re.sub(r'<[^>]+>', '', deadline_match.group(1)).strip()
                if deadline_text and deadline_text != "招满为止":
                    try:
                        parsed_date = datetime.strptime(deadline_text, '%Y-%m-%d').date()
                        job_data["delivery_end"] = parsed_date
                    except:
                        pass
            
            # 提取投递链接
            link_match = re.search(rf'<td class="{prefix}-col-links"[^>]*>.*?<a href="([^"]*)"[^>]*>投递</a>', tr_content, re.DOTALL)
            if link_match:
                job_data["delivery_link"] = link_match.group(1).strip()
            
            # 提取招聘公告链接
            notice_match = re.search(rf'<td class="{prefix}-col-notice"[^>]*>.*?<a href="([^"]*)"[^>]*>公告</a>', tr_content, re.DOTALL)
            if notice_match:
                job_data["recruitment_announcement"] = notice_match.group(1).strip()
            
            # 提取内推码
            referral_match = re.search(rf'<td class="{prefix}-col-referral"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if referral_match:
                referral_text = re.sub(r'<[^>]+>', '', referral_match.group(1)).strip()
                if referral_text and referral_text != "-":
                    job_data["referral_code"] = referral_text
            
            # 提取备注
            notes_match = re.search(rf'<td class="{prefix}-col-notes"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
            if notes_match:
                notes_text = re.sub(r'<[^>]+>', '', notes_match.group(1)).strip()
                if notes_text and notes_text != "-":
                    job_data["remark"] = notes_text
            
            # 只有公司名称和岗位不为空才添加
            if job_data["company_name"] and job_data["position"]:
                jobs.append(job_data)
        
        return jobs


async def import_jobs_to_database(jobs: List[Dict[str, Any]], created_by: int, data_type: str = 'campus') -> int:
    """
    将招聘信息导入数据库
    
    :param jobs: 招聘信息列表
    :param created_by: 创建者ID
    :param data_type: 数据类型 ('campus'=校招, 'internship'=实习)
    :return: 成功导入的数量
    """
    # 根据数据类型选择模型和表名
    ModelClass = JobPosting if data_type == 'campus' else InternshipPosting
    table_name = "校招信息" if data_type == 'campus' else "实习信息"
    
    if not HAS_DB_ACCESS:
        print(f"模拟导入 {len(jobs)} 条{table_name}，创建者: {created_by}")
        for i, job in enumerate(jobs):
            print(f"  {i+1}. ID {job.get('id', 'N/A')} - {job['company_name']} - {job['position']}")
        return len(jobs)
    
    count = 0
    skipped = 0
    
    async with async_db_session() as db:
        for job_data in jobs:
            try:
                # 检查是否已存在相同ID的记录
                if job_data.get('id'):
                    existing = await db.get(ModelClass, job_data['id'])
                    if existing:
                        skipped += 1
                        continue
                
                # 创建数据库模型实例
                new_job = ModelClass(
                    company_name=job_data["company_name"],
                    company_type=job_data["company_type"],
                    industry=job_data["industry"],
                    recruitment_type=job_data["recruitment_type"],
                    work_location=job_data["work_location"],
                    recruitment_object=job_data["recruitment_object"],
                    position=job_data["position"],
                    delivery_start=job_data["delivery_start"],
                    delivery_end=job_data["delivery_end"],
                    delivery_link=job_data["delivery_link"],
                    recruitment_announcement=job_data["recruitment_announcement"],
                    referral_code=job_data["referral_code"],
                    remark=job_data["remark"],
                    salary_range=job_data["salary_range"],
                    is_exempt_from_written_test=job_data["is_exempt_from_written_test"] or False,
                    logo_url=job_data["logo_url"],
                    created_by=created_by
                )
                
                # 如果有ID，则手动设置ID
                if job_data.get('id'):
                    new_job.id = job_data['id']
                
                db.add(new_job)
                await db.flush()
                count += 1
                
                display_id = f"ID {job_data.get('id')}" if job_data.get('id') else "自动ID"
                print(f"  [成功] {count}. {display_id} - {job_data['company_name']}")
                
            except Exception as e:
                print(f"  [失败] 入库失败: {job_data['company_name']} - {e}")
                continue
        
        await db.commit()
    
    if skipped > 0:
        print(f"[统计] 成功导入 {count} 条{table_name}，跳过重复 {skipped} 条")
    
    return count


async def batch_import_jobs(start_page: int = 1, end_page: int = 10, created_by: int = 1, delay: float = 1.0, data_type: str = 'campus'):
    """
    批量导入招聘信息
    
    :param start_page: 开始页码
    :param end_page: 结束页码
    :param created_by: 创建者ID
    :param delay: 请求间隔时间（秒）
    :param data_type: 数据类型 ('campus'=校招, 'internship'=实习)
    """
    api = GiveMeOCAPI()
    total_imported = 0
    
    data_type_name = "校招信息" if data_type == 'campus' else "实习信息"
    
    print(f"[开始] 批量导入{data_type_name}")
    print(f"[类型] 数据类型: {data_type_name}")
    print(f"[范围] 页码范围: {start_page} - {end_page}")
    print(f"[用户] 创建者ID: {created_by}")
    print(f"[间隔] 请求间隔: {delay}秒")
    print(f"{'='*50}")
    
    for page in range(start_page, end_page + 1):
        print(f"\n[处理] 正在处理第 {page} 页...")
        
        # 获取页面数据
        response_data = api.get_page_data(page, data_type=data_type)
        
        if not response_data.get('success'):
            print(f"[失败] 第 {page} 页获取失败")
            continue
        
        # 解析HTML为招聘信息
        html = response_data.get('data', {}).get('html', '')
        if not html:
            print(f"[警告] 第 {page} 页无数据")
            continue
        
        jobs = api.parse_html_to_jobs(html, data_type=data_type)
        print(f"[解析] 第 {page} 页解析到 {len(jobs)} 条招聘信息")
        
        if jobs:
            # 导入数据库
            imported_count = await import_jobs_to_database(jobs, created_by, data_type)
            total_imported += imported_count
            print(f"[完成] 第 {page} 页导入完成")
        
        # 显示分页信息
        data_info = response_data.get('data', {})
        if 'total_items' in data_info:
            print(f"[统计] 总记录数: {data_info['total_items']}, 当前页: {page}/{data_info.get('total_pages', 'N/A')}")
        
        # 请求间隔
        if page < end_page:
            print(f"[等待] {delay} 秒...")
            time.sleep(delay)
    
    print(f"\n{'='*50}")
    print(f"[完成] 批量导入完成！")
    print(f"[结果] 总共导入: {total_imported} 条{data_type_name}")
    print(f"[统计] 处理页数: {end_page - start_page + 1} 页")


def main():
    """主函数"""
    print("[工具] GiveMeOC招聘信息批量导入工具")
    print("="*50)
    
    # 获取用户输入
    try:
        data_type = input("请选择数据类型 (1=校招, 2=实习, 默认1): ").strip() or "1"
        data_type = 'internship' if data_type == '2' else 'campus'
        
        start_page = int(input("请输入开始页码 (默认1): ") or "1")
        end_page = int(input("请输入结束页码 (默认5): ") or "5")
        created_by = int(input("请输入创建者ID (默认1): ") or "1")
        delay = float(input("请输入请求间隔秒数 (默认1.0): ") or "1.0")
        
        if start_page < 1 or end_page < start_page:
            print("[错误] 页码范围无效")
            return
        
        data_type_name = "校招信息" if data_type == 'campus' else "实习信息"
        
        # 确认导入
        print(f"\n[配置] 导入配置:")
        print(f"   数据类型: {data_type_name}")
        print(f"   页码范围: {start_page} - {end_page}")
        print(f"   创建者ID: {created_by}")
        print(f"   请求间隔: {delay}秒")
        print(f"   预计处理: {end_page - start_page + 1} 页")
        
        confirm = input("\n确认开始导入吗？(y/N): ").strip().lower()
        if confirm != 'y':
            print("[取消] 取消导入")
            return
        
        # 开始导入
        asyncio.run(batch_import_jobs(start_page, end_page, created_by, delay, data_type))
        
    except KeyboardInterrupt:
        print("\n[中断] 用户中断导入")
    except ValueError as e:
        print(f"[错误] 输入错误: {e}")
    except Exception as e:
        print(f"[错误] 导入失败: {e}")


if __name__ == "__main__":
    main()
