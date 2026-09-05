from backend.plugin.web_analytics.schema import CreateSiteParam
from backend.plugin.web_analytics.service.security import (
    anonymize_ip,
    domain_allowed,
    sanitize_properties,
    sanitize_url,
    source_host,
)


def test_domain_validation_and_matching() -> None:
    site = CreateSiteParam(name='Example', domains=['Example.COM', 'stats.example.com'])
    assert site.domains == ['example.com', 'stats.example.com']
    assert domain_allowed('www.example.com', site.domains)
    assert not domain_allowed('example.com.attacker.test', site.domains)


def test_source_host_prefers_origin() -> None:
    assert source_host('https://app.example.com', 'https://other.test/page') == 'app.example.com'
    assert source_host(None, 'https://blog.example.com/post') == 'blog.example.com'


def test_anonymize_ip_uses_network_prefix() -> None:
    assert anonymize_ip('192.168.10.99') == '192.168.10.0'
    assert anonymize_ip('2001:db8:abcd:1234::1') == '2001:db8:abcd::'
    assert anonymize_ip('invalid') == 'unknown'


def test_sanitize_url_removes_fragment_and_secrets() -> None:
    value = sanitize_url('https://example.com/path?utm_source=test&token=secret#private')
    assert value == 'https://example.com/path?utm_source=test&token=%5Bredacted%5D'


def test_sanitize_properties_redacts_and_limits_values() -> None:
    value = sanitize_properties({'token': 'secret', 'plan': 'pro', 'nested': {'key': 'value'}})
    assert value == {'token': '[redacted]', 'plan': 'pro', 'nested': '{"key":"value"}'}
