#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版招聘信息导入工具：避免复杂依赖，直接使用数据库连接
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, date
from typing import Any
import sys
import os
from pathlib import Path

# 设置控制台编码为UTF-8，避免Windows编码问题
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# 导入项目依赖
try:
    # 直接导入数据库相关模块，避免复杂依赖
    from backend.database.db import async_db_session, async_engine
    from backend.app.job.model.job_posting import JobPosting
    from sqlalchemy import text
    HAS_DB_ACCESS = True
except ImportError as e:
    print(f"数据库导入失败: {e}")
    HAS_DB_ACCESS = False


class JobPostingData(BaseModel):
    """招聘信息数据模型"""
    id: int | None = None  # 使用HTML中的data-id
    company_name: str
    company_type: str | None = None
    industry: str | None = None
    recruitment_type: str | None = None
    work_location: str | None = None
    recruitment_object: str | None = None
    position: str
    delivery_start: date | None = None
    delivery_end: date | None = None
    delivery_link: str | None = None
    recruitment_announcement: str | None = None
    referral_code: str | None = None
    remark: str | None = None
    salary_range: str | None = None
    is_exempt_from_written_test: bool | None = False
    logo_url: str | None = None


app = FastAPI(title="Simple Job HTML Importer", version="0.1.0")


def parse_job_postings_from_html(html: str) -> list[JobPostingData]:
    """从 HTML 中解析招聘信息"""
    results = []
    
    # 匹配表格行 <tr data-id="...">
    tr_pattern = r'<tr data-id="(\d+)".*?>(.*?)</tr>'
    tr_matches = re.findall(tr_pattern, html, re.DOTALL)
    
    for data_id, tr_content in tr_matches:
        # 初始化数据字典，使用data-id作为主键
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
        company_match = re.search(r'<td class="crt-col-company"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
        if company_match:
            job_data["company_name"] = re.sub(r'<[^>]+>', '', company_match.group(1)).strip()
        
        # 提取公司类型
        type_match = re.search(r'<td class="crt-col-type"[^>]*>.*?<span[^>]*crt-type-([^"]*)"[^>]*>([^<]*)</span>', tr_content, re.DOTALL)
        if type_match:
            job_data["company_type"] = type_match.group(2).strip()
        
        # 提取行业
        td_all = re.findall(r'<td[^>]*>(.*?)</td>', tr_content, re.DOTALL)
        if len(td_all) >= 3:
            job_data["industry"] = re.sub(r'<[^>]+>', '', td_all[2]).strip()
        
        # 提取招聘类型
        recruitment_type_match = re.search(r'<td class="crt-col-recruitment-type"[^>]*>.*?<span[^>]*>([^<]*)</span>', tr_content, re.DOTALL)
        if recruitment_type_match:
            job_data["recruitment_type"] = recruitment_type_match.group(1).strip()
        
        # 提取工作地点
        location_match = re.search(r'<td class="crt-col-location"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
        if location_match:
            job_data["work_location"] = re.sub(r'<[^>]+>', '', location_match.group(1)).strip()
        
        # 提取招聘对象
        target_match = re.search(r'<td class="crt-col-target"[^>]*>.*?<span[^>]*>([^<]*)</span>', tr_content, re.DOTALL)
        if target_match:
            job_data["recruitment_object"] = target_match.group(1).strip()
        
        # 提取岗位信息
        position_match = re.search(r'<td class="crt-col-position"[^>]*>.*?<span class="crt-position-tag"[^>]*>([^<]*)</span>', tr_content, re.DOTALL)
        if position_match:
            job_data["position"] = position_match.group(1).strip()
        
        # 提取更新时间（作为开始时间）
        update_time_match = re.search(r'<td class="crt-col-update-time"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
        if update_time_match:
            update_time_text = re.sub(r'<[^>]+>', '', update_time_match.group(1)).strip()
            if update_time_text:
                try:
                    # 尝试解析日期格式 YYYY-MM-DD，保存为日期对象
                    parsed_date = datetime.strptime(update_time_text, '%Y-%m-%d').date()
                    job_data["delivery_start"] = parsed_date
                except:
                    pass
        
        # 提取截止日期
        deadline_match = re.search(r'<td class="crt-col-deadline"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
        if deadline_match:
            deadline_text = re.sub(r'<[^>]+>', '', deadline_match.group(1)).strip()
            if deadline_text and deadline_text != "招满为止":
                try:
                    # 尝试解析日期格式 YYYY-MM-DD，保存为日期对象
                    parsed_date = datetime.strptime(deadline_text, '%Y-%m-%d').date()
                    job_data["delivery_end"] = parsed_date
                except:
                    pass
        
        # 提取投递链接
        link_match = re.search(r'<td class="crt-col-links"[^>]*>.*?<a href="([^"]+)"', tr_content, re.DOTALL)
        if link_match:
            job_data["delivery_link"] = link_match.group(1).strip()
        
        # 提取公告链接
        notice_match = re.search(r'<td class="crt-col-notice"[^>]*>.*?<a href="([^"]+)"', tr_content, re.DOTALL)
        if notice_match:
            job_data["recruitment_announcement"] = notice_match.group(1).strip()
        
        # 确保必填字段有值
        if not job_data["company_name"]:
            continue
        if not job_data["position"]:
            job_data["position"] = "未知岗位"
        
        try:
            job_posting = JobPostingData(**job_data)
            results.append(job_posting)
        except Exception as e:
            print(f"创建 JobPostingData 失败: {e}, 数据: {job_data}")
            continue
    
    return results


async def import_to_database(job_postings: list[JobPostingData], created_by: int) -> int:
    """将解析的数据导入数据库"""
    if not HAS_DB_ACCESS:
        print(f"模拟导入 {len(job_postings)} 条记录，创建者: {created_by}")
        for i, job in enumerate(job_postings):
            print(f"  {i+1}. {job.company_name} - {job.position}")
        return len(job_postings)
    
    # 实际数据库导入
    count = 0
    async with async_db_session() as db:
        for job_posting in job_postings:
            try:
                # 检查是否已存在相同ID的记录
                if job_posting.id:
                    existing = await db.get(JobPosting, job_posting.id)
                    if existing:
                        print(f"  [跳过] ID {job_posting.id} 已存在: {job_posting.company_name}")
                        continue
                
                # 创建数据库模型实例（不包含ID，因为id字段设置了init=False）
                new_job = JobPosting(
                    company_name=job_posting.company_name,
                    company_type=job_posting.company_type,
                    industry=job_posting.industry,
                    recruitment_type=job_posting.recruitment_type,
                    work_location=job_posting.work_location,
                    recruitment_object=job_posting.recruitment_object,
                    position=job_posting.position,
                    delivery_start=job_posting.delivery_start,
                    delivery_end=job_posting.delivery_end,
                    delivery_link=job_posting.delivery_link,
                    recruitment_announcement=job_posting.recruitment_announcement,
                    referral_code=job_posting.referral_code,
                    remark=job_posting.remark,
                    salary_range=job_posting.salary_range,
                    is_exempt_from_written_test=job_posting.is_exempt_from_written_test or False,
                    logo_url=job_posting.logo_url,
                    created_by=created_by
                )
                
                # 如果有ID，则手动设置ID（因为id字段设置了init=False）
                if job_posting.id:
                    new_job.id = job_posting.id
                db.add(new_job)
                await db.flush()  # 获取ID
                count += 1
                display_id = f"ID {job_posting.id}" if job_posting.id else "自动ID"
                print(f"  [成功] {count}. {display_id} - {job_posting.company_name}")
            except Exception as e:
                print(f"  [失败] 入库失败: {job_posting.company_name} - {e}")
                continue
        await db.commit()
    
    return count


INDEX_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>招聘信息导入工具</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial; margin: 16px; }
    .row { display:flex; gap:12px; align-items:center; margin: 8px 0; }
    textarea { width:100%; min-height: 260px; }
    button { padding: 6px 12px; cursor: pointer; }
    table { border-collapse: collapse; width: 100%; margin-top: 12px; font-size: 14px; }
    th, td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }
    th { background: #fafafa; }
    .muted { color:#777; font-size: 12px; }
  </style>
  <script>
    async function parseHtml() {
      const html = document.getElementById('html').value;
      if (!html.trim()) { alert('请粘贴 HTML'); return; }
      const res = await fetch('/parse', { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ html }) });
      const data = await res.json();
      if (data.code !== 200) { alert(data.msg || '解析失败'); return; }
      const items = data.data || [];
      renderPreview(items);
      window.__preview_html__ = html; // 缓存，供入库使用
    }

    function renderPreview(items) {
      const wrap = document.getElementById('preview');
      if (!items.length) { wrap.innerHTML = '<div class="muted">未解析到任何记录</div>'; return; }
      const heads = ['ID','公司','类型','行业','招聘类型','工作地点','招聘对象','岗位','开始','截止','投递链接','公告'];
      const cols = ['id','company_name','company_type','industry','recruitment_type','work_location','recruitment_object','position','delivery_start','delivery_end','delivery_link','recruitment_announcement'];
      let html = '<table><thead><tr>' + heads.map(h=>`<th>${h}</th>`).join('') + '</tr></thead><tbody>';
      for (const it of items) {
        html += '<tr>' + cols.map(k=>`<td>${it[k] ?? ''}</td>`).join('') + '</tr>';
      }
      html += '</tbody></table>';
      wrap.innerHTML = html;
      document.getElementById('count').innerText = `解析到 ${items.length} 条`;
    }

    async function commitHtml() {
      const html = window.__preview_html__ || document.getElementById('html').value;
      if (!html.trim()) { alert('请先解析或粘贴 HTML'); return; }
      const created_by = document.getElementById('created_by').value.trim();
      if (!created_by) { alert('请输入创建者用户ID'); return; }
      const res = await fetch('/commit', { method:'POST', headers:{ 'Content-Type':'application/json' }, body: JSON.stringify({ html, created_by: Number(created_by) })});
      const data = await res.json();
      alert(data.msg || (data.code === 200 ? '入库成功' : '入库失败'));
    }
  </script>
  </head>
  <body>
    <h2>招聘信息导入工具（简化版）</h2>
    <div class="row">
      <label for="created_by">创建者用户ID:</label>
      <input id="created_by" type="number" placeholder="如：1" style="width:120px;padding:4px;" />
      <span class="muted">将写入每条记录的 created_by 字段</span>
    </div>
    <div class="row"><textarea id="html" placeholder="在此粘贴包含表格的完整 HTML 源码"></textarea></div>
    <div class="row">
      <button onclick="parseHtml()">解析预览</button>
      <button onclick="commitHtml()">确认入库</button>
      <span id="count" class="muted"></span>
    </div>
    <div id="preview"></div>
  </body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> Any:
    return HTMLResponse(INDEX_HTML)


@app.post("/parse")
async def parse(payload: dict[str, Any]) -> JSONResponse:
    html = payload.get("html", "")
    try:
        items = parse_job_postings_from_html(html)
        response_data = {
            "code": 200,
            "msg": "ok",
            "data": [item.model_dump(mode="json") for item in items],
        }
        return JSONResponse(content=response_data)
    except Exception as e:
        return JSONResponse(content={"code": 500, "msg": f"解析失败: {e}", "data": None})


@app.post("/commit")
async def commit(payload: dict[str, Any]) -> JSONResponse:
    html = payload.get("html", "")
    created_by = payload.get("created_by")
    if not isinstance(created_by, int):
        return JSONResponse(content={"code": 400, "msg": "created_by 必须为整型", "data": None})
    try:
        job_postings = parse_job_postings_from_html(html)
        count = await import_to_database(job_postings, created_by)
        if HAS_DB_ACCESS:
            return JSONResponse(content={"code": 200, "msg": f"入库成功：{count} 条", "data": None})
        else:
            return JSONResponse(content={"code": 200, "msg": f"解析成功：{count} 条（需要先执行数据库迁移）", "data": None})
    except Exception as e:
        return JSONResponse(content={"code": 500, "msg": f"入库失败: {e}", "data": None})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8787, log_level="info")
