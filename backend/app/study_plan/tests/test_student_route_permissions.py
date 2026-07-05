#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi.routing import APIRoute

from backend.app.study_plan.api.v1.student import router
from backend.app.study_plan.utils.permission import DependsStudyPlanWhitelist


def _find_route(path: str, method: str) -> APIRoute:
    """
    查找学员端路由

    :param path: 路由路径
    :param method: HTTP 方法
    :return:
    """
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == path and method in route.methods:
            return route

    raise AssertionError(f'未找到路由: {method} {path}')


def _has_study_plan_whitelist(route: APIRoute) -> bool:
    """
    判断路由是否包含学习规划白名单依赖

    :param route: API 路由
    :return:
    """
    return any(dependency.call is DependsStudyPlanWhitelist for dependency in route.dependant.dependencies)


def test_ability_routes_do_not_require_study_plan_whitelist() -> None:
    """能力练习独立接口不应要求学习规划白名单"""
    public_ability_routes = [
        ('GET', '/ability-catalog'),
        ('POST', '/ability-attempts'),
        ('POST', '/ability-attempts/batch-sync'),
        ('GET', '/ability-attempts'),
        ('GET', '/ability-attempts/{client_session_id}'),
        ('GET', '/ability-profile'),
    ]

    for method, path in public_ability_routes:
        route = _find_route(path, method)
        assert not _has_study_plan_whitelist(route)


def test_study_plan_routes_require_study_plan_whitelist() -> None:
    """学习规划接口应保留白名单限制"""
    protected_plan_routes = [
        ('GET', '/today'),
        ('GET', '/items/{item_id}'),
        ('POST', '/items/{item_id}/start'),
        ('POST', '/items/{item_id}/complete'),
        ('GET', '/me/plans'),
        ('GET', '/me/uncompleted-count'),
        ('GET', '/me/plans/{plan_id}/items'),
        ('GET', '/me/plans/{plan_id}/progress'),
    ]

    for method, path in protected_plan_routes:
        route = _find_route(path, method)
        assert _has_study_plan_whitelist(route)
