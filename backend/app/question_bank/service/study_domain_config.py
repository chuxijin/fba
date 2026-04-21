#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

STUDY_DOMAIN_APP_CODE = 'youanshang'
STUDY_DOMAIN_DEFAULT_CODE = 'gongkao'

STUDY_DOMAIN_CONFIG: dict[str, dict[str, Any]] = {
    'cet': {
        'label': '四六级',
        'root_codes': {
            'product_catalog': ['pc_cet'],
            'knowledge_point': ['kp_cet'],
            'resource_exam': ['re_cet'],
        },
    },
    'kaoyan': {
        'label': '考研',
        'root_codes': {
            'product_catalog': ['pc_kaoyan'],
            'knowledge_point': ['kp_kaoyan'],
            'resource_exam': ['re_kaoyan'],
        },
    },
    'gongkao': {
        'label': '考公',
        'root_codes': {
            'product_catalog': ['pc_guokao', 'pc_shengkao'],
            'knowledge_point': ['kp_xingce', 'kp_shenlun', 'kp_mianshi'],
            'resource_exam': ['re_guokao', 're_shengkao'],
        },
    },
    'jiaozhi': {
        'label': '教资',
        'root_codes': {
            'product_catalog': [],
            'knowledge_point': [],
            'resource_exam': [],
        },
    },
}


def normalize_study_domain_code(value: Any) -> str:
    """
    规范化领域编码

    :param value: 原始领域值
    :return:
    """
    if isinstance(value, str):
        text = value.strip().lower()
        if text == 'jiaoshi':
            return 'jiaozhi'
        if text in STUDY_DOMAIN_CONFIG:
            return text

    return STUDY_DOMAIN_DEFAULT_CODE


def get_study_domain_label(code: str) -> str:
    """
    获取领域名称

    :param code: 领域编码
    :return:
    """
    normalized_code = normalize_study_domain_code(code)
    return str(STUDY_DOMAIN_CONFIG[normalized_code]['label'])


def get_study_domain_root_codes(code: str) -> dict[str, list[str]]:
    """
    获取领域根分类编码

    :param code: 领域编码
    :return:
    """
    normalized_code = normalize_study_domain_code(code)
    root_codes = STUDY_DOMAIN_CONFIG[normalized_code]['root_codes']
    return {
        'product_catalog': list(root_codes['product_catalog']),
        'knowledge_point': list(root_codes['knowledge_point']),
        'resource_exam': list(root_codes['resource_exam']),
    }
