#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest

from backend.common.exception.errors import RequestError
from backend.plugin.oss.service.storage_service import storage_service


def test_normalize_path_basic() -> None:
    assert storage_service._normalize_path('test/2026/03') == 'test/2026/03'
    assert storage_service._normalize_path('\\test\\images\\') == 'test/images'


def test_normalize_path_reject_parent() -> None:
    with pytest.raises(RequestError):
        storage_service._normalize_path('../secret')


def test_build_object_key() -> None:
    object_key = storage_service._build_object_key('root', 'test/dir', 'a.png')
    assert object_key == 'root/test/dir/a.png'


def test_resolve_expire_values() -> None:
    assert storage_service._resolve_signed_url_expire(600, 300) == 600
    assert storage_service._resolve_object_expire_days(7, None) == 7
    assert storage_service._resolve_object_expire_days(0, 7) is None
