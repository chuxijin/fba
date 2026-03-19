import json
import asyncio
import os
import re

# 模拟引用你的解析服务（因为如果在本地直接跑你的环境可能会缺少部分环境变量或者依赖，所以这里我们写一个独立的抽取脚本）
# 如果你需要用到完整的 chat_service 可以根据项目环境导入，目前这为了演示最快速和隔离，我直接写一段最小化的脚本帮你跑完保存。
try:
    from backend.app.question_bank.service.parse_service import parse_service
    from backend.common.database import db
    from backend.plugin.ai.service.chat_service import ai_chat_service
    from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
except ImportError:
    pass

async def extract_to_json():
    input_file = r"D:\100_Work\101_Program\Proj\fba\test_parsed.md"
    output_file = r"D:\100_Work\101_Program\Proj\fba\test.json"
    
    with open(input_file, 'r', encoding='utf-8') as f:
        # 只读取前 528 行的内容用于测试第一部分 20道题
        lines = f.readlines()
        
    start_line = max(0, 34 - 1)
    end_line = min(len(lines), 528)
    md_content = "".join(lines[start_line:end_line])

    # 抽取逻辑（复刻 parse_service 里的逻辑）
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
3. 即使你发现原文有逻辑错误或笔误，也不要去修复它，你要做的是原样抓取并JSON化！"""

    chunk_size = 1000
    overlap = 200
    parsed_chunks = []
    md_len = len(md_content)
    
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
        
    async def process_chunk(idx, title, text):
        prompt_text = f"【当前{title}】：\n{text}\n\n注意：如果发现某道题或材料被开头/结尾截断了不完整，请**只提取完整的那些题目**，不要提取残缺的题目，残缺的题目会在下一个分片中被完整提取。"
        chat_param = AIChat(
            provider_id="openai", # 使用配置中默认的 provider
            model_id="gpt-4o-2024-11-20", 
            messages=[
                AIChatMessage(role="system", content=system_prompt),
                AIChatMessage(role="user", content=prompt_text)
            ],
            temperature=0.1
        )
        try:
            print(f"正在请求 {title} ...")
            ai_resp = await ai_chat_service.raw_chat(db=None, chat=chat_param, stream=True)
            resp_content = ai_resp.get('content', '')
            json_match = re.search(r'\{[\s\S]*\}', resp_content)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return {"questions": data.get("questions", [])}
                except json.JSONDecodeError as je:
                    print(f"JSON 解析失败 {title}: {je}")
                    return {"questions": []}
            else:
                return {"questions": []}
        except Exception as e:
            print(f"请求失败 {title}: {e}")
            return {"questions": []}

    print(f"共切分出 {len(parsed_chunks)} 个数据块分片，正在开始处理...")
    final_questions = []
    
    for idx, (t, c) in enumerate(parsed_chunks):
        res = await process_chunk(idx, t, c)
        if isinstance(res, dict):
            final_questions.extend(res.get("questions", []))
        # Rate limit
        await asyncio.sleep(2)
        
    print(f"处理完成！成功解析 {len(final_questions)} 道题，正在写入 {output_file}...")
    
    # 按照题目 sort_order 去重并重新排序，因为滑动窗口重叠可能会导致某些题目在两个分片中被提取
    unique_questions = {}
    for q in final_questions:
        o = q.get('sort_order')
        if o not in unique_questions:
            unique_questions[o] = q
    
    sorted_questions = [unique_questions[k] for k in sorted(unique_questions.keys())]

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"questions": sorted_questions}, f, ensure_ascii=False, indent=2)
        
    print("写入完毕，大功告成！")

if __name__ == "__main__":
    asyncio.run(extract_to_json())
