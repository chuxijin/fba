from backend.common.enums import IntEnum


class AIProviderType(IntEnum):
    """AI 供应商类型"""

    openai = 0
    anthropic = 1
    gemini = 2
    bedrock = 3
    cerebras = 4
    cohere = 5
    groq = 6
    hugging_face = 7
    mistral = 8
    openrouter = 9
    outlines = 10
    #: 决策模型（Jev / System One 协议），**不是** OpenAI 兼容的 chat 路径，
    #: 走 `app/question_bank_v2/service/jev_client.py` 自己直连。
    #: 表里用它区分「这是决策模型还是对话模型」—— 两者的 api_host/调用方式完全不同。
    decision_model = 11
