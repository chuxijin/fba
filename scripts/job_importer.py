#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轻量可视化导入工具：在浏览器中粘贴 HTML → 预览 → 确认入库。

运行方式（项目根目录）：
    python scripts/job_importer.py

打开浏览器访问：http://127.0.0.1:8787/
"""
from __future__ import annotations

import os
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# 导入项目依赖
from backend.app.job.schema.job_posting import CreateJobPosting
from backend.app.job.model.job_posting import JobPosting
from backend.app.job.crud.crud_job_posting import job_posting_dao
from backend.database.db import async_db_session


app = FastAPI(title="Job HTML Importer", version="0.1.0")


def parse_job_postings_from_html(html: str) -> list[CreateJobPosting]:
    """
    从 HTML 中解析招聘信息
    """
    results = []
    
    # 匹配表格行 <tr data-id="...">
    tr_pattern = r'<tr data-id="(\d+)".*?>(.*?)</tr>'
    tr_matches = re.findall(tr_pattern, html, re.DOTALL)
    
    for data_id, tr_content in tr_matches:
         # 初始化数据字典
         job_data = {
             "company_name": "",
             "company_type": "",
             "industry": "",
             "recruitment_type": "",
             "work_location": "",
             "recruitment_object": "",
             "position": "",
             "delivery_start": None,
             "delivery_end": None,
             "delivery_link": "",
             "recruitment_announcement": "",
             "referral_code": "",
             "remark": "",
             "salary_range": "",
             "is_exempt_from_written_test": False,
             "logo_url": ""
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
        industry_match = re.search(r'<td class="crt-col-company"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
        if industry_match:
            # 第三个td是行业
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
        
         # 提取截止日期
         deadline_match = re.search(r'<td class="crt-col-deadline"[^>]*>(.*?)</td>', tr_content, re.DOTALL)
         if deadline_match:
             deadline_text = re.sub(r'<[^>]+>', '', deadline_match.group(1)).strip()
             if deadline_text and deadline_text != "招满为止":
                 try:
                     # 尝试解析日期格式 YYYY-MM-DD
                     parsed_date = datetime.strptime(deadline_text, '%Y-%m-%d')
                     job_data["delivery_end"] = parsed_date.date()
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
         if not job_data["company_type"]:
             job_data["company_type"] = "其他"
         if not job_data["industry"]:
             job_data["industry"] = "其他"
         if not job_data["recruitment_type"]:
             job_data["recruitment_type"] = "校园招聘"
         if not job_data["work_location"]:
             job_data["work_location"] = "未知"
         if not job_data["recruitment_object"]:
             job_data["recruitment_object"] = "应届生"
        
        try:
            job_posting = CreateJobPosting(**job_data)
            results.append(job_posting)
        except Exception as e:
            print(f"创建 CreateJobPosting 失败: {e}, 数据: {job_data}")
            continue
    
    return results


async def import_from_html(html: str, created_by: int) -> int:
    """
    从 HTML 解析并导入到数据库
    """
    job_postings = parse_job_postings_from_html(html)
    count = 0
    
    async with async_db_session() as db:
        for job_posting in job_postings:
            try:
                await job_posting_dao.create(db, job_posting, created_by)
                count += 1
            except Exception as e:
                print(f"入库失败: {e}")
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
      const heads = ['公司','类型','行业','招聘类型','工作地点','招聘对象','岗位','截止','投递链接','公告'];
      const cols = ['company_name','company_type','industry','recruitment_type','work_location','recruitment_object','position','delivery_end','delivery_link','recruitment_announcement'];
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
    <h2>招聘信息导入工具</h2>
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
        count = await import_from_html(html=html, created_by=created_by)
        return JSONResponse(content={"code": 200, "msg": f"入库成功：{count} 条", "data": None})
    except Exception as e:
        return JSONResponse(content={"code": 500, "msg": f"入库失败: {e}", "data": None})


if __name__ == "__main__":
    # 默认 127.0.0.1:8787
    uvicorn.run(app, host="127.0.0.1", port=8787, log_level="info")


