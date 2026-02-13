from fastapi import APIRouter
from starlette.responses import StreamingResponse

from backend.common.response.response_schema import ResponseModel, response_base
from backend.database.db import CurrentSession
from backend.plugin.ai.schema.chat import AIChat, EmbeddingParam
from backend.plugin.ai.service.chat_service import ai_chat_service

router = APIRouter()


@router.post('/completions', summary='文本生成（对话）')
async def completions(db: CurrentSession, chat: AIChat) -> StreamingResponse:
    return StreamingResponse(ai_chat_service.stream_messages(db=db, chat=chat), media_type='text/plain')


@router.post('/embeddings', summary='文本向量化')
async def embeddings(db: CurrentSession, obj: EmbeddingParam) -> ResponseModel:
    vector = await ai_chat_service.embedding(db=db, provider_id=obj.provider_id, model_id=obj.model_id, text=obj.text)
    return response_base.success(data=vector)
