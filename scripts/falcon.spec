# PyInstaller spec — built by scripts/build-release-*.sh (not invoked directly).
import sys
from pathlib import Path

root = Path(SPECPATH).resolve().parent
src = root / "src"

block_cipher = None

hidden = [
    "falcon.analyze",
    "falcon.citations",
    "falcon.cli",
    "falcon.config",
    "falcon.distill",
    "falcon.ingest",
    "falcon.install_paths",
    "falcon.layout",
    "falcon.llm",
    "falcon.log",
    "falcon.models",
    "falcon.native_recorder",
    "falcon.pipeline",
    "falcon.scrub",
    "falcon.segment",
    "falcon.validate",
    "falcon.capture.factory",
    "falcon.capture.frames",
    "falcon.capture.grabber",
    "falcon.capture.recorder",
    "falcon.capture.runner",
    "yaml",
    "PIL",
    "imagehash",
    "httpx",
    "httpcore",
    "anyio",
    "certifi",
]

if sys.platform == "win32":
    hidden.extend(
        [
            "falcon.capture.windows",
            "pywinauto",
            "pywinauto.uia_defines",
            "pywinauto.uia_element_info",
            "win32api",
            "win32gui",
            "win32process",
            "pythoncom",
            "pywintypes",
        ]
    )

if sys.platform == "darwin":
    hidden.extend(
        [
            "falcon.capture.macos",
            "falcon.capture.clicks",
            "falcon.capture.appswitch",
        ]
    )

a = Analysis(
    [str(src / "falcon" / "cli.py")],
    pathex=[str(src)],
    binaries=[],
    datas=[(str(root / "config.toml.example"), ".")],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="falcon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="falcon",
)
