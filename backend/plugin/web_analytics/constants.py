from typing import Final

EVENT_PAGEVIEW: Final = 'pageview'
EVENT_HEARTBEAT: Final = 'heartbeat'
EVENT_CLICK: Final = 'click'
EVENT_SCROLL: Final = 'scroll'
EVENT_WEB_VITAL: Final = 'web_vital'
EVENT_CUSTOM: Final = 'custom'

BUILTIN_EVENT_TYPES: Final = {
    EVENT_PAGEVIEW,
    EVENT_HEARTBEAT,
    EVENT_CLICK,
    EVENT_SCROLL,
    EVENT_WEB_VITAL,
    EVENT_CUSTOM,
}

SENSITIVE_QUERY_KEYS: Final = {
    'access_token',
    'auth',
    'code',
    'email',
    'key',
    'password',
    'phone',
    'refresh_token',
    'secret',
    'session',
    'token',
}
