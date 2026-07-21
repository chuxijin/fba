#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.plugin.render_book.utils.template_registry import get_template_registry
from backend.plugin.render_book.utils.template_catalog import get_template_catalog, resolve_template_manifest

__all__ = ['get_template_catalog', 'get_template_registry', 'resolve_template_manifest']
