# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [('ui-redesign/index.html', '.'), ('ui-redesign/logo.png', '.'), ('ui-redesign/logo.ico', '.')]
binaries = []
hiddenimports = [
    'server', 'autostart', 'providers', 'providers.geostationary', 'providers.sdo', 'providers.fy4',
    'pystray', 'flask', 'flask_cors', 'webview',
    # pywebview Windows 平台依赖
    'pythoncom', 'win32com', 'win32com.client', 'win32api', 'win32con', 'win32gui',
    'win32process', 'win32event',
]

# 收集 PIL 所有子模块 + 数据
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# 收集 pywebview 所有子模块（platforms.win32 等）
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# 收集 pywin32 / win32com 所有子模块
tmp_ret = collect_all('win32com')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_submodules('pythoncom')
hiddenimports += tmp_ret

tmp_ret = collect_submodules('win32')
hiddenimports += tmp_ret


a = Analysis(
    ['launcher.py'],
    pathex=['ui-redesign'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='RealEarth',
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
    icon='ui-redesign/logo.ico',
)
