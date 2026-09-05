import re

from fastapi import FastAPI

from backend.core.conf import settings


def setup(app: FastAPI) -> None:
    """Register public collector routes in the global authentication whitelist."""
    del app
    public_paths = {
        f'{settings.FASTAPI_API_V1_PATH}/analytics/collect',
        f'{settings.FASTAPI_API_V1_PATH}/analytics/replay',
        f'{settings.FASTAPI_API_V1_PATH}/analytics/script.js',
    }
    for path in public_paths:
        if path not in settings.TOKEN_REQUEST_PATH_EXCLUDE:
            settings.TOKEN_REQUEST_PATH_EXCLUDE.append(path)
    pattern_text = rf'^{settings.FASTAPI_API_V1_PATH}/analytics/public/[^/]+/counter$'
    if not any(pattern.pattern == pattern_text for pattern in settings.TOKEN_REQUEST_PATH_EXCLUDE_PATTERN):
        settings.TOKEN_REQUEST_PATH_EXCLUDE_PATTERN.append(re.compile(pattern_text))
