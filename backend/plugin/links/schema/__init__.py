#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.links.schema.domain import (
    CreateDomainParam,
    GetDomainDetail,
    UpdateDomainParam,
)
from backend.plugin.links.schema.dwz import (
    CreateDwzParam,
    GetDwzDetail,
    GetDwzList,
    UpdateDwzParam,
)
from backend.plugin.links.schema.kf import (
    CreateKfItemParam,
    CreateKfParam,
    GetKfDetail,
    GetKfItemDetail,
    GetKfList,
    UpdateKfItemParam,
    UpdateKfParam,
)
from backend.plugin.links.schema.log import (
    CreateLogParam,
    GetLogDetail,
    LogStatistics,
)
from backend.plugin.links.schema.page import (
    CreatePageParam,
    GetPageDetail,
    GetPageList,
    UpdatePageParam,
)
from backend.plugin.links.schema.qun import (
    CreateQunItemParam,
    CreateQunParam,
    GetQunDetail,
    GetQunItemDetail,
    GetQunList,
    UpdateQunItemParam,
    UpdateQunParam,
)

__all__ = [
    # Domain
    'CreateDomainParam',
    'UpdateDomainParam',
    'GetDomainDetail',
    # Dwz
    'CreateDwzParam',
    'UpdateDwzParam',
    'GetDwzDetail',
    'GetDwzList',
    # Qun
    'CreateQunParam',
    'UpdateQunParam',
    'GetQunDetail',
    'GetQunList',
    'CreateQunItemParam',
    'UpdateQunItemParam',
    'GetQunItemDetail',
    # Kf
    'CreateKfParam',
    'UpdateKfParam',
    'GetKfDetail',
    'GetKfList',
    'CreateKfItemParam',
    'UpdateKfItemParam',
    'GetKfItemDetail',
    # Log
    'CreateLogParam',
    'GetLogDetail',
    'LogStatistics',
    # Page
    'CreatePageParam',
    'UpdatePageParam',
    'GetPageDetail',
    'GetPageList',
]
