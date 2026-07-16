#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from prometheus_client import Counter, Histogram

from backend.core.conf import settings

_MYDRIVE_DIRECTORY_CACHE_COUNTER = Counter(
    name='fba_mydrive_directory_cache_total',
    documentation='MyDrive 目录缓存事件总数',
    labelnames=['app_name', 'outcome'],
)

_MYDRIVE_PROVIDER_REQUEST_COUNTER = Counter(
    name='fba_mydrive_provider_request_total',
    documentation='MyDrive Provider 请求总数',
    labelnames=['app_name', 'provider', 'method', 'path', 'outcome'],
)

_MYDRIVE_PROVIDER_REQUEST_COST_TIME_HISTOGRAM = Histogram(
    name='fba_mydrive_provider_request_cost_time',
    documentation='MyDrive Provider 请求耗时（ms）',
    labelnames=['app_name', 'provider', 'method', 'path', 'outcome'],
    buckets=(25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000),
)


def inc_directory_cache(*, outcome: str) -> None:
    """记录目录缓存事件"""
    _MYDRIVE_DIRECTORY_CACHE_COUNTER.labels(
        app_name=settings.GRAFANA_PROMETHEUS_APP_NAME,
        outcome=outcome,
    ).inc()


def observe_provider_request(*, provider: str, method: str, path: str, outcome: str, elapsed: float) -> None:
    """
    记录 Provider 请求结果与耗时。

    :param provider: 网盘 Provider
    :param method: HTTP 方法
    :param path: 固定 API 路径
    :param outcome: 请求结果
    :param elapsed: 请求耗时（毫秒）
    :return:
    """
    labels = {
        'app_name': settings.GRAFANA_PROMETHEUS_APP_NAME,
        'provider': provider,
        'method': method,
        'path': path,
        'outcome': outcome,
    }
    _MYDRIVE_PROVIDER_REQUEST_COUNTER.labels(**labels).inc()
    _MYDRIVE_PROVIDER_REQUEST_COST_TIME_HISTOGRAM.labels(**labels).observe(elapsed)
