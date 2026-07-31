import time

from backend.common.cache.local import LocalCacheManager


def test_per_entry_ttl_expires_before_global_ttl() -> None:
    cache = LocalCacheManager()
    cache.set('short', {'value': 1}, ttl=0.01)
    assert cache.get('short') == {'value': 1}
    time.sleep(0.02)
    assert cache.get('short') is None


def test_default_entry_keeps_official_behavior() -> None:
    cache = LocalCacheManager()
    cache.set('default', {'value': 1})
    assert cache.get('default') == {'value': 1}
