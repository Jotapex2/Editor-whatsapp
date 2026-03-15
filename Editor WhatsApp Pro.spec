# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

base_dir = Path(SPEC).resolve().parent
icon_file = str(base_dir / 'icon2.ico')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[(icon_file, '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'jedi', 'pytest', 'PyQt5', 'qtpy'],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Editor WhatsApp Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[icon_file],
)
