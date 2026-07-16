#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.mydrive.schema.account import CreateMyDriveAccountParam, GetMyDriveAccountDetail, UpdateMyDriveAccountParam
from backend.app.mydrive.schema.file import GetMyDriveFileDetail
from backend.app.mydrive.schema.space import CreateMyDriveSpaceParam, GetMyDriveSpaceDetail, UpdateMyDriveSpaceParam

__all__ = [
    'CreateMyDriveAccountParam',
    'CreateMyDriveSpaceParam',
    'GetMyDriveAccountDetail',
    'GetMyDriveFileDetail',
    'GetMyDriveSpaceDetail',
    'UpdateMyDriveAccountParam',
    'UpdateMyDriveSpaceParam',
]
