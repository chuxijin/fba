#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from backend.database.db import async_db_session
from backend.plugin.oc.service.formatter_service import formatter_service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用启动时加载 formatter 缓存"""
    async with async_db_session() as db:
        await formatter_service.load_cache(db)
    yield
