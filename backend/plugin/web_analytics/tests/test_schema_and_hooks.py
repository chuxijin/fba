from fastapi import FastAPI
from pydantic import ValidationError

from backend.core.conf import settings
from backend.plugin.web_analytics.hooks import setup
from backend.plugin.web_analytics.schema import CollectBatchParam, CreateSiteParam


def test_site_rejects_domain_with_protocol() -> None:
    try:
        CreateSiteParam(name='Example', domains=['https://example.com'])
    except ValidationError:
        pass
    else:
        raise AssertionError('domain with protocol must be rejected')


def test_collect_batch_parses_pageview() -> None:
    batch = CollectBatchParam.model_validate({
        'site': 'wa_12345678',
        'visitor': 'visitor-1234',
        'session': 'session-1234',
        'events': [{'id': 'event-123456', 'type': 'pageview', 'path': '/docs'}],
    })
    assert batch.events[0].type == 'pageview'
    assert batch.events[0].path == '/docs'


def test_setup_registers_public_routes_idempotently() -> None:
    setup(FastAPI())
    setup(FastAPI())
    collect_path = f'{settings.FASTAPI_API_V1_PATH}/analytics/collect'
    assert settings.TOKEN_REQUEST_PATH_EXCLUDE.count(collect_path) == 1
    assert any('analytics/public' in pattern.pattern for pattern in settings.TOKEN_REQUEST_PATH_EXCLUDE_PATTERN)
