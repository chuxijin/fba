#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_copilot import copilot_session_dao, copilot_message_dao
from backend.app.jia.model.copilot import JiaCopilotMessage
from backend.app.jia.schema.copilot import CreateSessionParam, ChatRequest, ChatResponse, AnalyzeItemRequest, AnalyzeItemResponse, RecognizeFormulaRequest, RecognizeFormulaResponse, AnalyzeFoodRequest, AnalyzeFoodResponse
from backend.app.jia.service.exercise_service import exercise_service
from backend.app.jia.service.food_service import food_service
from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
from backend.plugin.ai.service.chat_service import ai_chat_service



TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_exercises",
            "description": "通过关键词搜索动作库 (Search exercise library)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，例如 '胸肌', '俯卧撑'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_foods",
            "description": "通过关键词搜索食物库 (Search food database)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "食物名称，如 '苹果', '鸡胸肉'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_items",
            "description": "通过关键词搜索物品 (Search items by name or category)",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "物品名称关键词"
                    },
                    "category": {
                        "type": "string",
                        "description": "物品分类"
                    },
                     "location": {
                        "type": "string",
                        "description": "存放位置"
                    },
                    "status": {
                        "type": "string",
                        "description": "状态 (e.g. '充足', '缺失', '即将过期')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_similar_items",
            "description": "语义搜索物品 (查找相似功能、重复、或模糊描述的物品)",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索描述，如 '旅行必备', '红色衣服', '清洁工具'"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    }
]

