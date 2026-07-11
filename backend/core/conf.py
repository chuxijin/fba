#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import shutil

from functools import cache
from re import Pattern
from typing import Any, Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from backend.core.path_conf import ENV_EXAMPLE_FILE_PATH, ENV_FILE_PATH
from backend.plugin.settings_source import PluginSettingsSource


class Settings(BaseSettings):
    """全局配置"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding='utf-8',
        extra='allow',
        case_sensitive=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """自定义配置源优先级"""
        return env_settings, dotenv_settings, PluginSettingsSource(settings_cls)

    # .env 当前环境
    ENVIRONMENT: Literal['dev', 'prod']

    # 机器标识
    MACHINE_ID: str = 'unknown'

    # FastAPI
    FASTAPI_API_V1_PATH: str = '/api/v1'
    FASTAPI_TITLE: str = 'fba'
    FASTAPI_DESCRIPTION: str = 'FastAPI Best Architecture'
    FASTAPI_DOCS_URL: str = '/docs'
    FASTAPI_REDOC_URL: str = '/redoc'
    FASTAPI_OPENAPI_URL: str | None = '/openapi'
    FASTAPI_STATIC_FILES: bool = True

    # .env 数据库
    DATABASE_TYPE: Literal['mysql', 'postgresql']
    DATABASE_HOST: str
    DATABASE_PORT: int
    DATABASE_USER: str
    DATABASE_PASSWORD: str

    # 数据库
    DATABASE_ECHO: bool | Literal['debug'] = False
    DATABASE_POOL_ECHO: bool | Literal['debug'] = False
    DATABASE_SCHEMA: str = 'fba'
    DATABASE_CHARSET: str = 'utf8mb4'
    DATABASE_PK_MODE: Literal['autoincrement', 'snowflake'] = 'autoincrement'

    # .env Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: str
    REDIS_DATABASE: int

    # Redis
    REDIS_TIMEOUT: int = 5  # redis 默认连接超时时间
    REDIS_SOCKET_TIMEOUT: int = 5  # redis socket 连接超时时间
    REDIS_CONNECT_TIMEOUT: int = 5  # redis 连接超时时间

    # 缓存
    CACHE_LOCAL_ENABLED: bool = True
    CACHE_LOCAL_MAXSIZE: int = 100000
    CACHE_LOCAL_TTL: int = 60 * 60 * 2  # 2 小时
    CACHE_REDIS_TTL: int = 60 * 60 * 2  # 2 小时
    CACHE_CONFIG_REDIS_PREFIX: str = 'fba:cache:config'
    CACHE_DICT_REDIS_PREFIX: str = 'fba:cache:dict'
    CACHE_PUBSUB_CHANNEL: str = 'fba:cache:invalidate'
    CACHE_PUBSUB_RECONNECT_DELAY: int = 5  # 重连延迟（秒）
    CACHE_PUBSUB_MAX_RECONNECT_ATTEMPTS: int = 10  # 最大重连次数

    # .env Snowflake
    SNOWFLAKE_ENABLED: bool = False
    SNOWFLAKE_DATACENTER_ID: int | None = None
    SNOWFLAKE_WORKER_ID: int | None = None

    # Snowflake
    SNOWFLAKE_REDIS_PREFIX: str = 'fba:snowflake'
    SNOWFLAKE_HEARTBEAT_INTERVAL_SECONDS: int = 30
    SNOWFLAKE_NODE_TTL_SECONDS: int = 60

    # .env Token
    TOKEN_SECRET_KEY: str  # 密钥 secrets.token_urlsafe(32)

    # Token
    TOKEN_ALGORITHM: str = 'HS256'
    TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24  # 1 天
    TOKEN_REFRESH_EXPIRE_SECONDS: int = 60 * 60 * 24 * 7  # 7 天
    TOKEN_REDIS_PREFIX: str = 'fba:token'
    TOKEN_EXTRA_INFO_REDIS_PREFIX: str = 'fba:token_extra_info'
    TOKEN_ONLINE_REDIS_PREFIX: str = 'fba:token_online'
    TOKEN_REFRESH_REDIS_PREFIX: str = 'fba:refresh_token'
    TOKEN_INVALID_REASON_REDIS_PREFIX: str = 'fba:token_invalid_reason'
    TOKEN_REFRESH_INVALID_REASON_REDIS_PREFIX: str = 'fba:refresh_token_invalid_reason'
    TOKEN_REQUEST_PATH_EXCLUDE: list[str] = [  # JWT / RBAC 路由白名单
        f'{FASTAPI_API_V1_PATH}/auth/login',
        f'{FASTAPI_API_V1_PATH}/auth/refresh',
        f'{FASTAPI_API_V1_PATH}/auth/logout',
        f'{FASTAPI_API_V1_PATH}/auth/wx-login',  # 统一微信登录
        f'{FASTAPI_API_V1_PATH}/auth/test-login',  # 统一测试登录
        f'{FASTAPI_API_V1_PATH}/sys/categories/tree',  # 系统分类树（公开接口）
        f'{FASTAPI_API_V1_PATH}/resources/hot',  # 热门资源（公开接口）
        f'{FASTAPI_API_V1_PATH}/qbank/banks',  # 题库列表（公开接口）
        f'{FASTAPI_API_V1_PATH}/baidupan/oauth/callback',  # 百度网盘 OAuth 回调
        f'{FASTAPI_API_V1_PATH}/actcode/agiso/login',  # 订单号直接登录
        f'{FASTAPI_API_V1_PATH}/actcode/agiso/verify',  # 验证订单号
        f'{FASTAPI_API_V1_PATH}/sms/send_login_code',  # 发送短信验证码
        f'{FASTAPI_API_V1_PATH}/sms/login/sms',  # 短信验证码登录
        f'{FASTAPI_API_V1_PATH}/payment/pay/notify',  # 微信支付回调
        f'{FASTAPI_API_V1_PATH}/payment/pay/refund-notify',  # 微信退款回调
        f'{FASTAPI_API_V1_PATH}/invite/codes/share-config',  # 新增：分享有礼卡片配置免鉴权
        f'{FASTAPI_API_V1_PATH}/notify/send',  # 多渠道通知发送接口（免签放行，便于对接外部 Webhook 比如短信转发）
        f'{FASTAPI_API_V1_PATH}/notify/wecom/callback',  # 企业微信自建应用接收消息回调免鉴权
    ]
    TOKEN_REQUEST_PATH_EXCLUDE_PATTERN: list[Pattern[str]] = [  # JWT / RBAC 路由白名单（正则）
        re.compile(rf'^{FASTAPI_API_V1_PATH}/monitors/(redis|server)$'),
        re.compile(rf'^{FASTAPI_API_V1_PATH}/qbank/banks/\d+$'),  # 题库详情（公开接口）
        re.compile(rf'^{FASTAPI_API_V1_PATH}/resources/\d+/click$'),  # 资源点击统计（公开接口）
        re.compile(rf'^{FASTAPI_API_V1_PATH}/webhook/inbound/[^/]+$'),  # Webhook 入站接收（外部推送免鉴权）
        re.compile(
            rf'^{FASTAPI_API_V1_PATH}/webhook/inbound/structured/[^/]+$'
        ),  # Webhook 结构化入站（外部推送免鉴权）
    ]

    # 用户安全
    USER_BASE_ROLE_ID: int = 1
    USER_LOCK_REDIS_PREFIX: str = 'fba:user:lock'
    USER_LOCK_THRESHOLD: int = 5  # 用户密码错误锁定阈值，0 表示禁用锁定
    USER_LOCK_SECONDS: int = 60 * 5  # 5 分钟
    USER_PASSWORD_EXPIRY_DAYS: int = 365  # 用户密码有效期，0 表示永不过期
    USER_PASSWORD_REMINDER_DAYS: int = 7  # 用户密码到期提醒，0 表示不提醒
    USER_PASSWORD_HISTORY_CHECK_COUNT: int = 3
    USER_PASSWORD_MIN_LENGTH: int = 6
    USER_PASSWORD_MAX_LENGTH: int = 32
    USER_PASSWORD_REQUIRE_SPECIAL_CHAR: bool = False

    # 登录
    LOGIN_CAPTCHA_ENABLED: bool = True
    LOGIN_CAPTCHA_REDIS_PREFIX: str = 'fba:login:captcha'
    LOGIN_CAPTCHA_EXPIRE_SECONDS: int = 60 * 5  # 5 分钟
    LOGIN_FAILURE_PREFIX: str = 'fba:login:failure'

    # JWT
    JWT_USER_REDIS_PREFIX: str = 'fba:user'

    # RBAC
    RBAC_ROLE_MENU_MODE: bool = True
    RBAC_ROLE_MENU_EXCLUDE: list[str] = []

    # 学习规划灰度白名单：用户 ID 列表；空列表表示未启用灰度（全员放行）
    STUDY_PLAN_WHITELIST: list[int] = []

    # Cookie
    COOKIE_REFRESH_TOKEN_KEY: str = 'fba_refresh_token'
    COOKIE_REFRESH_TOKEN_EXPIRE_SECONDS: int = 60 * 60 * 24 * 7  # 7 天

    # 数据权限
    DATA_PERMISSION_MODEL_EXCLUDE: list[str] = [  # 排除允许进行数据过滤的 SQLA 模型
        'DataScope',
        'DataRule',
        'sys_role_data_scope',
        'sys_data_scope_rule',
    ]
    DATA_PERMISSION_COLUMN_EXCLUDE: list[str] = [  # 排除允许进行数据过滤的 SQLA 模型列
        'id',
        'sort',
        'deleted',
        'deleted_time',
        'created_time',
        'updated_time',
    ]
    DATA_PERMISSION_MODEL_TEMPLATE_VARIABLES: list[dict[str, str]] = [  # 数据规则模型可用模板变量
        {'key': '__ALL__', 'comment': '所有模型'},
    ]
    DATA_PERMISSION_COLUMN_TEMPLATE_VARIABLES: list[dict[str, str]] = [  # 数据规则字段可用模板变量
        {'key': '__dept_id__', 'comment': '部门 ID'},
        {'key': '__created_by__', 'comment': '创建者'},
    ]
    DATA_PERMISSION_TEMPLATE_VARIABLES: list[dict[str, str]] = [  # 数据规则值可用模板变量
        {'key': '${user_id}', 'comment': '当前登录用户 ID'},
        {'key': '${dept_id}', 'comment': '当前登录用户部门 ID'},
        {'key': '${now}', 'comment': '当前时间'},
    ]

    # Socket.IO
    WS_NO_AUTH_MARKER: str = 'internal'

    # CORS
    CORS_ALLOWED_ORIGINS: list[str] = [  # 末尾不带斜杠
        'http://127.0.0.1:8000',
        'http://localhost:3000',
        'http://localhost:8080',
        'http://127.0.0.1',
        'http://localhost:5173',
        'http://localhost:5174',
        'http://localhost:5175',
        'http://127.0.0.1:5500',
        'http://localhost:9001',
        'https://zyas.top',
        'https://api.yzxj.vip',
        'https://api-test.yzxj.vip',
        'https://admin.yzxj.vip',
        'https://home.yzxj.vip',
        'https://blog.yzxj.vip',
        'https://static.yzxj.vip',
        'https://ai.yzxj.vip',
    ]
    CORS_EXPOSE_HEADERS: list[str] = [
        'X-Request-ID',
    ]

    # 中间件配置
    MIDDLEWARE_CORS: bool = True

    # 请求限制配置
    REQUEST_LIMITER_REDIS_PREFIX: str = 'fba:limiter'

    # 时间配置
    DATETIME_TIMEZONE: str = 'Asia/Shanghai'
    DATETIME_FORMAT: str = '%Y-%m-%d %H:%M:%S'

    # 文件上传
    UPLOAD_READ_SIZE: int = 1024
    UPLOAD_IMAGE_EXT_INCLUDE: list[str] = ['jpg', 'jpeg', 'png', 'gif', 'webp']
    UPLOAD_IMAGE_SIZE_MAX: int = 5 * 1024 * 1024  # 5 MB
    UPLOAD_VIDEO_EXT_INCLUDE: list[str] = ['mp4', 'mov', 'avi', 'flv']
    UPLOAD_VIDEO_SIZE_MAX: int = 20 * 1024 * 1024  # 20 MB

    # 演示模式配置
    DEMO_MODE: bool = False
    DEMO_MODE_EXCLUDE: set[tuple[str, str]] = {
        ('POST', f'{FASTAPI_API_V1_PATH}/auth/login'),
        ('POST', f'{FASTAPI_API_V1_PATH}/auth/logout'),
        ('GET', f'{FASTAPI_API_V1_PATH}/auth/captcha'),
        ('POST', f'{FASTAPI_API_V1_PATH}/auth/refresh'),
    }

    # IP 定位配置
    IP_LOCATION_PARSE: Literal['online', 'offline', 'false'] = 'offline'
    IP_LOCATION_REDIS_PREFIX: str = 'fba:ip:location'
    IP_LOCATION_EXPIRE_SECONDS: int = 60 * 60 * 24  # 1 天

    # Trace ID
    TRACE_ID_REQUEST_HEADER_KEY: str = 'X-Request-ID'
    TRACE_ID_LOG_LENGTH: int = 32  # UUID 长度，必须小于等于 32
    TRACE_ID_LOG_DEFAULT_VALUE: str = '-'

    # 日志
    LOG_FORMAT: str = (
        '<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</> | <lvl>{level: <8}</> | <cyan>{request_id}</> | <lvl>{message}</>'
    )

    # 日志（控制台）
    LOG_STD_LEVEL: str = 'INFO'

    # 日志（文件）
    LOG_FILE_ACCESS_LEVEL: str = 'INFO'
    LOG_FILE_ERROR_LEVEL: str = 'ERROR'
    LOG_ACCESS_FILENAME: str = 'fba_access.log'
    LOG_ERROR_FILENAME: str = 'fba_error.log'

    # 操作日志
    OPERA_LOG_PATH_EXCLUDE: list[str] = [
        '/favicon.ico',
        '/docs',
        '/redoc',
        '/openapi',
        f'{FASTAPI_API_V1_PATH}/auth/login/swagger',
        f'{FASTAPI_API_V1_PATH}/oauth2/github/callback',
        f'{FASTAPI_API_V1_PATH}/oauth2/google/callback',
        f'{FASTAPI_API_V1_PATH}/baidupan/oauth/callback',
    ]
    OPERA_LOG_REDACT_KEYS: list[str] = [
        'password',
        'old_password',
        'new_password',
        'confirm_password',
    ]
    OPERA_LOG_QUEUE_MAXSIZE: int = 100000
    OPERA_LOG_QUEUE_BATCH_CONSUME_SIZE: int = 100
    OPERA_LOG_QUEUE_TIMEOUT: int = 60  # 1 分钟
    OPERA_LOG_BODY_MAX_SIZE: int = 10240  # 10 KB

    # Server Chan
    SERVER_CHAN_SEND_KEY: str = 'SCT241185TZMzg15OPJD8qIxVo6I0DUGTw'

    # Plugin 配置
    PLUGIN_REQUIRED: list[str] = ['dict']
    PLUGIN_PIP_CHINA: bool = True
    PLUGIN_PIP_INDEX_URL: str = 'https://mirrors.aliyun.com/pypi/simple/'
    PLUGIN_PIP_MAX_RETRY: int = 3
    PLUGIN_REDIS_PREFIX: str = 'fba:plugin'

    # HTTP 请求
    HTTP_REQUEST_TIMEOUT: int = 60  # HTTP 请求超时时间（秒）
    OPENLIST_BASE_URL: str = ''  # OpenList 服务地址
    OPENLIST_TASK_WAIT_TIMEOUT: int = 3600  # OpenList 复制任务等待超时时间（秒）
    OPENLIST_TASK_POLL_INTERVAL: float = 2.0  # OpenList 复制任务轮询间隔（秒）

    # I18n 配置
    I18N_DEFAULT_LANGUAGE: str = 'zh-CN'

    # Grafana
    GRAFANA_METRICS_ENABLE: bool = False
    GRAFANA_OTLP_GRPC_ENDPOINT: str = 'fba_alloy:4317'
    # 以下配置为静态定义，修改后需要手动同步相关 Grafana 配置：
    # - GRAFANA_PROMETHEUS_APP_NAME：deploy/backend/grafana/fba_datasource.yml
    #   deploy/backend/grafana/dashboards/fba_server.json
    # - GRAFANA_CELERY_OTEL_SERVICE_NAME：deploy/backend/grafana/dashboards/fba_celery.json
    # - GRAFANA_METRICS_PATH：deploy/backend/grafana/fba_config.alloy
    #   deploy/backend/grafana/dashboards/fba_server.json
    # - GRAFANA_PROMETHEUS_EXEMPLAR_TRACE_ID_KEY：deploy/backend/grafana/fba_datasource.yml
    GRAFANA_PROMETHEUS_APP_NAME: str = 'fba_server'
    GRAFANA_CELERY_OTEL_SERVICE_NAME: str = 'fba_celery_worker'
    GRAFANA_METRICS_PATH: str = '/metrics'
    GRAFANA_PROMETHEUS_EXEMPLAR_TRACE_ID_KEY: str = 'TraceID'

    ##################################################
    # [ App ] task
    ##################################################
    # .env Redis
    CELERY_BROKER_REDIS_DATABASE: int

    # .env RabbitMQ
    # docker run -d --hostname fba-mq --name fba-mq  -p 5672:5672 -p 15672:15672 rabbitmq:latest
    CELERY_RABBITMQ_HOST: str
    CELERY_RABBITMQ_PORT: int
    CELERY_RABBITMQ_USERNAME: str
    CELERY_RABBITMQ_PASSWORD: str

    # 基础配置
    CELERY_BROKER: Literal['rabbitmq', 'redis'] = 'redis'
    CELERY_RABBITMQ_VHOST: str = ''
    CELERY_REDIS_PREFIX: str = 'fba:celery'
    CELERY_TASK_MAX_RETRIES: int = 5

    ##################################################
    # [ Plugin ] code_generator
    ##################################################
    CODE_GENERATOR_DOWNLOAD_ZIP_FILENAME: str

    ##################################################
    # [ Plugin ] oauth2
    ##################################################
    # .env
    OAUTH2_GITHUB_CLIENT_ID: str
    OAUTH2_GITHUB_CLIENT_SECRET: str
    OAUTH2_GOOGLE_CLIENT_ID: str
    OAUTH2_GOOGLE_CLIENT_SECRET: str

    # 基础配置（in plugin.toml）
    OAUTH2_STATE_REDIS_PREFIX: str
    OAUTH2_STATE_EXPIRE_SECONDS: int
    OAUTH2_GITHUB_REDIRECT_URI: str
    OAUTH2_GOOGLE_REDIRECT_URI: str
    OAUTH2_FRONTEND_LOGIN_REDIRECT_URI: str
    OAUTH2_FRONTEND_BINDING_REDIRECT_URI: str

    ##################################################
    # [ Plugin ] email
    ##################################################
    # .env
    EMAIL_USERNAME: str
    EMAIL_PASSWORD: str

    # 基础配置（in plugin.toml）
    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_SSL: bool
    EMAIL_CAPTCHA_REDIS_PREFIX: str
    EMAIL_CAPTCHA_EXPIRE_SECONDS: int

    ##################################################
    # [ Plugin ] oss 云存储
    ##################################################
    # 基础运行配置（可被 sys_config 覆盖）
    STORAGE_PROVIDER: str = 'aliyun_oss'
    STORAGE_KEY_PREFIX: str = ''
    STORAGE_USE_SIGNED_URL: bool = False
    STORAGE_SIGNED_URL_EXPIRE_SECONDS: int = 300
    STORAGE_OBJECT_EXPIRE_DAYS: int = 0

    # 阿里云 OSS
    OSS_ACCESS_KEY: str = ''
    OSS_SECRET_KEY: str = ''
    OSS_ENDPOINT: str = ''
    OSS_BUCKET_NAME: str = ''
    OSS_USE_SIGNED_URL: bool = True
    OSS_SIGNED_URL_EXPIRE_SECONDS: int = 300

    # 七牛云 Kodo
    QINIU_KODO_ACCESS_KEY: str = ''
    QINIU_KODO_SECRET_KEY: str = ''
    QINIU_KODO_BUCKET: str = ''
    QINIU_KODO_BUCKET_NAME: str = ''
    QINIU_KODO_DOMAIN: str = ''
    QINIU_KODO_USE_HTTPS: bool = True

    ##################################################
    # [ Plugin ] ocr 图片文字识别
    ##################################################
    OCR_PROVIDER: str = 'llama_parse'
    OCR_DOCUMENT_PROVIDER: str = 'llama_parse'
    OCR_IMAGE_MAX_COUNT: int = 3
    OCR_REQUEST_TIMEOUT: int = 20
    OCR_TOKEN_REDIS_PREFIX: str = 'fba:ocr:token'
    OCR_LLAMA_CLOUD_API_KEY: str = ''
    OCR_LLAMA_POLL_INTERVAL_SECONDS: int = 60
    OCR_LLAMA_MAX_POLL_ATTEMPTS: int = 30
    OCR_LLAMA_REQUEST_RETRY_COUNT: int = 3
    OCR_LLAMA_REQUEST_RETRY_DELAY_SECONDS: int = 5
    OCR_LLAMA_CONNECT_TIMEOUT: int = 30
    OCR_LLAMA_READ_TIMEOUT: int = 300
    OCR_LLAMA_WRITE_TIMEOUT: int = 300
    OCR_LLAMA_POOL_TIMEOUT: int = 30
    OCR_LLAMA_TIER: str = 'agentic'
    OCR_LLAMA_VERSION: str = 'latest'
    OCR_LLAMA_CUSTOM_PROMPT: str = (
        '你是一个专业的文档 OCR 和结构化解析助手。'
        '请完整保留公式、题目描述、选项内容、图片和表格位置。'
        '遇到复杂表格时优先保留为图片或稳定的版式内容。'
    )
    OCR_LLAMA_EXPAND: str = 'markdown_full,text_full'
    OCR_LLAMA_IMAGES_TO_SAVE: str = 'embedded'
    OCR_LLAMA_SAVE_IMAGES: bool = True
    OCR_LLAMA_DOWNLOAD_IMAGES: bool = True
    OCR_LLAMA_INLINE_IMAGES: bool = True
    OCR_LLAMA_TABLES_AS_MARKDOWN: bool = True
    OCR_LLAMA_MERGE_CONTINUED_TABLES: bool = True
    OCR_LLAMA_IGNORE_DIAGONAL_TEXT: bool = True
    OCR_LLAMA_IGNORE_TEXT_IN_IMAGE: bool = False
    OCR_LLAMA_IGNORE_HIDDEN_TEXT: bool = True
    OCR_LLAMA_LANGUAGES: str = 'ch_sim,en'
    OCR_LLAMA_COST_OPTIMIZER_ENABLED: bool = True

    BAIDU_OCR_API_KEY: str = ''
    BAIDU_OCR_SECRET_KEY: str = ''
    BAIDU_OCR_HANDWRITING_URL: str = 'https://aip.baidubce.com/rest/2.0/ocr/v1/handwriting'
    BAIDU_OCR_ACCURATE_BASIC_URL: str = 'https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic'
    BAIDU_OCR_GENERAL_BASIC_URL: str = 'https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic'
    BAIDU_OCR_SUBJECTIVE_FALLBACK_ENABLED: bool = True

    ##################################################
    # [ App ] 题库微信小程序
    ##################################################
    # .env 微信小程序配置
    WX_MINIAPP_APPID: str
    WX_MINIAPP_SECRET: str

    # .env 微信 H5 配置（可选）
    WX_H5_APPID: str = ''
    WX_H5_SECRET: str = ''

    ##################################################
    # [ App ] 微信支付 V3
    ##################################################
    PAYMENT_PENDING_ORDER_TIMEOUT_MINUTES: int = 30

    # .env 微信支付配置
    WECHAT_PAY_MCH_ID: str = ''
    WECHAT_PAY_API_V3_KEY: str = ''
    WECHAT_PAY_CERT_SERIAL_NO: str = ''
    WECHAT_PAY_PRIVATE_KEY_PATH: str = ''
    WECHAT_PAY_CERT_PATH: str = ''
    WECHAT_PAY_NOTIFY_URL: str = ''
    WECHAT_PAY_REFUND_NOTIFY_URL: str = ''

    ##################################################
    # [ App ] 微信虚拟支付
    ##################################################
    # .env 微信虚拟支付配置
    VIRTUAL_PAY_OFFERID: str = ''
    VIRTUAL_PAY_APPKEY: str = ''
    VIRTUAL_PAY_SANDBOX_APPKEY: str = ''

    ##################################################
    # OpenAI 向量化服务
    ##################################################
    # .env OpenAI API 配置
    OPENAI_API_KEY: str = ''
    OPENAI_API_BASE: str = ''
    OPENAI_EMBEDDING_MODEL: str = 'text-embedding-3-small'

    ##################################################
    # 敏感词过滤
    ##################################################
    # 敏感词列表（用于过滤资源介绍等内容）
    SENSITIVE_WORDS: list[str] = [
        # 示例敏感词，请根据实际需求添加
        '政治敏感词',
        '色情',
        '赌博',
        '暴力',
        '违法',
        # 添加更多敏感词...
    ]

    ##################################################
    # [ Plugin ] agiso
    ##################################################
    # .env 阿奇索配置
    AGISO_APP_SECRET: str = ''
    AGISO_BATCH_RULES: list[dict[str, Any]] = []  # 兼容旧 plugin.toml 配置，优先使用 sys_config

    ##################################################
    # [ Plugin ] notify 多渠道通知
    ##################################################
    NOTIFY_CHANNEL_PRIORITY: list[str]
    NOTIFY_TIMEOUT: int
    NOTIFY_MAX_TITLE_LENGTH: int
    # 钉钉机器人
    NOTIFY_DINGTALK_ENABLED: bool
    NOTIFY_DINGTALK_API_URL: str
    NOTIFY_DINGTALK_ACCESS_TOKEN: str = ''  # .env
    NOTIFY_DINGTALK_SECRET: str = ''  # .env
    # SMTP 邮件
    NOTIFY_SMTP_ENABLED: bool
    NOTIFY_SMTP_HOST: str
    NOTIFY_SMTP_PORT: int
    NOTIFY_SMTP_SSL: bool
    NOTIFY_SMTP_USERNAME: str = ''  # .env
    NOTIFY_SMTP_PASSWORD: str = ''  # .env
    NOTIFY_SMTP_RECIPIENTS: list[str] = []  # .env
    # Server 酱（使用 serverchan-sdk）
    NOTIFY_SERVERCHAN_ENABLED: bool
    NOTIFY_SERVERCHAN_SEND_KEY: str = ''  # .env
    # Telegram Bot
    NOTIFY_TELEGRAM_ENABLED: bool
    NOTIFY_TELEGRAM_API_URL: str
    NOTIFY_TELEGRAM_BOT_TOKEN: str = ''  # .env
    NOTIFY_TELEGRAM_CHAT_ID: str = ''  # .env
    # 企业微信机器人
    NOTIFY_WECOM_ENABLED: bool
    NOTIFY_WECOM_API_URL: str
    NOTIFY_WECOM_WEBHOOK_KEY: str = ''  # .env

    # 企业微信自建应用推送
    NOTIFY_WECOM_APP_ENABLED: bool
    NOTIFY_WECOM_APP_CORPID: str = ''  # .env
    NOTIFY_WECOM_APP_CORPSECRET: str = ''  # .env
    NOTIFY_WECOM_APP_AGENTID: int = 0  # .env
    NOTIFY_WECOM_APP_TOUSER: str = '@all'  # .env
    NOTIFY_WECOM_APP_MSGTYPE: str = 'markdown'
    NOTIFY_WECOM_APP_TOKEN: str = ''  # .env
    NOTIFY_WECOM_APP_ENCODING_AES_KEY: str = ''  # .env

    ##################################################
    # [ Plugin ] baidupan 百度网盘开放平台
    ##################################################
    # .env 百度网盘配置
    BAIDUPAN_APP_KEY: str = ''  # 应用 AppKey
    BAIDUPAN_SECRET_KEY: str = ''  # 应用 SecretKey
    BAIDUPAN_SIGN_KEY: str = ''  # 应用 SignKey（用于接口签名）
    BAIDUPAN_REDIRECT_URI: str = ''  # OAuth 回调地址

    ##################################################
    # [ App ] Jia 推送服务
    ##################################################
    # Firebase 服务账号凭证 JSON 文件路径
    FIREBASE_CREDENTIALS_PATH: str = ''

    ##################################################
    # [ App ] Halo 博客
    ##################################################
    HALO_BASE_URL: str = ''
    HALO_PAT: str = ''

    ##################################################
    # [ App ] Halo 博客数据库（直接读取 Docsme 文档）
    ##################################################
    HALO_DB_HOST: str = '127.0.0.1'
    HALO_DB_PORT: int = 3307
    HALO_DB_USER: str = 'root'
    HALO_DB_PASSWORD: str = ''
    HALO_DB_NAME: str = 'halo'
    RESPONSE_ENCRYPT_ENABLED: bool = False
    RESPONSE_ENCRYPT_SECRET_KEY: str = ''  # AES 密钥，32 字符 hex 字符串（16 bytes）
    RESPONSE_ENCRYPT_INCLUDE: list[str] = []  # 加密路径前缀，为空则加密所有 API 路径

    ##################################################
    # [ App ] Jia 文档加密
    ##################################################
    DOC_ENCRYPT_SECRET_KEY: str = ''

    ##################################################
    # [ Plugin ] sms 短信服务
    ##################################################
    # 服务商选择: tencent / smsbao
    SMS_PROVIDER: str = 'tencent'

    # 通用配置
    SMS_LOGIN_REDIS_PREFIX: str = 'fba:sms:login'
    SMS_LOGIN_EXPIRE_SECONDS: int = 300  # 短信验证码有效期，5 分钟
    SMS_PHONE_CHANGE_REDIS_PREFIX: str = 'fba:sms:phone_change'  # 更换手机号验证码前缀
    SMS_LOGIN_TEMPLATE_ID: str = ''  # 短信登录模板 ID
    SMS_SIGN_NAME: str = ''  # 短信签名
    SMS_SDK_APP_ID: str = ''  # 短信应用 ID

    # .env 腾讯云短信
    TENCENTCLOUD_SECRET_ID: str = ''
    TENCENTCLOUD_SECRET_KEY: str = ''

    # .env 短信宝
    SMSBAO_USERNAME: str = ''  # 短信宝账号
    SMSBAO_API_KEY: str = ''  # 短信宝 ApiKey（后台获取，比密码 MD5 更安全）
    SMSBAO_CONTENT_TEMPLATE: str = ''  # 自定义短信内容模板（可选）

    ##################################################
    # [ App ] 超级考研代理开通
    ##################################################
    CHAOJI_KAOYAN_BASE_URL: str = 'https://www.chaojikaoyan.com'
    CHAOJI_KAOYAN_AGENT_TEL: str = ''
    CHAOJI_KAOYAN_AGENT_KEY: str = ''
    CHAOJI_KAOYAN_ORDER_TYPE: int = 6
    CHAOJI_KAOYAN_REQUEST_TIMEOUT: int = 20

    @model_validator(mode='before')
    @classmethod
    def check_env(cls, values: Any) -> Any:
        """检查环境变量"""
        if values.get('ENVIRONMENT') == 'prod':
            # FastAPI
            values['FASTAPI_OPENAPI_URL'] = None
            values['FASTAPI_STATIC_FILES'] = False

            # task
            values['CELERY_BROKER'] = 'rabbitmq'

        return values


@cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    if not ENV_FILE_PATH.exists():
        shutil.copy(ENV_EXAMPLE_FILE_PATH, ENV_FILE_PATH)
    return Settings()


# 创建全局配置实例
settings = get_settings()
