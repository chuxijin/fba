"""从实际供应配置生成 promtool 用例，不启动业务应用或制造生产慢请求。"""

import json
import sys

from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / 'fba_latency_alerts.json'
BUCKETS = [5, 10, 25, 50, 75, 100, 250, 500, 750, 1000, 2500, 5000, 7500, 10000]


def series(path: str, total: str, below_2500: str, below_10000: str, method: str = 'POST') -> list[dict[str, str]]:
    labels = f'app_name="fba_server",path="{path}",method="{method}",status_code="200"'
    result = [{'series': f'fba_request_cost_time_count{{{labels}}}', 'values': total}]
    for bucket in BUCKETS:
        values = '0+0x5' if bucket < 2500 else below_2500 if bucket < 10000 else below_10000
        result.append({'series': f'fba_request_cost_time_bucket{{{labels},le="{bucket}.0"}}', 'values': values})
    result.append({'series': f'fba_request_cost_time_bucket{{{labels},le="+Inf"}}', 'values': total})
    return result


def build() -> dict:
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    group = config['groups'][0]
    rules = group['rules']
    assert group['name'] == 'fba-latency-rules'
    assert len(rules) == 2
    assert {rule['uid'] for rule in rules} == {'efn0g1ul3n4zke', 'fba-low-traffic-slow-request'}
    expressions = []
    for rule in rules:
        data = {item['refId']: item for item in rule['data']}
        assert rule['condition'] == 'C'
        assert data['C']['model']['expression'] == 'D'
        assert data['C']['model']['conditions'][0]['evaluator'] == {'params': [0], 'type': 'gt'}
        assert rule['noDataState'] == 'OK'
        for ref in ['A', 'B', 'D']:
            assert data[ref]['model']['instant'] is True
            assert 'path!="__unmatched__"' in data[ref]['model']['expr']
        expressions.append(data['D']['model']['expr'])
    path = '/api/v1/import-report'
    cases = [
        ('idle', series(path, '0+0x5', '0+0x5', '0+0x5'), [0, 0]),
        ('two requests including nine seconds', series(path, '0 0 0 0 2 2', '0 0 0 0 1 1', '0 0 0 0 2 2'), [0, 0]),
        ('one request over ten seconds', series(path, '0 0 0 0 1 1', '0+0x5', '0+0x5'), [0, 1]),
        ('high traffic and high p95', series(path, '0+6x5', '0+0x5', '0+6x5'), [1, 0]),
        ('exact minimum sample boundary', series(path, '0+4x5', '0+0x5', '0+4x5'), [1, 0]),
        ('high traffic and fast responses', series(path, '0+6x5', '0+6x5', '0+6x5'), [0, 0]),
        ('unknown paths excluded', series('__unmatched__', '0+6x5', '0+0x5', '0+0x5'), [None, None]),
        (
            'original login exclusion preserved',
            series('/api/v1/oauth2/wechat/miniapp/login', '0+6x5', '0+0x5', '0+0x5'),
            [None, None],
        ),
    ]
    tests = []
    for name, inputs, expected in cases:
        tests.append({
            'name': name,
            'interval': '1m',
            'input_series': inputs,
            'promql_expr_test': [
                {
                    'expr': expression,
                    'eval_time': '5m',
                    'exp_samples': []
                    if value is None
                    else [{'labels': f'{{method="POST",path="{path}"}}', 'value': value}],
                }
                for expression, value in zip(expressions, expected, strict=True)
            ],
        })
    mixed = series(path, '0+6x5', '0+0x5', '0+6x5') + series(path, '0+6x5', '0+6x5', '0+6x5', 'GET')
    tests.append({
        'name': 'request methods do not mix',
        'interval': '1m',
        'input_series': mixed,
        'promql_expr_test': [
            {
                'expr': expression,
                'eval_time': '5m',
                'exp_samples': [
                    {'labels': f'{{method="POST",path="{path}"}}', 'value': value},
                    {'labels': f'{{method="GET",path="{path}"}}', 'value': 0},
                ],
            }
            for expression, value in zip(expressions, [1, 0], strict=True)
        ],
    })
    return {'rule_files': [], 'evaluation_interval': '1m', 'tests': tests}


if __name__ == '__main__':
    Path(sys.argv[1]).write_text(json.dumps(build(), ensure_ascii=False, indent=2), encoding='utf-8')
