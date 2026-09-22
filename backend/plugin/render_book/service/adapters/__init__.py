# -*- coding: utf-8 -*-
from .gongkao_adapter import adapt_gongkao_payload
from .default_adapter import adapt_default_payload
from .practice_adapter import adapt_practice_payload
from .mistake_adapter import adapt_mistake_payload
from .basic_calc_adapter import adapt_basic_calc_payload
from .hanyu_adapter import adapt_hanyu_payload

__all__ = [
    'adapt_gongkao_payload',
    'adapt_default_payload',
    'adapt_practice_payload',
    'adapt_mistake_payload',
    'adapt_basic_calc_payload',
    'adapt_hanyu_payload',
]