class CopilotService:
    
    async def _execute_tool(self, db: AsyncSession, user_id: int, tool_call: dict) -> str:
        """执行工具调用并返回结果 (JSON String)"""
        try:
            func_name = tool_call['function']['name']
            args_str = tool_call['function']['arguments']
            args = json.loads(args_str)
            
            if func_name == 'search_exercises':
                query = args.get('query')
                limit = args.get('limit', 5)
                # Call existing service
                exercises = await exercise_service.search_similar(db, query, limit=limit)
                # Format specific JSON result
                result = [
                    {"id": e.id, "name": e.name_zh, "category": e.category, "difficulty": e.difficulty} 
                    for e in exercises
                ]
                return json.dumps(result, ensure_ascii=False)
            
            if func_name == 'search_foods':
                query = args.get('query')
                limit = args.get('limit', 5)
                foods = await food_service.search_similar(db=db, query=query, limit=limit)
                result = [
                    {"id": f.id, "name": f.name, "energy": float(f.energy or 0), "category": f.category_id} # Simplified
                    for f in foods
                ]
                return json.dumps(result, ensure_ascii=False)

            if func_name == 'search_items':
                from backend.app.jia.service.item_service import item_service
                name = args.get('name')
                category = args.get('category')
                location = args.get('location')
                status = args.get('status')
                
                # Get items using service
                data = await item_service.get_list(
                    db=db, 
                    user_id=user_id, # Now we have user_id
                    name=name, 
                    category=category, 
                    location=location,
                    status=status
                )
                items = data.get('items', [])
                
                # Format result
                result = [
                    {
                        "id": i.id, 
                        "name": i.name, 
                        "category": i.category, 
                        "location": i.location,
                        "quantity": i.quantity,
                        "status": i.status,
                        "description": i.description
                    } 
                    for i in items
                ]
                return json.dumps(result, ensure_ascii=False) 

 

            if func_name == 'search_similar_items':
                from backend.app.jia.service.item_service import item_service
                query = args.get('query')
                limit = args.get('limit', 10)
                
                items = await item_service.search_similar(db=db, query_text=query, user_id=user_id, limit=limit)
                
                result = [
                    {
                        "id": i.id, 
                        "name": i.name, 
                        "category": i.category, 
                        "location": i.location,
                        "status": i.status,
                        "description": i.description,
                        "score": "similiar" # Vector search doesn't return score easily here, just mark as similar
                    } 
                    for i in items
                ]
                return json.dumps(result, ensure_ascii=False)

            return json.dumps({"error": f"Tool '{func_name}' not found"})
            
        except Exception as e:
            return json.dumps({"error": f"Tool execution failed: {str(e)}"})

    async def chat(self, db: AsyncSession, user_id: int, req: ChatRequest) -> ChatResponse:
        """
        Copilot Core Logic with Tool Execution Loop
        """
        # 0. Get User Settings
        from backend.app.jia.service.user_setting_service import user_setting_service
        user_settings = await user_setting_service.get_my_settings(db=db, user_id=user_id)
        
        # Apply User Settings
        current_provider_id = user_settings.copilot_provider or 4
        if not req.model and user_settings.copilot_model:
            req.model = user_settings.copilot_model

        # 1. Get or Create Session
        session_id = req.session_id
        current_session = None
        
        if session_id:
             current_session = await copilot_session_dao.get(db, session_id)
        
        if not current_session:
            title = (req.query[:20] if req.query else "New Chat") 
            # Use requested assistant_type or default to 'home'
            ass_type = req.assistant_type or "home"
            
            new_session = await copilot_session_dao.create(
                db, CreateSessionParam(title=title, model=req.model, assistant_type=ass_type), user_id
            )
            if not new_session.id:
                await db.flush()
                await db.refresh(new_session)
            session_id = new_session.id
            current_session = new_session
            
        # Determine System Prompt & Tools based on Assistant Type
        assistant_type = current_session.assistant_type or "home"
        
        system_prompt = "You are a helpful assistant."
        enabled_tools = []
        
        if assistant_type == "food":
            system_prompt = """
            你是一位“营养美食专家”。
            你的专长是分析食物热量、营养成分，并给出饮食建议。
            请积极使用 'search_foods' 工具来查找准确的食物数据。
            回答请专业、亲切，关注用户的健康。
            """
            enabled_tools = [t for t in TOOLS if t['function']['name'] == 'search_foods']
            
        elif assistant_type == "exercise":
            system_prompt = """
            你是一位“健身运动专家”。
            你的专长是推荐健身动作、制定训练计划。
            请积极使用 'search_exercises' 工具来查找动作库。
            回答请充满活力，鼓励用户坚持锻炼。
            """
            enabled_tools = [t for t in TOOLS if t['function']['name'] == 'search_exercises']
            
        elif assistant_type == "item":
            system_prompt = """
            你是一位“物件规整大师”。
            你的核心能力是利用**语义向量搜索**来感知用户物品。
            
            **核心原则**:
            1. **优先使用 'search_similar_items'**: 除非用户明确要求精确过滤（如“列出所有过期物品”），否则查询物品时**必须**优先使用此工具。它均能处理模糊描述、功能查找、场景匹配。
            2. **主动性**: 不仅回答“在哪里”，更要基于物品关联性和场景给出建议。
            
            **场景应对指南**:
            - **智能查找**: "我的护照/蓝色衣服/切水果的工具在哪?" -> `search_similar_items(query='...')`
                - 即使原本名字不完全匹配，向量搜索也能找到（如搜“切水果”找到“水果刀”）。
            - **冗余/断舍离检查**: "帮我看看哪些东西重复了/可以扔了?" 
                - 策略: 分批次搜索常见易囤积品类（如“衣服”, “数据线”, “厨具”）。
                - 分析搜索结果，指出功能高度重合的物品（如“你有5根Type-C线”）。
            - **场景化出行建议**: "我要去云南/露营/出差"
                - 策略: 步骤1-分析目的地/活动所需物品（如云南需要防晒、外套）；步骤2-调用 `search_similar_items` 搜索这些关键词；步骤3-列出用户已有物品，提醒缺失物品。
            - **购物防重**: "我想买个洗地机"
                - 策略: 先搜 `search_similar_items('洗地机 清洁工具')`，如果发现用户已有类似功能的（如“吸尘器”、“拖把”），则提醒用户可能重复。
            - **收纳/位置管理**: "这个放在哪里好?"
                - 策略: 搜类似物品的位置，建议放在一起。
            
            请展现出你作为“大师”的智能，活用语义理解能力。
            """
            enabled_tools = [t for t in TOOLS if t['function']['name'] in ['search_items', 'search_similar_items']]
            
        else: # home or others
            system_prompt = """
            你是一位“智能家居助手” (Jia Copilot)。
            你是用户家庭生活的全能帮手。
            你可以协助管理家庭设备、查询生活信息（如食物、运动等）。
            如果用户问到食物，请查 food 库；如果问到运动，请查 exercise 库。
            """
            enabled_tools = TOOLS # Generalist uses all tools
        
        # 2. Save User Message
        user_content = req.query or ""
        
        # [Fix] Provider 4 (HappyAPI / gpt-4o) fails with URL attachments.
        # Solution: Move URL attachments to text content, keep Base64 attachments.
        valid_attachments = []
        if req.attachments:
            for att in req.attachments:
                if att.url and (att.url.startswith('http://') or att.url.startswith('https://')):
                    # Append URL to text content
                    user_content += f"\n{att.url}"
                else:
                    # Keep Base64 or other types
                    valid_attachments.append(att.model_dump())
        
        attachment_list = valid_attachments if valid_attachments else None
        
        user_msg = JiaCopilotMessage(
            session_id=session_id, 
            role="user", 
            content=user_content,
            attachments=attachment_list
        )
        db.add(user_msg)
        await db.commit()
        await db.refresh(user_msg)
        
        # 3. Build Context & History (Desc -> Asc)
        history = await copilot_message_dao.get_history(db, session_id, limit=req.context_count or 10)
        raw_history = list(history)
        raw_history.reverse()
        
        current_messages = []
        current_messages.append(AIChatMessage(role="system", content=system_prompt))
        
        for msg in raw_history:
            # Handle Content (Text or Multimodal)
            content_part = msg.content
            if msg.attachments:
                parts = []
                if msg.content: parts.append({"type": "text", "text": msg.content})
                for att in msg.attachments:
                    if att['type'] == 'image':
                        # Check compatibility again if needed, but DB should store valid ones
                        parts.append({"type": "image_url", "image_url": {"url": att['url']}})
                content_part = parts
            
            # 关键: 如果是 Tool Call 消息，必须包含 tool_calls 字段
            # 如果是 Tool Result 消息，必须包含 tool_call_id
            current_messages.append(AIChatMessage(
                role=msg.role,
                content=content_part,
                tool_calls=msg.tool_calls,
                tool_call_id=msg.tool_call_id,
                name=None 
            ))
            
        # 4. Multi-turn Loop (AI -> Tool -> AI ...)
        CHAT_PROVIDER_ID = current_provider_id
        final_text = ""
        final_meta = {}
        
        for turn_idx in range(5): # Max 5 turns to prevent infinite loops
            # Call AI
            chat_param = AIChat(
                provider_id=CHAT_PROVIDER_ID,
                model_id=req.model or 'gpt-5.1',
                messages=current_messages,
                tools=enabled_tools, # Enable Tools
                temperature=0.7,
                # max_tokens=2000 # Removed as requested
            )
            
            try:
                ai_resp = await ai_chat_service.raw_chat(db=db, chat=chat_param)
            except Exception as e:
                import traceback
                traceback.print_exc()
                return ChatResponse(session_id=session_id, text=f"Error: {str(e)}")
            
            resp_content = ai_resp.get('content')
            resp_tool_calls = ai_resp.get('tool_calls')
            
            # Save Assistant/ToolCall Message to DB
            ai_msg_role = "assistant"
            ai_db_msg = JiaCopilotMessage(
                session_id=session_id,
                role=ai_msg_role,
                content=resp_content,
                tool_calls=resp_tool_calls
            )
            db.add(ai_db_msg)
            await db.commit()
            await db.refresh(ai_db_msg)
            
            # Append local history
            current_messages.append(AIChatMessage(
                role=ai_msg_role,
                content=resp_content,
                tool_calls=resp_tool_calls
            ))
            
            # Check for Tool Calls
            if resp_tool_calls:
                # Execute Tools (Sequential for now)
                for tc in resp_tool_calls:
                    tool_result_str = await self._execute_tool(db, user_id, tc)
                    
                    # Log result for debug
                    # print(f"Tool {tc['function']['name']} result: {tool_result_str}")
                    
                    # Save Tool Result to DB
                    tool_db_msg = JiaCopilotMessage(
                        session_id=session_id,
                        role="tool",
                        content=tool_result_str,
                        tool_call_id=tc['id']
                    )
                    db.add(tool_db_msg)
                    
                    # Append history
                    current_messages.append(AIChatMessage(
                        role="tool",
                        content=tool_result_str,
                        tool_call_id=tc['id']
                    ))
                    
                    # Set meta if relevant (for frontend usage)
                    if tc['function']['name'] == 'search_exercises':
                        try:
                            ex_data = json.loads(tool_result_str)
                            if ex_data and isinstance(ex_data, list):
                                final_meta['type'] = 'workout_suggestion'
                                final_meta['exercises'] = ex_data
                        except:
                            pass

                await db.commit()
                # Continue loop -> next iteration will send tool results to AI
            else:
                # No tool calls -> Final Answer
                final_text = resp_content
                break
        
        # Save final meta (async check: update the last AI message with meta?)
        # Or just return it. The frontend uses the meta from response.
        # Ideally, we should update the last message in DB with meta.
        if final_meta and ai_db_msg: # ai_db_msg is the last one
             # Note: ai_db_msg might be from previous turn if we broke loop.
             # Actually, if we break, ai_db_msg IS the last message.
             # But we need to update it.
             ai_db_msg.meta = final_meta
             db.add(ai_db_msg) # re-add to session to ensure update?
             await db.commit()
             
        # Return Final Response
        return ChatResponse(
            session_id=session_id,
            text=final_text or "",
            meta=final_meta,
            tool_calls=None, # We executed them
            message_id=ai_db_msg.id if 'ai_db_msg' in locals() else None
        )

    async def analyze_item(self, db: AsyncSession, user_id: int, req: AnalyzeItemRequest) -> AnalyzeItemResponse:
        """
        智能识别物品信息（支持图片、文字描述或语音）
        """
        # 获取用户设置
        from backend.app.jia.service.user_setting_service import user_setting_service
        user_settings = await user_setting_service.get_my_settings(db=db, user_id=user_id)
        current_provider_id = user_settings.copilot_provider or 4

        # 如果有音频文件，先转文字
        text_input = req.text
        if req.audio_path:
            try:
                text_input = await self._transcribe_audio(db, current_provider_id, req.audio_path)
            except Exception as e:
                return AnalyzeItemResponse(name="语音识别失败", notes=str(e))

        # 统一的 prompt
        system_prompt = """你是一个专业的物品识别与生活管理助手。请根据用户提供的图片或文字描述，返回详细的 JSON 格式物品信息。

**识别要求**：
1. **name**: 准确识别物品名称，尽量具体（如"苹果 iPhone 15 Pro"而非"手机"）
2. **category**: 分类（衣物/电子产品/书籍/厨具/家具/日用品/食品/药品/杂物）
3. **description**: 详细描述物品的外观特征、颜色、材质、用途和使用场景
4. **quantity**: 可见/提到的数量，默认为1
5. **standard_quantity**: 一个普通人建议拥有的合理数量（避免冗余或缺失）
   - 例如：牙刷建议1-2个，袜子建议10-15双，充电器建议2-3个
6. **consume_days**: 物品的建议更换/消耗周期（天数）
   - 例如：牙刷约90天，毛巾约180天，电子产品约1095天（3年），要根据物品的具体情况，而不是类别
   - 食品填写保质期天数，耐用品填写建议使用寿命
7. **price**: 如果用户提到价格就用用户的，否则给出市场参考价格（人民币）
8. **expire_date**: 如果是食品/药品且能看到/推算日期，填写保质期（YYYY-MM-DD格式）
9. **notes**: 其他有用信息，如保养建议、存放注意事项等

请严格按以下 JSON 格式返回（不要返回其他内容）：
{
    "name": "物品名称",
    "category": "分类",
    "description": "详细描述：外观、颜色、材质、用途、使用场景",
    "quantity": 1,
    "standard_quantity": 1,
    "consume_days": null,
    "price": null,
    "expire_date": null,
    "notes": null
}"""

        # 根据输入类型构建消息
        if req.image_url:
            # 图片识别
            user_content = [
                {"type": "text", "text": "请识别这张图片中的物品，给出完整的信息"},
                {"type": "image_url", "image_url": {"url": req.image_url}}
            ]
            if text_input:
                # 图片 + 文字补充
                user_content[0]["text"] = f"请识别这张图片中的物品。用户补充说明：{text_input}"
            messages = [
                AIChatMessage(role="system", content=system_prompt),
                AIChatMessage(role="user", content=user_content)
            ]
        elif text_input:
            # 纯文字描述
            messages = [
                AIChatMessage(role="system", content=system_prompt),
                AIChatMessage(role="user", content=f"用户描述的物品：{text_input}")
            ]
        else:
            return AnalyzeItemResponse(name="输入错误", notes="请提供图片、文字描述或语音")

        chat_param = AIChat(
            provider_id=current_provider_id,
            model_id="gpt-4o-2024-11-20",
            messages=messages,
            temperature=0.3,
        )

        try:
            ai_resp = await ai_chat_service.raw_chat(db=db, chat=chat_param)
            resp_content = ai_resp.get('content', '')

            # 解析 JSON
            import re
            json_match = re.search(r'\{[\s\S]*\}', resp_content)
            if json_match:
                result = json.loads(json_match.group())
                return AnalyzeItemResponse(
                    name=result.get('name'),
                    category=result.get('category'),
                    description=result.get('description'),
                    quantity=result.get('quantity'),
                    standard_quantity=result.get('standard_quantity'),
                    consume_days=result.get('consume_days'),
                    price=result.get('price'),
                    expire_date=result.get('expire_date'),
                    notes=result.get('notes'),
                )
            else:
                return AnalyzeItemResponse(name="未能识别", notes=resp_content)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return AnalyzeItemResponse(name="识别失败", notes=str(e))

    async def recognize_formula(self, db: AsyncSession, user_id: int, req: RecognizeFormulaRequest) -> RecognizeFormulaResponse:
        """
        通过图片识别数学公式，返回 LaTeX
        """
        from backend.app.jia.service.user_setting_service import user_setting_service
        user_settings = await user_setting_service.get_my_settings(db=db, user_id=user_id)
        current_provider_id = user_settings.copilot_provider or 4

        system_prompt = """你是一个专业的数学公式识别助手。请根据用户提供的图片，识别其中的数学公式并转换为 LaTeX 格式。

**要求**：
1. 只返回 LaTeX 公式本身，不要包含 $$ 或 $ 符号
2. 如果图片中有多个公式，用换行分隔
3. 确保 LaTeX 语法正确，可以被标准 LaTeX 渲染引擎解析
4. 如果无法识别，返回空字符串

请严格按以下 JSON 格式返回（不要返回其他内容）：
{"formula": "LaTeX公式", "confidence": "high/medium/low"}"""

        messages = [
            AIChatMessage(role="system", content=system_prompt),
            AIChatMessage(role="user", content=[
                {"type": "text", "text": "请识别这张图片中的数学公式，转换为 LaTeX 格式"},
                {"type": "image_url", "image_url": {"url": req.image_url}}
            ])
        ]

        chat_param = AIChat(
            provider_id=current_provider_id,
            model_id="gpt-4o-2024-11-20",
            messages=messages,
            temperature=0.1,
        )

        try:
            ai_resp = await ai_chat_service.raw_chat(db=db, chat=chat_param)
            resp_content = ai_resp.get('content', '')

            import re
            json_match = re.search(r'\{[\s\S]*\}', resp_content)
            if json_match:
                result = json.loads(json_match.group())
                return RecognizeFormulaResponse(
                    formula=result.get('formula', ''),
                    confidence=result.get('confidence'),
                )
            else:
                # 如果没有 JSON，尝试直接当作 LaTeX
                cleaned = resp_content.strip().strip('$').strip()
                return RecognizeFormulaResponse(formula=cleaned)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return RecognizeFormulaResponse(formula='', confidence=f'识别失败: {str(e)}')

    async def analyze_food(self, db: AsyncSession, user_id: int, req: AnalyzeFoodRequest) -> AnalyzeFoodResponse:
        """
        智能识别食物营养信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param req: 请求参数
        :return:
        """
        from backend.app.jia.service.user_setting_service import user_setting_service
        user_settings = await user_setting_service.get_my_settings(db=db, user_id=user_id)
        current_provider_id = user_settings.copilot_provider or 4

        system_prompt = """你是一位专业的食品营养分析师。请根据用户提供的图片或文字描述，返回详细的食物营养信息 JSON。

**识别要求**（所有营养数据基于每 100g 可食部分）：
1. **name**: 准确的食物名称（如"鸡胸肉"而非"鸡肉"）
2. **alias**: 常见别名，逗号分隔（如"鸡脯肉,鸡胸脯"）
3. **description**: 简短描述，包括口感、常见做法
4. **serving_size**: 通常为 100（每 100g）
5. **serving_unit**: 通常为 "g"
6. **energy**: 能量 (kcal)
7. **protein**: 蛋白质 (g)
8. **carbohydrate**: 碳水化合物 (g)
9. **fat**: 脂肪 (g)
10. **water**: 水分 (g)
11. **fiber**: 膳食纤维 (g)
12. **sodium**: 钠 (mg)
13. **notes**: 饮食建议、注意事项

请严格按以下 JSON 格式返回（不要返回其他内容）：
{
    "name": "食物名称",
    "alias": "别名1,别名2",
    "description": "简短描述",
    "serving_size": 100,
    "serving_unit": "g",
    "energy": 0,
    "protein": 0,
    "carbohydrate": 0,
    "fat": 0,
    "water": 0,
    "fiber": 0,
    "sodium": 0,
    "notes": null
}"""

        if req.image_url:
            user_content = [
                {"type": "text", "text": "请识别这张图片中的食物，给出完整的营养信息"},
                {"type": "image_url", "image_url": {"url": req.image_url}},
            ]
            if req.text:
                user_content[0]["text"] = f"请识别这张图片中的食物。用户补充说明：{req.text}"
            messages = [
                AIChatMessage(role="system", content=system_prompt),
                AIChatMessage(role="user", content=user_content),
            ]
        elif req.text:
            messages = [
                AIChatMessage(role="system", content=system_prompt),
                AIChatMessage(role="user", content=f"用户描述的食物：{req.text}"),
            ]
        else:
            return AnalyzeFoodResponse(name="输入错误", notes="请提供图片或文字描述")

        chat_param = AIChat(
            provider_id=current_provider_id,
            model_id="gpt-4o-2024-11-20",
            messages=messages,
            temperature=0.3,
        )

        try:
            ai_resp = await ai_chat_service.raw_chat(db=db, chat=chat_param)
            resp_content = ai_resp.get('content', '')

            import re
            json_match = re.search(r'\{[\s\S]*\}', resp_content)
            if json_match:
                result = json.loads(json_match.group())
                return AnalyzeFoodResponse(
                    name=result.get('name'),
                    alias=result.get('alias'),
                    description=result.get('description'),
                    serving_size=result.get('serving_size'),
                    serving_unit=result.get('serving_unit'),
                    energy=result.get('energy'),
                    protein=result.get('protein'),
                    carbohydrate=result.get('carbohydrate'),
                    fat=result.get('fat'),
                    water=result.get('water'),
                    fiber=result.get('fiber'),
                    sodium=result.get('sodium'),
                    notes=result.get('notes'),
                )
            return AnalyzeFoodResponse(name="未能识别", notes=resp_content)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return AnalyzeFoodResponse(name="识别失败", notes=str(e))

    async def _transcribe_audio(self, db: AsyncSession, provider_id: int, audio_path: str) -> str:
        """
        使用 Whisper 将音频转为文字
        """
        from openai import AsyncOpenAI
        from backend.plugin.ai.crud.crud_provider import ai_provider_dao
        from backend.core.conf import settings
        import os

        # 获取 provider 配置
        provider = await ai_provider_dao.get(db, provider_id)
        if not provider:
            raise Exception("AI 服务商不存在")

        base_url = provider.api_host
        if base_url:
            base_url = f'{base_url}/v1' if not base_url.endswith('/v1') else base_url

        client = AsyncOpenAI(api_key=provider.api_key, base_url=base_url)

        # 构建音频文件完整路径
        upload_dir = settings.UPLOAD_DIR if hasattr(settings, 'UPLOAD_DIR') else 'static/upload'
        full_path = os.path.join(upload_dir, audio_path)

        # 读取音频文件
        with open(full_path, 'rb') as f:
            audio_data = f.read()

        # 调用 Whisper API
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.m4a", audio_data, "audio/m4a"),
            language="zh",
        )

        return transcript.text


copilot_service = CopilotService()
