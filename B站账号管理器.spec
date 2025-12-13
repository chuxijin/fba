# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['my_app\\main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['bilibili_api.clients', 'bilibili_api.clients.HTTPXClient', 'bilibili_api.clients.AiohttpClient', 'httpx', 'aiohttp'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='B站账号管理器',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='E:\\500-SystemFile\\AppData\\Local\\Temp\\fb9af862-8912-48df-b298-8f5d21d73072',
)
