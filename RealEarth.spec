# -*- mode: python ; coding: utf-8 -*-
# RealEarth 4.0.0 打包配置
# 单进程 Tkinter 桌面应用，不再依赖 Flask / pywebview / Edge WebView2
from PyInstaller.utils.hooks import collect_all

# 4.0.0 已废弃 Web UI，无需携带 ui-redesign 静态资源
datas = []
binaries = []
hiddenimports = [
    'autostart',
    'providers',
    'providers.geostationary',
    'providers.sdo',
    'providers.fy4',
    'providers.noaa_goes',
    'pystray',
]
tmp_ret = collect_all('PIL')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['flask', 'flask_cors', 'webview', 'server', 'ui-redesign'],
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
)
