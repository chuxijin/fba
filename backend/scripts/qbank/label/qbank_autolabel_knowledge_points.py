#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识点自动标注脚本（单文件，直接跑）

思路很简单：把「题干 + 本体系全部知识点」一次性交给模型，让它**从中挑一个**并给出置信度。
本体系知识点只有十几个到几十个，直接作为选项列出来即可 ——
**不需要向量化、不需要检索、不需要任务队列**。

两个引擎，用 `--engine` 选：

┌─ `chat`（默认）───────────────────────────────────────────────────────────┐
│ 走项目自带的 OpenAI 兼容网关（后台「AI 供应商/模型」里配的那些），        │
│ 让模型直接吐 JSON：{"point_id":…, "confidence":…, "reason":…}             │
└───────────────────────────────────────────────────────────────────────────┘

┌─ `jev`（推荐，便宜两个数量级）───────────────────────────────────────────┐
│ 走 TypeSafe AI 的 Jev（System One 决策模型）的 Choice 原语 ——             │
│ 它**只能从给定选项里挑一个**（结构上不会幻觉出候选之外的点），            │
│ 并返回 choice + probabilities + confidence。                              │
│                                                                           │
│ 两家渠道，用 `--jev-provider` 选（请求体格式完全一致，只有地址/模型名不同）：│
│                                                                           │
│   ① typesafe（官方直连，默认）                                            │
│      POST https://api.typesafe.ai/v1/systemone     模型 jev-latest        │
│      https://console.typesafe.ai 注册（新账号送 $5 ≈ 1.2 亿 input token） │
│      ⚠️ 官方 2026-09-22 起因容量**再次暂停新注册**（页面会报 "we're full"），│
│         已有账号不受影响；注册不了就走下面 ②。                            │
│                                                                           │
│   ② vercel ❌ **实测不可用**（2026-09-23 拿真 Key 验证）                   │
│      服务端 403：必须先绑信用卡才解锁「免费」额度（Hobby 计划不够），     │
│      且免费期原文 "until September 25th" 已过。**别再当白嫖首选**         │
│                                                                           │
│   ③ openrouter（要充值，最现实）                                          │
│      POST https://openrouter.ai/api/alpha/decisions  模型 typesafe/jev-1.13│
│      ⚠️ 不在 /v1/chat/completions，chat SDK 用不了，但 body 与官方一致    │
│                                                                           │
│   ④ aliyun ★**限时免费**（2026-09-24 上线，当前首选）                     │
│      POST https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com              │
│           /compatible-mode/v1/systemone                                   │
│      模型 **decision-model-preview**（⚠️ 没有 qwen- 前缀）                │
│      域名含业务空间 ID ⇒ 必须传 --jev-base-url，见下方命令                │
│                                                                           │
│ Key 走环境变量：AI_GATEWAY_API_KEY / TYPESAFE_API_KEY / OPENROUTER_API_KEY│
│ 或 --jev-api-key                                                          │
│ 计费：本任务每题约 1–2 千 token ⇒ 6 万题全量重标大致在 1 亿 token 以内，   │
│ ⇒ 官方的 $5 额度够用；OpenRouter 按同价充值，充多少用多少。               │
│ 文档：https://docs.typesafe.ai                                             │
└───────────────────────────────────────────────────────────────────────────┘

写入走 `question_knowledge_point_dao.replace(system_id=...)`，即**只替换该体系的标注**，
其他体系（如 default 的导入数据）的标注不受影响。

⚠️ 默认只跑「本体系还没有标注」的题，并且**永不覆盖 source='manual' 的人工标注**。

用法:
    cd backend

    # 1) 先看请求长什么样（不调模型、不写库、零成本）
    python -m scripts.qbank.label.qbank_autolabel_knowledge_points \
        --system-id 4 --bank-id 61 --limit 5 --leaves-only --dry-run
    #    (加 --engine jev 就打印 Jev 的请求体，看它不需要 Key)

    # 2) 真调模型但不写库，只看它会标成什么
    #    注：行测题大多已经标过本体系，默认只跑「未标注」会一条也筛不到，所以要加 --include-labeled
    python -m scripts.qbank.label.qbank_autolabel_knowledge_points \
        --system-id 4 --bank-id 61 --limit 50 --leaves-only --include-labeled --engine jev

    #    官方注册暂停时，改走 OpenRouter：
    python -m scripts.qbank.label.qbank_autolabel_knowledge_points \
        --system-id 4 --bank-id 61 --limit 50 --leaves-only --include-labeled \
        --engine jev --jev-provider openrouter

    #    走阿里云百炼（限时免费；WorkspaceId 在百炼控制台拿，必须带在域名里）：
    python -m scripts.qbank.label.qbank_autolabel_knowledge_points \
        --system-id 4 --bank-id 61 --limit 50 --leaves-only --include-labeled \
        --engine jev \
        --jev-base-url https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode \
        --jev-endpoint /v1/systemone \
        --jev-model decision-model-preview \
        --jev-api-key $DASHSCOPE_API_KEY
    #    ⚠️ 该模型不支持 chat completions ⇒ 只能走 jev 通道，不能加进后台的 ai_provider

    # 3) 确认没问题再落库
    python -m scripts.qbank.label.qbank_autolabel_knowledge_points \
        --system-id 4 --bank-id 61 --limit 50 --leaves-only --include-labeled --engine jev --write

    #    跑「某章节」用 --section-id（否则按题库筛会把整张卷的言语/判断也拿去标数量关系）：
    python -m scripts.qbank.label.qbank_autolabel_knowledge_points \
        --system-id 4 --section-id 1931 --leaves-only --root-point-id 561 --include-labeled \
        --engine jev --write
    #    ⚠️ jev 引擎的两个实测结论（2026-09-25，百炼 decision-model-preview，455 题全量）：
    #      --no-jev-rules  带长归类规则反而把模型推向 other（弃权 25% → 15%，且规则对正确率无帮助）
    #      --no-jev-other  题已按章节筛过时 other 是多余选项，去掉后弃权 15% → 0%
    #      ⇒ **封闭场景一律加这两个开关**，455 题约 85 秒。
    #
    #    ⚠️ 关于 `JEV_CRITERIA_HINTS`（特征词描述）—— 实测**去掉描述反而略好**：
    #      全体平均置信度 0.845 → 0.872，低置信 59 → 53，和差倍比 123 → 102。
    #      原因：**描述写得越宽，那个类越像垃圾桶**。「和差倍比问题」一条里塞了
    #      平均数/植树/方阵/分段计费/极值构造 6 个不相干概念，反而让它跟经济、工程、数论都重叠。
    #      ⇒ 描述要写，但**每条只说一件事、类与类之间不许重叠**；宁可不写也别写宽。

