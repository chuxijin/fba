import pytest

from fastapi import FastAPI
from starlette.routing import Match

from backend.app.gongkao.api.v1 import practice_log


@pytest.mark.parametrize(('method', 'path', 'endpoint'), [
    ('GET', '/comparisons', 'get_practice_comparisons'),
    ('GET', '/trends', 'get_practice_log_trends'),
    ('POST', '/import-report', 'import_practice_report'),
    ('GET', '/42', 'get_practice_log'),
    ('PUT', '/42', 'update_practice_log'),
    ('DELETE', '/42', 'delete_practice_log'),
])
def test_report_routes_match_the_expected_handler(method: str, path: str, endpoint: str) -> None:
    scope = {'type': 'http', 'method': method, 'path': path, 'root_path': ''}
    matches = [route for route in practice_log.router.routes if route.matches(scope)[0] == Match.FULL]
    assert len(matches) == 1
    assert matches[0].endpoint.__name__ == endpoint
    if path == '/42':
        assert matches[0].matches(scope)[1]['path_params']['pk'] == 42


def test_detail_route_cannot_consume_a_named_report_path_even_if_registered_first() -> None:
    detail = next(route for route in practice_log.router.routes if route.endpoint is practice_log.get_practice_log)
    for path in ['/comparisons', '/import-report', '/not-a-number']:
        assert detail.matches({'type': 'http', 'method': 'GET', 'path': path, 'root_path': ''})[0] == Match.NONE


def test_openapi_preserves_public_record_urls_and_includes_report_endpoints() -> None:
    app = FastAPI()
    app.include_router(practice_log.router, prefix='/api/v1/gk/practice-logs')
    paths = app.openapi()['paths']
    assert 'get' in paths['/api/v1/gk/practice-logs/comparisons']
    assert 'post' in paths['/api/v1/gk/practice-logs/import-report']
    assert 'get' in paths['/api/v1/gk/practice-logs/{pk}']
