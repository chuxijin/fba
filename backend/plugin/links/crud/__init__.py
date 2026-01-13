#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.links.crud.crud_domain import domain_dao
from backend.plugin.links.crud.crud_dwz import dwz_dao
from backend.plugin.links.crud.crud_kf import kf_dao, kf_item_dao
from backend.plugin.links.crud.crud_log import log_dao
from backend.plugin.links.crud.crud_qun import qun_dao, qun_item_dao

__all__ = [
    'domain_dao',
    'dwz_dao',
    'qun_dao',
    'qun_item_dao',
    'kf_dao',
    'kf_item_dao',
    'log_dao',
]