连哪台库由 backend/.env 决定。想临时跑生产库可以不改文件，用同名环境变量覆盖：
    DATABASE_HOST / DATABASE_PORT / DATABASE_USER / DATABASE_PASSWORD（取值见 backend/.env.prod）
"""

# 该脚本必须先把项目根目录插入 sys.path，之后才能导入 backend.*，故整体豁免 E402
# ruff: noqa: E402

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from pathlib import Path
from typing import Any

import httpx

from sqlalchemy import select, text

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.question_bank_v2.crud.crud_knowledge import question_knowledge_point_dao
from backend.app.question_bank_v2.schema.knowledge import KnowledgePointAssignmentParam
from backend.app.question_bank_v2.service.evaluation_service import EvaluationService
from backend.database.db import async_db_session
from backend.plugin.ai.model.model import AIModel
from backend.plugin.ai.model.provider import AIProvider
from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
from backend.plugin.ai.service.chat_service import ai_chat_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('autolabel')

DEFAULT_THRESHOLD = Decimal('0.6000')
DB_PRECISION = '0.0001'
ENGINES = ('chat', 'jev')

SYSTEM_PROMPT = (
    '你是中文考试题库的知识点标注助手。你只能从用户给出的候选知识点中挑选一个，'
    '严禁编造候选之外的知识点。若候选项确实都不合适，必须返回 null，不要硬猜。'
    '置信度要如实反映你的把握程度（没有把握就给低分）。只返回 JSON，不要输出任何其他内容。'
)

# ---- 数量关系的归类规则 ----
# 叶子知识点混了两个维度：情境（题目讲什么事）与方法（用什么套路解）。
# 模型乱标的主因是它不知道该用哪个「轴」，所以把裁决规则写死进 prompt —— 这比继续改知识点树更关键。
# ⚠️ 规则只存在于文档和 prompt 里，**不要在知识点树上建「情境类」/「方法类」分组层**：
#    父节点本身也能挂题，多一层就多一层「被误标到大类」的风险。
CLASSIFY_RULES = """【归类规则（必须遵守）】
候选知识点分两种：
- 情境类：题目讲的是什么事（行程 / 工程 / 经济 / 年龄 / 几何 / 浓度 / 周期与日期 / 容斥 / 概率排列组合 / 钟表）
- 方法类：用什么套路解（和差倍比、数论和数字特性）—— 只有实在没有情境时才用

裁决顺序：
1. 题干有明确情境 → 归情境类。即使解题时要用到不定方程、比例、整除等方法，也不改归情境。
2. 题干没有情境，或核心考点就是那个方法本身 → 归方法类。
3. 两者都沾边 → 选考生「看到题目第一眼就该想到」的那个：情境能一句话说清就归情境，说不清就归方法。

其余题型往哪塞（看到这些特征不要另立类别）：
- 牛吃草、统筹规划（最少多少分钟 / 几天完成）→ 工程问题
- 平均数、比例、百分数、倍数、植树、方阵、分段计费、
  极值构造（问至少 / 至多，但归不进任何具体情境）→ 和差倍比问题
- 不定方程、整除、尾数、奇偶、余数、数列 → 数论和数字特性问题
- 溶液、浓度、加水蒸发、溶质溶剂比例 → 浓度问题
- 快慢钟、时针分针夹角 / 重合 / 坏钟校准 → 钟表问题
- 星期、日期、日历推算 → 周期与日期问题
- 递推计数、标数法 → 概率排列组合问题

