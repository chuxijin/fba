import os
import re
import json
from pathlib import Path
from typing import List
import httpx
import logging
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.path_conf import UPLOAD_DIR
from backend.common.exception import errors

log = logging.getLogger(__name__)

class ParseService:
    @staticmethod
    async def parse_pdf_to_markdown(file_path: Path, images_dir_name: str, request_base_url: str = "") -> str:
        """
        纯 API 方式调用 LlamaParse（避免 Pydantic v1 与 v2 冲突），提取内容的 Markdown 和图片
        """
        if not images_dir_name:
            raise ValueError("必须提供 images_dir_name 参数")
            
        # 图片保存的相对子目录: upload/parsed_images/传的参数/
        images_dir = UPLOAD_DIR / "parsed_images" / images_dir_name
        images_dir.mkdir(parents=True, exist_ok=True)
        
        api_key = os.environ.get("LLAMA_CLOUD_API_KEY")
        if not api_key:
            raise ValueError("环境变量 LLAMA_CLOUD_API_KEY 未配置，无法调用 LlamaParse 服务")

        log.info(f"开始使用纯 HTTP API 上传并解析 PDF: {file_path}")

        # LlamaParse V2 标准两阶段流程地址
        files_url = "https://api.cloud.llamaindex.ai/api/v1/beta/files"
        parse_url = "https://api.cloud.llamaindex.ai/api/v2/parse"
        headers = {"Authorization": f"Bearer {api_key}", "accept": "application/json"}
        
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                # --- 第一步：上传文件获取 file_id ---
                file_bytes = await asyncio.to_thread(file_path.read_bytes)
                files = {"file": (file_path.name, file_bytes, "application/pdf")}
                # purpose=parse 是文档建议的用途
                upload_res = await client.post(files_url, headers=headers, files=files, data={"purpose": "parse"})
                upload_res.raise_for_status()
                file_id = upload_res.json()["id"]
                log.info(f"文件上传成功，FileID: {file_id}")

                # --- 第二步：提交解析请求获取 job_id ---
                parse_payload = {
                    "file_id": file_id,
                    "tier": "agentic",
                    "version": "latest",
                    "agentic_options": {
                        "custom_prompt": "你是一个专业的公考题目提取助手。请在解析文档时，确保所有公式、题目描述、选项内容都完整保留。遇到表格时，无须识别直接改成图片。"
                    },
                    "output_options": {
                        "images_to_save": ["embedded", "layout"],
                        "markdown": {
                            "annotate_links": True,
                            "inline_images": True,
                            "tables": {
                                "output_tables_as_markdown": False
                            }
                        }
                    },
                    "processing_options": {
                        "cost_optimizer": {"enable": True},
                        "ocr_parameters": {
                            "languages": ["ch_sim"]
                        }
                    }
                }
                
                job_res = await client.post(parse_url, headers=headers, json=parse_payload)
                if job_res.status_code == 422:
                    log.error(f"LlamaParse 提交解析失败 (422): {job_res.text}")
                job_res.raise_for_status()
                job_id = job_res.json()["id"]

                log.info(f"PDF 已提交，正在云端进行解析，JobID: {job_id}")
                
                # 2. 轮询等待任务完成 (使用 LlamaParse V2 API 结构)
                md_content = ""
                for i in range(120): # 最长等待十分钟
                    await asyncio.sleep(5)
                    # 轮询时不要加 expand，避免由于带着大负载查询导致服务端状态被锁或卡缓存机制
                    status_res = await client.get(f"{parse_url}/{job_id}", headers=headers)
                    status_res.raise_for_status()
                    status_data = status_res.json()
                    
                    # V2 Status 响应: 状态嵌套在 job 对象中
                    status = status_data.get("job", {}).get("status")
                    
                    if status == "COMPLETED":
                        log.info(f"JobID: {job_id} 状态已 COMPLETED。开始拉取全内容和图片元数据...")
                        
                        # 解析彻底完成后，再通过 expand 取出巨大的 Markdown 文本和图片 URL 列表
                        # V2 的 REST API 常规模式为逗号分隔字符串，或者同名数组。我们用标准做法
                        params = {
                            "expand": "markdown,images_content_metadata,text"
                        }
                        full_res = await client.get(f"{parse_url}/{job_id}", headers=headers, params=params)
                        full_data = full_res.json()
                        
                        # 如果逗号格式支持不好引发空数据，则尝试数组模式（兜底）
                        if not full_data.get("markdown_full") and not full_data.get("markdown"):
                            params_list = [("expand", "markdown"), ("expand", "images_content_metadata"), ("expand", "text")]
                            full_res = await client.get(f"{parse_url}/{job_id}", headers=headers, params=params_list)
                            full_data = full_res.json()
                        
                        status_data = full_data  # 覆盖回 status_data 以便复用下游解析
                         
                        # 1. 确定 Markdown 内容
                        md_content = status_data.get("markdown_full")
                        if not md_content:
                            log.warning(f"JobID: {job_id} 未找到 markdown_full，尝试从分页 markdown 拼接...")
                            md_pages = status_data.get("markdown", {}).get("pages", [])
                            if md_pages:
                                md_content = "\n\n".join([p.get("markdown", "") for p in md_pages])
                        
                        if not md_content:
                            log.error(f"JobID: {job_id} 解析已完成但未获取到任何 Markdown 内容")
                            raise Exception("云端已完成解析，但未返回 Markdown 内容（markdown_full 或 pages 均为空）。")

                        # 2. 处理图片 (无论从哪拿的内容，元数据都在 images_content_metadata)
                        images_metadata = status_data.get("images_content_metadata", {}).get("images", [])
                        if images_metadata:
                            log.info(f"探测到 {len(images_metadata)} 张图片，开始下载...")
                            for img_info in images_metadata:
                                img_name = img_info.get("filename")
                                presigned_url = img_info.get("presigned_url")
                                
                                if img_name and presigned_url:
                                    try:
                                        img_res = await client.get(presigned_url)
                                        if img_res.status_code == 200:
                                            img_path = images_dir / img_name
                                            await asyncio.to_thread(img_path.write_bytes, img_res.content)
                                    except Exception as e:
                                        log.warning(f"下载图片 {img_name} 失败: {e}")
                        else:
                            log.info("该文档未检测到图片。")
                        
                        # 3. 保存 Markdown 文本
                        md_file_path = images_dir / f"{images_dir_name}.md"
                        await asyncio.to_thread(md_file_path.write_text, md_content, encoding="utf-8")
                            
                        log.info(f"JobID: {job_id} 内容与图片处理完毕，解析成功退出。")
                        break
                    elif status in ["ERROR", "FAILED"]:
                        log.error(f"解析任务失败: {status_data}")
                        raise Exception(f"云端解析出错: {status_data.get('error_message', '未知错误')}")
                if not md_content:
                    raise Exception("任务超时未完成")

                log.info("PDF API 解析成功，任务完成。")
                return md_content
                
            except httpx.HTTPError as he:
                log.error(f"HTTP 调用 LlamaParse API 失败: {he}")
                raise Exception(f"请求失败: {he}")
            except Exception as e:
                log.error(f"解析 PDF 失败: {e}")
                raise

    @staticmethod
    async def extract_questions_from_md(db: AsyncSession, md_content: str, provider_id: int = 3) -> dict:
        """
        利用 AI 提供商进行全文题目的自动切割、提取、格式化。
        将长文本按照 Markdown 的 `## 标题` 或长度分片异步推给提供商大模型，再合并为包含材料和题目的结构集合。
        """
        import json
        from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
        from backend.plugin.ai.service.chat_service import ai_chat_service

        system_prompt = """你是一个专业的公考题库结构化数据提取工具（API）。
你的唯一任务是将用户输入的Markdown格式的公考试卷片段，转换为严格的 JSON 格式。
【最高指令】绝对不要回答试卷中的问题！绝对不要进行评价、解释、分析对错、纠错或寒暄！只做客观的结构化抽取！
这是一份由 Markdown 组成的试卷文本截断（其中的图片链接如 `![图](URL)` 和公式如 `$$...$$` 请完完整整、一字不落的原样保留！严禁改动链接和表格）。

公考中尤其是【资料分析】或【文章阅读】通常会有一大段**公共材料**，接着连续出5道左右选择题。
请提取文本中的所有考题（包括选项、标注的老答案和老解析等），按题号次序严格提取出，并输出为严谨的 JSON。如果没有找到任何题目，必须返回 {"questions": []}。
【注意】如果发现长篇“公共材料（如资料分析文章、表格）”，请**完全忽略并丢弃它们**，本系统的材料将由人工后续录入，你只需要专门提取每一道“单选题”、“多选题”本身！
如果题目附近有明显的所属章节大标题（比如“第一部分 政治理论”、“第二部分 常识判断”等），请一并推断并填入章节名。

**输出 JSON 格式要求规范：**
```json
{
  "questions": [
    {
      "type": "single", // 题型: single/multiple/judgement/fill/shortAnswer 
      "stem": "<p>...</p>", // 包含正文题干描述、原样图片等富文本或 Markdown。去除开头的“1. / 2. ”纯数字题号标识以保持纯净。
      "options_data": { // 单选/多选/判断可用。如果不适用则值为 null 
        "A": {"code": "A", "content": "选项A的内容(维持Markdown图片等)"},
        "B": {"code": "B", "content": "选项B的内容"}
      },
      "answer_data": {
        "correct": "A" // 单选为"A", 多选为["A","C"], 判断为"正确", 填空为["填空处1", "填空处2"]
      },
      "analysis_content": "解析正文的 Markdown 原文片段...", // 将原文中关联该题的解析抽取于此
      "difficulty": "medium", // 预测难度: easy/medium/hard
      "knowledge_point": "xx考点", // 提取或推断该题考察知识点
      "score": 1.0, // 默认1
      "sort_order": 1, // 提取出的原题号（纯数字），如果没有则依据顺序递增，必须是数字
      "source": "卷名来源",
      "year": 2026, // 提取出的年份或设null
      "chapter_name": "所属章节标题，比如 第一部分 政治理论（如果没有则填null）"
    }
  ]
}
      "type": "single", // 题型: single/multiple/judgement/fill/shortAnswer 
      "stem": "<p>...</p>", // 包含正文题干描述、原样图片等富文本或 Markdown。去除开头的“1. / 2. ”纯数字题号标识以保持纯净。
      "options_data": { // 单选/多选/判断可用。如果不适用则值为 null 
        "A": {"code": "A", "content": "选项A的内容(维持Markdown图片等)"},
        "B": {"code": "B", "content": "选项B的内容"}
      },
      "answer_data": {
        "correct": "A" // 单选为"A", 多选为["A","C"], 判断为"正确", 填空为["填空处1", "填空处2"]
      },
      "analysis_content": "解析正文的 Markdown 原文片段...", // 将原文中关联该题的解析抽取于此
      "difficulty": "medium", // 预测难度: easy/medium/hard
      "knowledge_point": "xx考点", // 提取或推断该题考察知识点
      "score": 1.0, // 默认1
      "sort_order": 1, // 提取出的原题号（纯数字），如果没有则依据顺序递增，必须是数字
      "source": "卷名来源",
      "year": 2026 // 提取出的年份或设null
    }
  ]
}
```
**千万注意**:
1. 仅仅输出合法且闭合的 JSON 数据对象，必须以 `{` 开始，以 `}` 结束。
2. 不要加任何类似于 ```json ``` 的代码块标记！绝对不要包含任何其它总结、提示性的人类寒暄（比如“这是整理好的内容”、“答案是有笔误的”等等）。
3. 即使你发现原文有逻辑错误或笔误，也不要去修复它，你要做的是原样抓取并JSON化！
"""

        # 新的分片逻辑：固定字数滑动窗口 + 上下文重叠
        # 每块尽量取 1000 字符，前后重叠 200 字符，以防止刚好把一道题或材料切断
        # 实际处理时，第一块：0~1000；第二块：800~1800；依此类推。
        chunk_size = 1000
        overlap = 200
        
        parsed_chunks = []
        md_len = len(md_content)
        
        if md_len == 0:
            return {"materials": [], "questions": []}
            
        start = 0
        chunk_index = 0
        while start < md_len:
            end = min(start + chunk_size, md_len)
            
            # 如果不是第一块，我们在文本开头加上提示语，防止 AI 误判被截断的开头
            prefix_context = "(接上文)...\n" if start > 0 else ""
            suffix_context = "\n...(未完待续)" if end < md_len else ""
            
            text_slice = md_content[start:end]
            final_text = f"{prefix_context}{text_slice}{suffix_context}"
            
            # 使用类似于旧版的结构保存，title 简单用分片索引代替
            parsed_chunks.append((f"分片_{chunk_index}", final_text))
            
            chunk_index += 1
            # 步长为 size - overlap
            start += (chunk_size - overlap)
            
        async def process_chunk(title, text, chunk_index):
            prompt_text = f"【当前{title}】：\n{text}\n\n注意：如果发现某道题或材料被开头/结尾截断了不完整，请**只提取完整的那些题目**，不要提取残缺的题目，残缺的题目会在下一个分片中被完整提取。"
            chat_param = AIChat(
                provider_id=provider_id,
                model_id="gpt-4o-2024-11-20", 
                messages=[
                    AIChatMessage(role="system", content=system_prompt),
                    AIChatMessage(role="user", content=prompt_text)
                ],
                temperature=0.1
            )
            
            try:
                ai_resp = await ai_chat_service.raw_chat(db=db, chat=chat_param, stream=True)
                resp_content = ai_resp.get('content', '')
                
                json_match = re.search(r'\{[\s\S]*\}', resp_content)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        # 为合并防冲，给临时 ID 加上切片索引后缀
                        chunk_suffix = f"_{chunk_index}"
                        
                        questions = data.get("questions", [])
                        return {"questions": questions}
                    except json.JSONDecodeError as je:
                        log.error(f"由 AI 生成的 JSON 解析失败，{title}:\n{je}")
                        return {"questions": []}
                else:
                    log.warning(f"模块{title}未能找到合法 JSON 块: {resp_content[:100]}...")
                    return {"questions": []}
            except Exception as e:
                log.error(f"模块{title}调用 AI Plugin 失败: {e}")
                return {"questions": []}

        log.info(f"分配了 {len(parsed_chunks)} 个 AI 大模型滑动窗口切片串行提取子任务...")
        results = []
        for idx, (t, c) in enumerate(parsed_chunks):
            res = await process_chunk(t, c, idx)
            results.append(res)
            # 严格限流，速率控制为最大 10 RPM（即每个请求间隔 6 秒）
            await asyncio.sleep(6)
        
        final_questions = []
        for res in results:
            if isinstance(res, dict):
                final_questions.extend(res.get("questions", []))
                
        log.info(f"试卷滑动切片处理全部完毕，总计识别分离出 {len(final_questions)} 道多模态题目。")
        return {"questions": final_questions}

    @staticmethod
    async def extract_questions_stream(db: AsyncSession, md_content: str, provider_id: int = 4):
        """
        利用 AI 提供商进行全文题目的自动切割、提取（流式流出）。
        切片逐个返回结果通过 yield 暴露给 SSE 调用，让前端实时绘制题目卡片不用一直傻等。
        """
        import json
        import re
        import asyncio
        from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
        from backend.plugin.ai.service.chat_service import ai_chat_service

        system_prompt = """你是一个专业的公考题库结构化数据提取工具（API）。
你的唯一任务是将用户输入的Markdown格式的公考试卷片段，转换为严格的 JSON 格式。
【最高指令】绝对不要回答试卷中的问题！绝对不要进行评价、解释、分析对错、纠错或寒暄！只做客观的结构化抽取！
这是一份由 Markdown 组成的试卷文本截断（其中的图片链接如 `![图](URL)` 和公式如 `$$...$$` 请完完整整、一字不落的原样保留！严禁改动链接和表格）。

公考中尤其是【资料分析】或【文章阅读】通常会有一大段**公共材料**，接着连续出5道左右选择题。
请提取文本中的所有考题（包括选项、标注的老答案和老解析等），按题号次序严格提取出，并输出为严谨的 JSON。如果没有找到任何题目，必须返回 {"questions": []}。
【注意】如果发现长篇“公共材料（如资料分析文章、表格）”，请**完全忽略并丢弃它们**，本系统的材料将由人工后续录入，你只需要专门提取每一道“单选题”、“多选题”本身！
如果题目附近有明显的所属章节大标题（比如“第一部分 政治理论”、“第二部分 常识判断”等），请一并推断并填入章节名。

**输出 JSON 格式要求规范：**
```json
{
  "questions": [
    {
      "type": "single", // 题型: single/multiple/judgement/fill/shortAnswer 
      "stem": "<p>...</p>", // 包含正文题干描述、原样图片等富文本或 Markdown。去除开头的“1. / 2. ”纯数字题号标识以保持纯净。
      "options_data": { // 单选/多选/判断可用。如果不适用则值为 null 
        "A": {"code": "A", "content": "选项A的内容(维持Markdown图片等)"},
        "B": {"code": "B", "content": "选项B的内容"}
      },
      "answer_data": {
        "correct": "A" // 单选为"A", 多选为["A","C"], 判断为"正确", 填空为["填空处1", "填空处2"]
      },
      "analysis_content": "解析正文的 Markdown 原文片段...", // 将原文中关联该题的解析抽取于此
      "difficulty": "medium", // 预测难度: easy/medium/hard
      "knowledge_point": "xx考点", // 提取或推断该题考察知识点
      "score": 1.0, // 默认1
      "sort_order": 1, // 提取出的原题号（纯数字），如果没有则依据顺序递增，必须是数字
      "source": "卷名来源",
      "year": 2026, // 提取出的年份或设null
      "chapter_name": "所属章节标题，比如 第一部分 政治理论（如果没有则填null）"
    }
  ]
}
```
**千万注意**:
1. 仅仅输出合法且闭合的 JSON 数据对象，必须以 `{` 开始，以 `}` 结束。
2. 不要加任何类似于 ```json ``` 的代码块标记！绝对不要包含任何其它总结、提示性的人类寒暄（比如“这是整理好的内容”、“答案是有笔误的”等等）。
3. 即使你发现原文有逻辑错误或笔误，也不要去修复它，你要做的是原样抓取并JSON化！
"""

        chunk_size = 1000
        overlap = 200
        parsed_chunks = []
        md_len = len(md_content)
        
        if md_len == 0:
            yield {"questions": []}
            return
            
        start = 0
        chunk_index = 0
        while start < md_len:
            end = min(start + chunk_size, md_len)
            prefix_context = "(接上文)...\n" if start > 0 else ""
            suffix_context = "\n...(未完待续)" if end < md_len else ""
            text_slice = md_content[start:end]
            final_text = f"{prefix_context}{text_slice}{suffix_context}"
            parsed_chunks.append((f"分片_{chunk_index}", final_text))
            chunk_index += 1
            start += (chunk_size - overlap)
            
        async def process_chunk(title, text, idx):
            prompt_text = f"【当前{title}】：\n{text}\n\n注意：如果发现某道题或材料被开头/结尾截断了不完整，请**只提取完整的那些题目**，不要提取残缺的题目，残缺的题目会在下一个分片中被完整提取。"
            chat_param = AIChat(
                provider_id=provider_id,
                model_id="gpt-4o-2024-11-20", 
                messages=[
                    AIChatMessage(role="system", content=system_prompt),
                    AIChatMessage(role="user", content=prompt_text)
                ],
                temperature=0.1
            )
            
            try:
                ai_resp = await ai_chat_service.raw_chat(db=db, chat=chat_param, stream=False)
                resp_content = ai_resp.get('content', '')
                
                json_match = re.search(r'\{[\s\S]*\}', resp_content)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        return {"questions": data.get("questions", [])}
                    except json.JSONDecodeError as je:
                        log.error(f"由 AI 生成的 JSON 解析失败，{title}:\n{je}")
                        return {"questions": []}
                else:
                    log.warning(f"模块{title}未能找到合法 JSON 块: {resp_content[:100]}...")
                    return {"questions": []}
            except Exception as e:
                log.error(f"模块{title}调用 AI Plugin 失败: {e}")
                return {"questions": []}

        log.info(f"开启流式分配 {len(parsed_chunks)} 个抽取子任务...")
        total_found = 0
        for idx, (t, c) in enumerate(parsed_chunks):
            res = await process_chunk(t, c, idx)
            # 通过 generator yield 单个分片的捕获题型
            if res and isinstance(res, dict) and res.get("questions"):
                total_found += len(res["questions"])
                yield res
            
            # 严格限流，速率控制为最大 10 RPM（即每个请求间隔 6 秒）
            if idx < len(parsed_chunks) - 1:
                await asyncio.sleep(6)
        
        log.info(f"流式分片抽取彻底结束，总获取题数: {total_found}")

parse_service = ParseService()
