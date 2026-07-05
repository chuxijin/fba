from fastapi import FastAPI
from fastapi.routing import APIRoute


def _iter_api_routes(routes) -> list[APIRoute]:  # noqa: ANN001
    """
    递归获取 API 路由

    :param routes: 路由集合
    :return:
    """
    api_routes: list[APIRoute] = []
    for route in routes:
        if isinstance(route, APIRoute):
            api_routes.append(route)
            continue

        original_router = getattr(route, 'original_router', None)
        if original_router is not None:
            api_routes.extend(_iter_api_routes(original_router.routes))
            continue

        nested_routes = getattr(route, 'routes', None)
        if nested_routes is not None:
            api_routes.extend(_iter_api_routes(nested_routes))

    return api_routes


def simplify_operation_ids(app: FastAPI) -> None:
    """
    简化操作 ID，以便生成的客户端具有更简单的 API 函数名称

    :param app: FastAPI 应用实例
    :return:
    """
    for route in _iter_api_routes(app.routes):
        route.operation_id = route.name


def ensure_unique_route_names(app: FastAPI) -> None:
    """
    检查路由名称是否唯一

    :param app: FastAPI 应用实例
    :return:
    """
    temp_routes = set()
    for route in _iter_api_routes(app.routes):
        if route.name in temp_routes:
            raise ValueError(f'Non-unique route name: {route.name}')
        temp_routes.add(route.name)
