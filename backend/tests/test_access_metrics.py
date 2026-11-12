from collections.abc import Iterator
from unittest.mock import Mock

import pytest

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.testclient import TestClient
from starlette_context.middleware import ContextMiddleware

from backend.middleware import access_middleware
from backend.middleware.access_middleware import AccessMiddleware, resolve_request_path_template

TEMPLATE = '/api/v1/metrics-test/sessions/{session_key}'


def make_app() -> FastAPI:
    app = FastAPI()
    sessions = APIRouter()

    @sessions.post('/sessions/{session_key}', status_code=201)
    async def create_session(session_key: str) -> dict[str, str]:
        return {'session_key': session_key}

    @sessions.get('/failure')
    async def failure() -> None:
        raise HTTPException(status_code=500, detail='test failure')

    api = APIRouter(prefix='/v1')
    api.include_router(sessions, prefix='/metrics-test')
    app.include_router(api, prefix='/api')
    return app


def make_request(app: FastAPI, path: str, method: str = 'POST') -> Request:
    return Request({'type': 'http', 'method': method, 'path': path, 'root_path': '', 'app': app})


@pytest.mark.parametrize('session_key', ['abc123', 'different-user-value'])
def test_nested_include_prefixes_and_dynamic_values_use_one_template(session_key: str) -> None:
    request = make_request(make_app(), f'/api/v1/metrics-test/sessions/{session_key}')
    assert resolve_request_path_template(request) == TEMPLATE
    assert 'route' not in request.scope
    assert 'path_params' not in request.scope


def test_one_router_included_twice_keeps_each_effective_prefix() -> None:
    app = FastAPI()
    router = APIRouter()

    @router.get('/items/{item_id}')
    async def item(item_id: str) -> str:
        return item_id

    app.include_router(router, prefix='/api/v1/first')
    app.include_router(router, prefix='/api/v1/second')
    for prefix in ['first', 'second']:
        request = make_request(app, f'/api/v1/{prefix}/items/42', 'GET')
        assert resolve_request_path_template(request) == f'/api/v1/{prefix}/items/{{item_id}}'


def test_flat_routes_keep_existing_labels() -> None:
    app = FastAPI()

    async def item(item_id: str) -> str:  # noqa: RUF029
        return item_id

    app.router.routes.append(APIRoute('/api/v1/items/{item_id}', item, methods=['GET']))
    assert resolve_request_path_template(make_request(app, '/api/v1/items/42', 'GET')) == '/api/v1/items/{item_id}'


@pytest.mark.parametrize('path', ['/api/v1/unknown/random-value', '/api/v1/metrics-test/sessions/42'])
def test_unknown_paths_and_wrong_methods_remain_fixed_labels(path: str) -> None:
    assert resolve_request_path_template(make_request(make_app(), path, 'DELETE')) == '__unmatched__'


@pytest.fixture
def metrics(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Mock]]:
    monkeypatch.setattr(access_middleware.settings, 'GRAFANA_METRICS_ENABLE', True)
    names = [
        'inc_fastapi_request_in_progress',
        'inc_fastapi_request',
        'observe_fastapi_request_cost_time',
        'inc_fastapi_response',
        'dec_fastapi_request_in_progress',
    ]
    recorders = {name: Mock() for name in names}
    for name, recorder in recorders.items():
        monkeypatch.setattr(access_middleware, name, recorder)
    yield recorders


@pytest.mark.parametrize(
    ['method', 'path', 'status_code', 'template'],
    [
        ['POST', '/api/v1/metrics-test/sessions/42', 201, TEMPLATE],
        ['GET', '/api/v1/metrics-test/failure', 500, '/api/v1/metrics-test/failure'],
        ['GET', '/api/v1/unknown/random-value', 404, '__unmatched__'],
        ['DELETE', '/api/v1/metrics-test/sessions/42', 405, '__unmatched__'],
    ],
)
def test_middleware_records_balanced_template_labels(
    metrics: dict[str, Mock], method: str, path: str, status_code: int, template: str
) -> None:
    app = make_app()
    app.add_middleware(AccessMiddleware)
    app.add_middleware(ContextMiddleware)
    with TestClient(app) as client:
        assert client.request(method, path).status_code == status_code
    for recorder in metrics.values():
        recorder.assert_called_once()
        assert recorder.call_args.kwargs['path'] == template
        assert recorder.call_args.kwargs['method'] == method
    assert metrics['inc_fastapi_response'].call_args.kwargs['status_code'] == status_code


def test_authentication_short_circuit_still_records_known_route(metrics: dict[str, Mock]) -> None:
    class RejectBeforeRouting(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            return Response(status_code=401)

    app = make_app()
    app.add_middleware(RejectBeforeRouting)
    app.add_middleware(AccessMiddleware)
    app.add_middleware(ContextMiddleware)
    with TestClient(app) as client:
        assert client.post('/api/v1/metrics-test/sessions/42').status_code == 401
    for recorder in metrics.values():
        recorder.assert_called_once()
        assert recorder.call_args.kwargs['path'] == TEMPLATE
