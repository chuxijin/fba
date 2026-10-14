"""决策模型（Jev / System One）客户端。

## 为什么单独一个文件

项目自带的两个 AI 调用封装**都调不通这条通道**：
- `ChatService.raw_chat()` 走 OpenAI 的 `/v1/chat/completions`
- `LLMClient.invoke_structured()` 走 pydantic_ai，同样是 chat completions

而决策模型用的是 System One 协议（`POST {api_host}`，body 是
`{state, model, questions:{...}}`），**不是** OpenAI 兼容路径。
所以只能自己直连。

## 通道配置存在哪

`ai_provider` / `ai_model` 表，`type = AIProviderType.decision_model = 11`：
- `api_provider.api_host` 存到**完整 endpoint**（含 `/v1/systemone`）
- `ai_model.model_id` 存模型名（如 `decision-model-preview`）
- Key 存 `ai_provider.api_key`

新增这个 enum 的原因就是：这两个表本来只有 type/api_key/api_host，
没有地方区分「这是 chat 模型」还是「这是决策模型」。

## 相比脚本补了什么

脚本 `classify_jev()` 是裸 `httpx.post`，一次网络抖动整题就 failed。
这里加了指数退避重试 —— 批量跑几万题时这是必需品，不是锦上添花。
"""

import asyncio
import json
import logging

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.service.ai_label_prompt import JEV_QUESTION_ID
from backend.plugin.ai.enums import AIProviderType
from backend.plugin.ai.model.model import AIModel
from backend.plugin.ai.model.provider import AIProvider

logger = logging.getLogger(__name__)

# 官方规格：单次请求体上限 65536 token，choice 选项 ≤255
MAX_INPUT_TOKENS = 65536
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class JevError(RuntimeError):
    """决策模型调用失败（网络层或返回体不合法）"""


async def resolve_decision_model(
    db: AsyncSession, *, provider_id: int | None = None, model_id: str | None = None
) -> tuple[AIModel, AIProvider]:
    """取一个可用的决策模型；不指定就自动取最新的一个。"""
    stmt = (
        select(AIModel, AIProvider)
        .join(AIProvider, AIProvider.id == AIModel.provider_id)
        .where(
            AIModel.status == 1,
            AIProvider.status == 1,
            AIProvider.deleted == 0,
            AIModel.deleted == 0,
            AIProvider.type == AIProviderType.decision_model,
        )
    )
    if model_id:
        stmt = stmt.where(AIModel.model_id == model_id)
    if provider_id:
        stmt = stmt.where(AIProvider.id == provider_id)
    row = (await db.execute(stmt.order_by(AIModel.id.desc()).limit(1))).first()
    if row is None:
        msg = '没有可用的决策模型，请先在「AI 供应商」里配置 type=决策模型 的通道'
        raise JevError(msg)
    model, provider = row[0], row[1]
    if not (provider.api_key or '').strip():
        msg = f'决策模型供应商「{provider.name}」没有填 API Key'
        raise JevError(msg)
    return model, provider


def build_payload(
    *, state: str, criteria: dict[str, str], model: str, instructions: str
) -> dict[str, Any]:
    """构造 System One 请求体（官方 /v1/systemone 与 OpenRouter /alpha/decisions 格式一致）。"""
    return {
        'state': state,
        'model': model,
        'questions': {
            JEV_QUESTION_ID: {
                'type': 'choice',
                'instructions': instructions,
                'criteria': criteria,
            }
        },
    }


def parse_answer(
    payload: dict[str, Any], *, point_by_id: dict[int, dict[str, Any]]
) -> tuple[int | None, Decimal | None, str]:
    """从响应里抽出 (知识点 id, 置信度, top3 概率说明)。

    `confidence` 是**分布集中度**，不是校准过的正确率 —— 当一道题在两个类之间都沾边，
    概率一分为二，它会掉到 0.5 上下，哪怕最终选对了。别把它当准确率读。
    """
    answer = (payload.get('answers') or {}).get(JEV_QUESTION_ID) or {}

    raw_confidence = answer.get('confidence')
    confidence: Decimal | None = None
    if raw_confidence is not None:
        try:
            confidence = Decimal(str(raw_confidence)).quantize(Decimal('0.0001'))
        except (InvalidOperation, TypeError, ValueError):
            confidence = None

    note = describe_probs(answer.get('probabilities'), point_by_id)
    choice = str(answer.get('choice') or '').strip()
    if not choice or choice == 'other':
        return None, confidence, note
    if choice.isdigit():
        return int(choice), confidence, note
    return None, confidence, f'返回了未知选项 {choice}；{note}'


def describe_probs(probabilities: Any, point_by_id: dict[int, dict[str, Any]]) -> str:
    """把概率分布压成一行，方便在页面上核对模型是不是「勉强选的」。"""
    if not isinstance(probabilities, dict) or not probabilities:
        return ''
    try:
        ranked = sorted(probabilities.items(), key=lambda item: float(item[1]), reverse=True)[:3]
    except (TypeError, ValueError):
        return ''
    rendered: list[str] = []
    for name, value in ranked:
        label = str(name)
        if label.isdigit() and int(label) in point_by_id:
            label = point_by_id[int(label)]['name']
        rendered.append(f'{label}={float(value):.2f}')
    return '概率 ' + ' / '.join(rendered)


async def call_decision_model(
    *,
    http: httpx.AsyncClient,
    api_host: str,
    api_key: str,
    model: str,
    state: str,
    criteria: dict[str, str],
    instructions: str,
    max_retries: int = 3,
) -> dict[str, Any]:
    """POST 一次 System One，失败按指数退避重试。"""
    payload = build_payload(state=state, criteria=criteria, model=model, instructions=instructions)
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await http.post(api_host, headers=headers, json=payload)
            if response.status_code in RETRYABLE_STATUS:
                raise JevError(f'HTTP {response.status_code}: {response.text[:200]}')
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, JevError, json.JSONDecodeError) as exc:  # noqa: PERF203
            last_error = exc
            if attempt >= max_retries:
                break
            delay = 2 ** (attempt - 1)
            logger.warning(
                '决策模型第 %s/%s 次调用失败：%s，%s 秒后重试', attempt, max_retries, exc, delay
            )
            await asyncio.sleep(delay)

    msg = f'决策模型调用失败（已重试 {max_retries} 次）：{last_error}'
    raise JevError(msg)