判例：
- 甲乙两队合作修路，几天完成 → 工程问题（不是和差倍比）
- 甲队人数是乙队的 1.5 倍、共 100 人 → 和差倍比问题（没有情境）
- 工程队施工、人数为正整数需解不定方程 → 工程问题（情境优先于方法）
- 某单位持有甲乙丙三项认证的人数，至少有多少人三项都有 → 容斥问题（情境）
- 30 人得分互不相同、平均 93.8 分、排名最低可能是第几 → 和差倍比问题（不是数字推理）
"""

JEV_INSTRUCTION = '这道题考查的是 criteria 里的哪一个知识点？只能选一个；确实都不属于就选 other。'

# ---- Jev 渠道预设 ----
# 两家的请求体格式一致（都是 System One 的 state/questions/criteria），只有地址、路径、模型名、Key 变量名不同
JEV_PRESETS: dict[str, dict[str, Any]] = {
    'typesafe': {
        'base_url': 'https://api.typesafe.ai',
        'endpoint': '/v1/systemone',
        'model': 'jev-latest',
        'env_names': ('TYPESAFE_API_KEY',),
        'signup': 'https://console.typesafe.ai 注册（新账号送 $5；注意 2026-09-22 起因容量暂停新注册）',
    },
    'openrouter': {
        'base_url': 'https://openrouter.ai/api',
        'endpoint': '/alpha/decisions',
        'model': 'typesafe/jev-1.13',
        'env_names': ('OPENROUTER_API_KEY',),
        'signup': 'https://openrouter.ai 注册并先充值（$0.042/M input，输出免费，与官方同价）',
    },
    'vercel': {
        'base_url': 'https://ai-gateway.vercel.sh',
        'endpoint': '/v1/evaluate',
        'model': 'typesafe-ai/jev',
        'env_names': ('AI_GATEWAY_API_KEY',),
        'signup': 'https://vercel.com 注册（Hobby 免费计划即可）→ AI Gateway 建 Key；官方促销期内 Jev 免费',
    },
}
JEV_QUESTION_ID = 'point'
JEV_OTHER_KEY = 'other'
JEV_OTHER_DESC = '以上都不是（这道题不属于给出的任何知识点）'
JEV_MAX_OPTIONS = 255  # Jev 单个 Choice 的选项上限

# Jev 是「System 1」直觉模型，不做推理链 ⇒ **criteria 的描述质量几乎决定命中率**，
# 这一点和 chat 引擎完全不同（chat 能读长 prompt 自己推理）。所以给每个知识点补一句特征词。
# 按「知识点名称」匹配，匹配不到就退回路径文本 ⇒ 换体系/改名都不会炸，最多是没优化。
# ⚠️⚠️ **两条硬性写法约束**（2026-09-25 实测，违反了会让准确率下降）：
#   1. 每条只说一件事 —— 塞进 6 个互不相干概念的那条（旧「和差倍比问题」）实测把类变成了垃圾桶，
#      去掉全部描述反而更好（平均置信度 0.845 → 0.872）；
#   2. 类与类之间不许重叠 —— 一重叠模型就摇摆，confidence 直接掉到 0.5。
JEV_CRITERIA_HINTS: dict[str, str] = {
    '数字推理': '数列填空、等差等比、递推数列；题干极短，通常只有一串数字带一个括号',
    '行程问题': '相遇追及、速度时间路程、流水行船、多次相遇、环形跑道、上下坡',
    '工程问题': '多人/多队合作完成某项工作、工作效率、水管注水、牛吃草、统筹安排最少时间',
    '周期与日期问题': '星期几、日期与日历推算、闰年、循环周期、重复出现的规律',
    '概率排列组合问题': '概率计算、排列组合计数、抽样、分堆分组、递推计数、标数法',
    '容斥问题': '多个集合的重叠人数、至少/至多满足若干条件、持有若干项认证',
    # 2026-09-25 收窄：原来这一条塞了 平均数/植树/方阵/分段计费/极值构造，跟经济、工程、数论全重叠
    '和差关系与倍数比例问题': '两数之和与差、倍数关系、按比例分配、份数思想',
    # 2026-09-25 新增：承接从上面拆出来的「极值构造」，专收没有具体情境的纯极值题
    '最值构造问题': '最不利原则、极端构造：题干问最多/最少，且没有行程、工程、几何等具体情境'
                 '(如「至多有多少人」「排名最低可能是第几」)',
    '数论和数字特性问题': '整除、余数、尾数、奇偶性、不定方程、质因数、约数与倍数',
    '年龄问题': '年龄差不变、几年后/几年前、代入年龄关系',
    '几何问题': '平面图形面积周长、立体图形体积表面积、相似与勾股、切面、坐标几何',
    '经济问题': '成本售价利润、折扣、利润率、销量与收入、涉价的分段计费',
    '浓度问题': '溶液浓度、溶质与溶剂、加水蒸发、不同浓度溶液混合',
    '钟表问题': '快慢钟、时针分针夹角与重合、坏钟校准、分针追时针',
}

# 每种结果对应的日志级别
STATUS_LEVEL = {
    'written': logging.INFO,
    'low_confidence': logging.INFO,
    'abstain': logging.INFO,
    'invalid': logging.WARNING,
    'failed': logging.WARNING,
}


@dataclass
class LabelContext:
    """跑一批标注期间不变的东西，集中传递避免参数爆炸"""

    engine: str
    point_lines: list[str]
    point_by_id: dict[int, dict[str, Any]]
    jev_criteria: dict[str, str]
    jev_model: str
    jev_base_url: str
    jev_endpoint: str
    jev_api_key: str
    threshold: Decimal
    jev_rules: bool
    system_id: int
    user_id: int
    max_stem_chars: int
    max_tokens: int
    write: bool
    sleep: float
    http: Any = None
    model: AIModel | None = None
    provider: AIProvider | None = None


# ============ 文本处理 ============


def strip_html(content: str | None) -> str:
    """把富文本题干转成纯文本"""
    if not content:
        return ''
    value = re.sub(r'<br\s*/?>', '\n', str(content), flags=re.IGNORECASE)
    value = re.sub(r'</(p|div|li)>', '\n', value, flags=re.IGNORECASE)
    value = re.sub(r'<[^>]+>', '', value)
    return re.sub(r'\n{2,}', '\n', unescape(value)).strip()


def normalize_options(raw: Any) -> list[tuple[str, str]]:
    """把 option_data 规整成 [(选项号, 选项文本)]，兼容 JSONB 直出与字符串两种情况"""
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    options: list[tuple[str, str]] = []
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            code = item.get('option_code') or item.get('code') or chr(65 + index)
            options.append((str(code), strip_html(item.get('content'))))
        else:
            options.append((chr(65 + index), strip_html(str(item))))
    return options


def to_decimal(value: Any) -> Decimal | None:
    """把模型给的置信度转成能存库的 Decimal"""
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal(DB_PRECISION))
    except (InvalidOperation, TypeError, ValueError):
        return None


def build_stem_block(*, stem: str, options: list[tuple[str, str]], question_type: str | None) -> str:
    """题干 + 本题选项（两个引擎共用的「题目部分」文本）"""
    parts = [f'【题目类型】{question_type or "未知"}', f'【题干】\n{stem}']
    if options:
        rendered = '\n'.join(f'{code}. {content}' for code, content in options)
        parts.append(f'【本题选项】\n{rendered}')
    return '\n\n'.join(parts)


# ============ 引擎 A：chat（项目自带 OpenAI 兼容网关） ============


def build_messages(
    *,
    stem: str,
    options: list[tuple[str, str]],
    question_type: str | None,
    point_lines: list[str],
) -> list[AIChatMessage]:
    """构造一次标注请求的消息"""
    body = [
        build_stem_block(stem=stem, options=options, question_type=question_type),
        '【候选知识点】（只能从中选一个）\n' + '\n'.join(point_lines),
        CLASSIFY_RULES,
        '请返回 JSON：{"point_id": <候选里的 id，都不合适则为 null>, '
        '"confidence": <0 到 1 之间的数字>, "reason": "<20 字以内的理由>"}',
    ]
    return [
        AIChatMessage(role='system', content=SYSTEM_PROMPT),
        AIChatMessage(role='user', content='\n\n'.join(body)),
    ]


async def resolve_model(db: Any, *, model_name: str | None, provider_id: int | None) -> tuple[AIModel, AIProvider]:
    """取要用的模型与供应商；不指定时自动取一个已启用的"""
    stmt = (
        select(AIModel, AIProvider)
        .join(AIProvider, AIProvider.id == AIModel.provider_id)
        .where(AIModel.status == 1, AIProvider.status == 1)
    )
    if model_name:
        stmt = stmt.where(AIModel.model_id == model_name)
    if provider_id:
        stmt = stmt.where(AIProvider.id == provider_id)
    row = (await db.execute(stmt.order_by(AIModel.id.desc()).limit(1))).first()
    if row is None:
        raise SystemExit('没有可用的 AI 模型，请先在后台配置供应商与模型（或用 --model / --provider-id 指定）')
    return row[0], row[1]


async def classify_chat(
    *,
    db: Any,
    model: AIModel,
    provider: AIProvider,
    messages: list[AIChatMessage],
    max_tokens: int,
) -> tuple[int | None, Decimal | None, str]:
    """调一次 chat 模型，返回 (知识点 id, 置信度, 理由)"""
    response = await ai_chat_service.raw_chat(
        db=db,
        chat=AIChat(
            provider_id=provider.id,
            model_id=model.model_id,
            messages=messages,
            temperature=0.2,
            max_tokens=max_tokens,
        ),
    )
    payload = EvaluationService._extract_json_payload(EvaluationService._extract_text_content(response))

    raw_id = payload.get('point_id')
    point_id: int | None = None
    if isinstance(raw_id, (int, float)) and raw_id is not None:
        point_id = int(raw_id)
    elif isinstance(raw_id, str) and raw_id.strip().isdigit():
        point_id = int(raw_id.strip())

    return point_id, to_decimal(payload.get('confidence')), str(payload.get('reason') or '').strip()


# ============ 引擎 B：jev（TypeSafe AI 的 Choice 原语） ============


def build_jev_criteria(
    points: list[dict[str, Any]], *, with_other: bool = True, with_hints: bool = True
) -> dict[str, str]:
    """Jev 的 criteria：key 就是选项名（模型看得到），描述写完整路径最有用。

    `with_other` 控制要不要挂 other 兜底项。**封闭场景（题已按章节筛过，必然属于候选之一）
    建议关掉** —— 实测挂着 other 会让模型把 15%~25% 的题推给它，关掉后这些题都会回到正确类别。
    """
    if len(points) + (1 if with_other else 0) > JEV_MAX_OPTIONS:
        raise SystemExit(
            f'Jev 单个 Choice 最多 {JEV_MAX_OPTIONS} 个选项，当前候选 {len(points)} 个；'
            '请加 --leaves-only，或缩小到某个下级体系再跑'
        )
    criteria: dict[str, str] = {}
    for point in points:
        base = point['path_text'] or point['name']
        hint = JEV_CRITERIA_HINTS.get(point['name']) if with_hints else None
        criteria[str(point['id'])] = f'{base}：{hint}' if hint else base
    if with_other:
        criteria[JEV_OTHER_KEY] = JEV_OTHER_DESC
    return criteria


def build_jev_payload(*, state: str, criteria: dict[str, str], model: str, with_rules: bool = True) -> dict[str, Any]:
    """构造 Jev 请求体（官方 /v1/systemone 与 OpenRouter /alpha/decisions 的格式一致）

    ⚠️ `with_rules` 是**实验开关**：决策模型是「System 1」直觉模型，不做推理链，
    塞一篇几百字的归类规则进去反而可能把它推去选 other（实测见 --no-jev-rules）。
    默认仍带规则（chat 引擎确实靠它提分），但跑 Jev 时**务必两边各跑一次比 other 率**。
    """
    instructions = f'{JEV_INSTRUCTION}\n\n{CLASSIFY_RULES}' if with_rules else JEV_INSTRUCTION
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


def describe_probs(probabilities: Any, point_by_id: dict[int, dict[str, Any]]) -> str:
    """把概率分布压成一行，方便在日志里核对模型是不是「勉强选的」"""
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


async def classify_jev(
    *,
    stem: str,
    options: list[tuple[str, str]],
    question_type: str | None,
    ctx: LabelContext,
) -> tuple[int | None, Decimal | None, str]:
    """调一次 Jev，返回 (知识点 id, 置信度, 说明)"""
    if ctx.http is None:
        raise RuntimeError('HTTP 客户端未初始化')
    payload = build_jev_payload(
        state=build_stem_block(stem=stem, options=options, question_type=question_type),
        criteria=ctx.jev_criteria,
        model=ctx.jev_model,
        with_rules=ctx.jev_rules,
    )
    response = await ctx.http.post(
        ctx.jev_endpoint,
        headers={'Authorization': f'Bearer {ctx.jev_api_key}'},
        json=payload,
    )
    response.raise_for_status()
    answer = (response.json().get('answers') or {}).get(JEV_QUESTION_ID) or {}

    confidence = to_decimal(answer.get('confidence'))
    note = describe_probs(answer.get('probabilities'), ctx.point_by_id)
    choice = str(answer.get('choice') or '').strip()

    if not choice or choice == JEV_OTHER_KEY:
        return None, confidence, note
    if choice.isdigit():
        return int(choice), confidence, note
    return None, confidence, f'返回了未知选项 {choice}；{note}'


# ============ 请求预览（--dry-run） ============


def dump_request(question: dict[str, Any], ctx: LabelContext) -> None:
    """空跑：只打印将要发出的请求，不调模型、不写库"""
    stem = strip_html(question['stem'])[:1200]
    options = normalize_options(question['option_data'])
    log.info('=' * 60)
    log.info(f'空跑：以下是将要发给 {ctx.engine} 的请求（题目 id={question["id"]}）')
    if ctx.engine == 'jev':
        payload = build_jev_payload(
            state=build_stem_block(stem=stem, options=options, question_type=question['question_type']),
            criteria=ctx.jev_criteria,
            model=ctx.jev_model,
        )
        log.info(f'POST {ctx.jev_base_url}{ctx.jev_endpoint}\n{json.dumps(payload, ensure_ascii=False, indent=2)}')
    else:
        for message in build_messages(
            stem=stem,
            options=options,
            question_type=question['question_type'],
            point_lines=ctx.point_lines,
        ):
            log.info(f'--- {message.role} ---\n{message.content}')
    log.info('=' * 60)
    log.info('空跑结束，没有调用模型、没有写库')


# ============ 数据 ============


def build_where(
    *,
    system_id: int,
    bank_ids: list[int],
    question_ids: list[int],
    section_ids: list[int],
    include_labeled: bool,
    overwrite_manual: bool,
) -> tuple[str, dict[str, Any]]:
    """构造题目筛选条件（摘要与主查询共用）"""
    clauses = ['q.deleted = 0']
    params: dict[str, Any] = {'sid': system_id}

    if bank_ids:
        clauses.append(
            'bi.bank_revision_id IN (SELECT r.id FROM qbank_v2_bank_revision r WHERE r.bank_id = ANY(:bank_ids))'
        )
        params['bank_ids'] = bank_ids
    if question_ids:
        clauses.append('q.id = ANY(:question_ids)')
        params['question_ids'] = question_ids
    if section_ids:
        # 只跑某个章节（如「数量关系」）—— 否则按题库筛会把整张卷的言语/判断都拿去标数量关系的候选
        clauses.append('bi.section_id = ANY(:section_ids)')
        params['section_ids'] = section_ids

    if not include_labeled:
        clauses.append(
            'NOT EXISTS (SELECT 1 FROM qbank_v2_question_knowledge_point x '
            'JOIN qbank_v2_knowledge_point kp ON kp.id = x.knowledge_point_id '
            'WHERE x.question_id = q.id AND x.deleted = 0 AND kp.system_id = :sid)'
        )
    elif not overwrite_manual:
        clauses.append(
            'NOT EXISTS (SELECT 1 FROM qbank_v2_question_knowledge_point y '
            'JOIN qbank_v2_knowledge_point kp2 ON kp2.id = y.knowledge_point_id '
            'WHERE y.question_id = q.id AND y.deleted = 0 AND kp2.system_id = :sid '
            "AND y.source = 'manual')"
        )

    return ' AND '.join(clauses), params


async def fetch_points(
    db: Any, system_id: int, *, leaves_only: bool = False, root_id: int | None = None
) -> list[dict[str, Any]]:
    """取本体系的知识点（含完整路径，路径信息对模型判断很有帮助）

    leaves_only=True 时只保留叶子节点 —— 父节点（如「数量关系」）太笼统，让模型选它没有意义。
    root_id 可以把候选**限制在某个子树**内（例如只跑数量关系就传 561）：
    候选越少越准，尤其 Jev 是直觉模型，混进一堆无关选项会明显掉点。
    """
    rows = (
        (
            await db.execute(
                text(
                    'SELECT id, name, path, depth, parent_id FROM qbank_v2_knowledge_point '
                    'WHERE system_id = :sid AND deleted = 0 ORDER BY depth, sort_order, id'
                ),
                {'sid': system_id},
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        raise SystemExit(f'知识体系 {system_id} 下没有知识点')

    if root_id is not None:
        keep = {
            row['id']
            for row in rows
            if str(root_id) in [part for part in str(row['path'] or '').split('.') if part.isdigit()]
        }
        rows = [row for row in rows if row['id'] in keep]
        if not rows:
            raise SystemExit(f'知识体系 {system_id} 下没有属于 {root_id} 子树的知识点')

    name_by_id = {row['id']: row['name'] for row in rows}
    parent_ids = {row['parent_id'] for row in rows if row['parent_id'] is not None}
    selected = [row for row in rows if not leaves_only or row['id'] not in parent_ids]
    if not selected:
        raise SystemExit(f'知识体系 {system_id} 过滤叶子后没有知识点（去掉 --leaves-only 试试）')

    points: list[dict[str, Any]] = []
    for row in selected:
        chain = [
            name_by_id[int(part)]
            for part in str(row['path'] or '').split('.')
            if part.isdigit() and int(part) in name_by_id
        ]
        points.append({
            'id': row['id'],
            'name': row['name'],
            'depth': row['depth'],
            'path_text': ' > '.join(chain),
        })
    return points


async def fetch_summary(db: Any, where: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """按题库汇总待处理题量 —— 落库前先让人看清这批题到底是什么域的东西"""
    sql = f"""
        SELECT r.bank_id,
               r.name AS bank_name,
               COALESCE(string_agg(DISTINCT c.name, ' / '), '(无分类)') AS categories,
               count(DISTINCT q.id) AS questions
        FROM qbank_v2_question q
        JOIN qbank_v2_bank_item bi ON bi.question_id = q.id AND bi.deleted = 0
        JOIN qbank_v2_bank_revision r ON r.id = bi.bank_revision_id
        LEFT JOIN qbank_v2_bank_category bc ON bc.bank_id = r.bank_id AND bc.deleted = 0
        LEFT JOIN sys_category c ON c.id = bc.category_id
        WHERE {where}
        GROUP BY r.bank_id, r.name
        ORDER BY questions DESC
    """
    return [dict(row) for row in (await db.execute(text(sql), params)).mappings().all()]


async def fetch_questions(db: Any, where: str, params: dict[str, Any], limit: int, offset: int) -> list[dict[str, Any]]:
    """取待标注的题目"""
    sql = f"""
        SELECT DISTINCT q.id, q.stem, q.question_type, q.option_data
        FROM qbank_v2_question q
        JOIN qbank_v2_bank_item bi ON bi.question_id = q.id AND bi.deleted = 0
        WHERE {where}
        ORDER BY q.id
        LIMIT :limit OFFSET :offset
    """
    rows = (await db.execute(text(sql), {**params, 'limit': limit, 'offset': offset})).mappings().all()
    return [dict(row) for row in rows]


# ============ 单题处理 ============


async def call_engine(
    *, db: Any, question: dict[str, Any], ctx: LabelContext
) -> tuple[int | None, Decimal | None, str]:
    """按引擎分派一次标注调用"""
    stem = strip_html(question['stem'])[: ctx.max_stem_chars]
    options = normalize_options(question['option_data'])
    if ctx.engine == 'jev':
        return await classify_jev(stem=stem, options=options, question_type=question['question_type'], ctx=ctx)
    messages = build_messages(
        stem=stem,
        options=options,
        question_type=question['question_type'],
        point_lines=ctx.point_lines,
    )
    if ctx.model is None or ctx.provider is None:
        raise RuntimeError('chat 引擎的模型未初始化')
    return await classify_chat(
        db=db, model=ctx.model, provider=ctx.provider, messages=messages, max_tokens=ctx.max_tokens
    )


async def label_one(*, db: Any, question: dict[str, Any], ctx: LabelContext) -> tuple[str, str]:
    """处理一题，返回 (状态, 日志文本)。状态取值见 STATUS_LEVEL"""
    question_id = question['id']
    try:
        point_id, confidence, reason = await call_engine(db=db, question=question, ctx=ctx)
    except Exception as exc:  # 单题失败不该中断整批
        return 'failed', f'id={question_id} 调用失败：{exc}'

    if point_id is None:
        return 'abstain', f'id={question_id} 模型认为都不合适（置信度 {confidence}）{reason}'

    point = ctx.point_by_id.get(point_id)
    if point is None:
        return 'invalid', f'id={question_id} 模型返回了不存在的知识点 {point_id}，已忽略'

    label = point['path_text'] or point['name']

    if confidence is None or confidence < ctx.threshold:
        return 'low_confidence', f'id={question_id} 低置信度 {confidence} -> {label}（不写入，留给人工）{reason}'

    if not ctx.write:
        return 'written', f'id={question_id} -> {label}（置信度 {confidence}，未加 --write，未落库）{reason}'

    await question_knowledge_point_dao.replace(
        db,
        question_id=question_id,
        items=[
            KnowledgePointAssignmentParam(
                knowledge_point_id=point_id,
                source='ai',
                confidence=confidence,
            )
        ],
        user_id=ctx.user_id,
        system_id=ctx.system_id,
    )
    await db.commit()
    return 'written', f'id={question_id} -> {label}（已写入，source=ai，置信度 {confidence}）'


async def label_batch(*, db: Any, questions: list[dict[str, Any]], ctx: LabelContext) -> dict[str, int]:
    """逐个标注并统计，单题异常不影响整批"""
    counters = dict.fromkeys(STATUS_LEVEL, 0)
    total = len(questions)
    for index, question in enumerate(questions, start=1):
        status, message = await label_one(db=db, question=question, ctx=ctx)
        counters[status] += 1
        log.log(STATUS_LEVEL[status], f'[{index}/{total}] {message}')
        await asyncio.sleep(ctx.sleep)
    return counters


def report(counters: dict[str, int]) -> None:
    """打印统计"""
    log.info(
        f'结束：写入 {counters["written"]} / 低置信度 {counters["low_confidence"]} / '
        f'模型弃权 {counters["abstain"]} / 非法输出 {counters["invalid"]} / 调用失败 {counters["failed"]}'
    )


# ============ 主流程 ============


async def setup_engine(db: Any, ctx: LabelContext, args: argparse.Namespace) -> None:
    """按引擎准备运行时依赖"""
    if ctx.engine == 'chat':
        ctx.model, ctx.provider = await resolve_model(db, model_name=args.model, provider_id=args.provider_id)
        log.info(f'使用模型：{ctx.model.model_id}（供应商 {ctx.provider.name} / {ctx.provider.api_host}）')
        return
    ctx.http = httpx.AsyncClient(base_url=ctx.jev_base_url, timeout=args.jev_timeout)
    log.info(f'使用 Jev（{args.jev_provider}）：{ctx.jev_model} @ {ctx.jev_base_url}{ctx.jev_endpoint}')


async def run(args: argparse.Namespace) -> None:
    async with async_db_session() as db:
        points = await fetch_points(db, args.system_id, leaves_only=args.leaves_only, root_id=args.root_point_id)
        ctx = LabelContext(
            engine=args.engine,
            point_lines=[f'- id={point["id"]} | {point["path_text"] or point["name"]}' for point in points],
            point_by_id={point['id']: point for point in points},
            jev_criteria=build_jev_criteria(points, with_other=args.jev_other, with_hints=args.jev_hints)
            if args.engine == 'jev'
            else {},
            jev_model=args.jev_model,
            jev_base_url=args.jev_base_url,
            jev_endpoint=args.jev_endpoint,
            jev_api_key=args.jev_api_key,
            threshold=Decimal(str(args.threshold)).quantize(Decimal(DB_PRECISION)),
            jev_rules=args.jev_rules,
            system_id=args.system_id,
            user_id=args.user_id,
            max_stem_chars=args.max_stem_chars,
            max_tokens=args.max_tokens,
            write=args.write,
            sleep=args.sleep,
        )
        log.info(f'知识体系 {args.system_id}：{len(points)} 个候选知识点，引擎 {ctx.engine}，阈值 {ctx.threshold}')

        where, params = build_where(
            system_id=args.system_id,
            bank_ids=args.bank_id or [],
            question_ids=args.question_id or [],
            section_ids=args.section_id or [],
            include_labeled=args.include_labeled,
            overwrite_manual=args.overwrite_manual,
        )

        summary = await fetch_summary(db, where, params)
        log.info('待处理题目的构成（先确认这批题确实属于本体系）：')
        for row in summary:
            log.info(f'  - [{row["bank_id"]}] {row["bank_name"]} | {row["categories"]} | {row["questions"]} 题')

        questions = await fetch_questions(db, where, params, args.limit, args.offset)
        if not questions:
            log.info('没有命中任何题目（可检查 --bank-id / --question-id，或加 --include-labeled）')
            return
        log.info(f'本次实际处理 {len(questions)} 题（limit={args.limit}, offset={args.offset}）')

        if args.dry_run:
            dump_request(questions[0], ctx)
            return

        await setup_engine(db, ctx, args)
        try:
            counters = await label_batch(db=db, questions=questions, ctx=ctx)
        finally:
            if ctx.http is not None:
                await ctx.http.aclose()

        report(counters)
        if not args.write:
            log.info('本次是预演（未加 --write），数据库没有任何改动')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='用模型从本体系知识点里给题目挑一个（单文件脚本）')
    parser.add_argument('--system-id', type=int, required=True, help='知识体系 ID，例如 4（internal）')
    parser.add_argument('--bank-id', type=int, action='append', help='目标题库 ID，可重复传入')
    parser.add_argument('--question-id', type=int, action='append', help='只跑指定题目，可重复传入')
    parser.add_argument('--section-id', type=int, action='append', help='只跑指定章节的题，可重复传入（如数量关系）')
    parser.add_argument('--limit', type=int, default=20, help='本次最多处理多少题（默认 20）')
    parser.add_argument('--offset', type=int, default=0, help='跳过前多少题（默认 0）')
    parser.add_argument('--engine', choices=ENGINES, default='chat', help='chat=项目自带网关；jev=TypeSafe AI（推荐）')
    parser.add_argument('--model', help='chat 引擎的模型 ID，不传则自动取一个已启用的')
    parser.add_argument('--provider-id', type=int, help='chat 引擎的供应商 ID，配合 --model 使用')
    parser.add_argument(
        '--jev-provider',
        choices=tuple(JEV_PRESETS),
        default='typesafe',
        help='jev 走哪家：typesafe=官方直连；vercel=Vercel AI Gateway（官方促销期免费）；openrouter=OpenRouter',
    )
    parser.add_argument(
        '--jev-api-key',
        help='Jev Key；不传则按 provider 读环境变量（AI_GATEWAY_API_KEY / TYPESAFE_API_KEY / OPENROUTER_API_KEY）',
    )
    parser.add_argument('--jev-model', help='Jev 模型名（默认按 --jev-provider 取）')
    parser.add_argument('--jev-base-url', help='Jev 地址（默认按 --jev-provider 取）')
    parser.add_argument('--jev-endpoint', help='Jev 路径（默认按 --jev-provider 取）')
    parser.add_argument(
        '--no-jev-other',
        dest='jev_other',
        action='store_false',
        help='jev 引擎下不加 other 兜底项（题已按章节筛过时用它，模型会被迫在真实类别里选）',
    )
    parser.add_argument(
        '--no-jev-hints',
        dest='jev_hints',
        action='store_false',
        help='jev 引擎下 criteria 只写知识点路径，不加 JEV_CRITERIA_HINTS 的特征词（用于对照描述有多大用）',
    )
    parser.add_argument('--jev-timeout', type=float, default=60.0, help='Jev 单次请求超时秒数（默认 60）')
    parser.add_argument(
        '--no-jev-rules',
        dest='jev_rules',
        action='store_false',
        help='jev 引擎下不把归类规则写进 instructions（决策模型可能被长指令推去选 other，用它做对照）',
    )
    parser.add_argument(
        '--threshold', type=float, default=float(DEFAULT_THRESHOLD), help='置信度阈值，低于它不写入（默认 0.6）'
    )
    parser.add_argument('--max-tokens', type=int, default=512, help='chat 引擎的最大输出 token')
    parser.add_argument('--max-stem-chars', type=int, default=2000, help='题干截断长度（默认 2000 字）')
    parser.add_argument('--sleep', type=float, default=0.2, help='每题之间的间隔秒数（默认 0.2）')
    parser.add_argument('--user-id', type=int, default=1, help='写入时记的 created_by（默认 1）')
    parser.add_argument('--write', action='store_true', help='真正写库；不加则只预演')
    parser.add_argument('--dry-run', action='store_true', help='只打印将要发送的请求，不调模型')
    parser.add_argument('--include-labeled', action='store_true', help='连本体系已标注的题也一起跑')
    parser.add_argument('--leaves-only', action='store_true', help='只把叶子知识点作为候选（推荐，避免模型选到父节点）')
    parser.add_argument(
        '--root-point-id',
        type=int,
        help='把候选限制在该知识点子树内（例如跑数量关系传 561）；候选越少越准，Jev 下尤其明显',
    )
    parser.add_argument('--overwrite-manual', action='store_true', help='允许覆盖 source=manual 的人工标注')
    return parser.parse_args()


def resolve_jev(args: argparse.Namespace) -> None:
    """按 provider 补齐 Jev 的默认连接参数与 Key（命令行 > 环境变量 > 预设）"""
    preset = JEV_PRESETS[args.jev_provider]
    args.jev_base_url = args.jev_base_url or preset['base_url']
    args.jev_endpoint = args.jev_endpoint or preset['endpoint']
    args.jev_model = args.jev_model or preset['model']
    if not args.jev_api_key:
        for name in preset['env_names']:
            if os.environ.get(name):
                args.jev_api_key = os.environ[name]
                break


def main() -> None:
    args = parse_args()
    if not args.bank_id and not args.question_id and not args.section_id:
        raise SystemExit('必须指定 --bank-id / --section-id / --question-id 之一，避免误伤全库')
    if args.engine == 'jev':
        resolve_jev(args)
        if not args.jev_api_key and not args.dry_run:
            preset = JEV_PRESETS[args.jev_provider]
            env_hint = ' 或 '.join(preset['env_names'])
            raise SystemExit(
                f'jev 引擎（{args.jev_provider}）需要 API Key：{preset["signup"]}\n'
                f'拿到后设环境变量 {env_hint}，或传 --jev-api-key'
            )
    if args.overwrite_manual and not args.write:
        log.warning('--overwrite-manual 已开启，但没加 --write，不会有实际覆盖')
    start = time.time()
    asyncio.run(run(args))
    log.info(f'耗时 {time.time() - start:.1f}s')


if __name__ == '__main__':
    main()
