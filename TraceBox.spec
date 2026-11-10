# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets/tracebox.svg", "assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TraceBox",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
)
