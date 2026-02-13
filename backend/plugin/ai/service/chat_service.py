import json

from collections.abc import AsyncGenerator
from typing import Any

from pydantic_ai import Agent, ModelResponse, ModelSettings, TextPart
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.plugin.ai.crud.crud_model import ai_model_dao
from backend.plugin.ai.crud.crud_provider import ai_provider_dao
from backend.plugin.ai.schema.chat import AIChat
from backend.plugin.ai.utils.message_parse import to_chat_message
from backend.plugin.ai.utils.model_control import get_pydantic_model

chat_agent = Agent(name='fba_chat')


class ChatService:
    """聊天服务类"""

    @staticmethod
    async def stream_messages(*, db: AsyncSession, chat: AIChat) -> AsyncGenerator[bytes, Any]:
        """
        流式消息

        :param db: 数据库会话
        :param chat: 聊天参数
        :return:
        """
        provider = await ai_provider_dao.get(db, chat.provider_id)
        if not provider:
            raise errors.NotFoundError(msg='供应商不存在')

        if not provider.status:
            raise errors.RequestError(msg='此供应商暂不可用，请更换供应商或联系系统管理员')

        model = await ai_model_dao.get_by_model_and_provider(db, chat.model_id, chat.provider_id)
        if not model:
            raise errors.NotFoundError(msg='供应商模型不存在')

        if not model.status:
            raise errors.RequestError(msg='此模型暂不可用，请更换模型或联系系统管理员')

        yield json.dumps({'role': 'user', 'content': chat.user_prompt}, ensure_ascii=False).encode('utf-8') + b'\n'

        model_settings = {
            k: v
            for k, v in {
                'max_tokens': chat.max_tokens,
                'temperature': chat.temperature,
                'top_p': chat.top_p,
                'timeout': chat.timeout,
                'parallel_tool_calls': chat.parallel_tool_calls,
                'seed': chat.seed,
                'presence_penalty': chat.presence_penalty,
                'frequency_penalty': chat.frequency_penalty,
                'logit_bias': chat.logit_bias,
                'stop_sequences': chat.stop_sequences,
                'extra_headers': chat.extra_headers,
                'extra_body': chat.extra_body,
            }.items()
            if v is not None
        }

        async with chat_agent.run_stream(
            chat.user_prompt,
            model=get_pydantic_model(
                provider_type=provider.type,
                model_name=model.model_id,
                api_key=provider.api_key,
                base_url=provider.api_host,
                model_settings=ModelSettings(**model_settings),
            ),
        ) as result:
            async for text in result.stream_output(debounce_by=0.01):
                message = ModelResponse(parts=[TextPart(text)], model_name=model.model_id, timestamp=result.timestamp())
                yield json.dumps(to_chat_message(message)).encode('utf-8') + b'\n'



    @staticmethod
    async def invoke(*, db: AsyncSession, chat: AIChat) -> str:
        """
        非流式对话，返回完整内容

        :param db: 数据库会话
        :param chat: 聊天参数
        :return:
        """
        provider = await ai_provider_dao.get(db, chat.provider_id)
        if not provider:
            raise errors.NotFoundError(msg='供应商不存在')

        if not provider.status:
            raise errors.RequestError(msg='此供应商暂不可用，请更换供应商或联系系统管理员')

        model = await ai_model_dao.get_by_model_and_provider(db, chat.model_id, chat.provider_id)
        if not model:
            raise errors.NotFoundError(msg='供应商模型不存在')

        if not model.status:
            raise errors.RequestError(msg='此模型暂不可用，请更换模型或联系系统管理员')

        model_settings = {
            k: v
            for k, v in {
                'max_tokens': chat.max_tokens,
                'temperature': chat.temperature,
                'top_p': chat.top_p,
                'timeout': chat.timeout,
                'parallel_tool_calls': chat.parallel_tool_calls,
                'seed': chat.seed,
                'presence_penalty': chat.presence_penalty,
                'frequency_penalty': chat.frequency_penalty,
                'logit_bias': chat.logit_bias,
                'stop_sequences': chat.stop_sequences,
                'extra_headers': chat.extra_headers,
                'extra_body': chat.extra_body,
            }.items()
            if v is not None
        }

        result = await chat_agent.run(
            chat.user_prompt,
            model=get_pydantic_model(
                provider_type=provider.type,
                model_name=model.model_id,
                api_key=provider.api_key,
                base_url=provider.api_host,
                model_settings=ModelSettings(**model_settings),
            ),
        )
        if hasattr(result, 'data'):
            return result.data
        elif hasattr(result, 'output'):
            return result.output
        else:
             # Try to find where the content is
            return str(result)

    @staticmethod
    async def raw_chat(*, db: AsyncSession, chat: AIChat) -> dict:
        """
        直接调用 OpenAI 兼容接口，支持多模态和 Tool Calls
        """
        provider = await ai_provider_dao.get(db, chat.provider_id)
        if not provider:
            raise errors.NotFoundError(msg='供应商不存在')

        if not provider.status:
            raise errors.RequestError(msg='此供应商暂不可用，请更换供应商或联系系统管理员')

        model = await ai_model_dao.get_by_model_and_provider(db, chat.model_id, chat.provider_id)
        if not model:
            raise errors.NotFoundError(msg='供应商模型不存在')

        if not model.status:
            raise errors.RequestError(msg='此模型暂不可用，请更换模型或联系系统管理员')
            
        from openai import AsyncOpenAI
        
        base_url = provider.api_host
        if base_url:
            base_url = f'{base_url}/v1' if not base_url.endswith('/v1') else base_url
            
        client = AsyncOpenAI(api_key=provider.api_key, base_url=base_url)
        
        # 构造 Messages
        openai_messages = []
        if chat.messages:
             for m in chat.messages:
                 # 确保 content 是 list[dict] 或 str
                 msg_dict = m.model_dump(exclude_none=True)
                 openai_messages.append(msg_dict)
        else:
             openai_messages.append({"role": "user", "content": chat.user_prompt})
             
        # 构造参数
        kwargs = {
            'model': model.model_id,
            'messages': openai_messages,
            'temperature': chat.temperature,
            'max_tokens': chat.max_tokens,
        }
        
        if chat.tools:
            kwargs['tools'] = chat.tools
            if chat.tool_choice:
                kwargs['tool_choice'] = chat.tool_choice
        
        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.model_dump()
        except Exception as e:
            raise errors.ServerError(msg=f'AI 请求失败: {str(e)}')


    @staticmethod
    async def embedding(*, db: AsyncSession, provider_id: int, model_id: str, text: str) -> list[float]:
        """
        获取文本向量

        :param db: 数据库会话
        :param provider_id: 供应商 ID
        :param model_id: 模型 ID
        :param text: 文本内容
        :return:
        """
        provider = await ai_provider_dao.get(db, provider_id)
        if not provider:
            raise errors.NotFoundError(msg='供应商不存在')

        if not provider.status:
            raise errors.RequestError(msg='此供应商暂不可用，请更换供应商或联系系统管理员')

        # 使用 openai 客户端获取向量
        from openai import AsyncOpenAI

        base_url = provider.api_host
        if base_url:
            base_url = f'{base_url}/v1' if not base_url.endswith('/v1') else base_url

        try:
            client = AsyncOpenAI(api_key=provider.api_key, base_url=base_url)
            response = await client.embeddings.create(input=text, model=model_id)
            return response.data[0].embedding
        except Exception as e:
            raise errors.ServerError(msg=f'向量化失败: {str(e)}')


ai_chat_service: ChatService = ChatService()
