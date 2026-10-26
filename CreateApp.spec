# Build on the target OS/architecture. The end user does not need Python.
from pathlib import Path

root = Path(SPECPATH)
datas = [(str(root / name), name) for name in ('web', 'source-cache', 'third-party')]
datas += [(str(root / name), '.') for name in ('sources.lock.json', 'LICENSE', 'THIRD_PARTY.md')]
a = Analysis([str(root / 'createapp.py')], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=['questionary', 'csv', 'difflib', 'math', 'statistics'],
    hookspath=[], runtime_hooks=[], excludes=['tkinter', 'unittest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='createapp', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, console=True,
    disable_windowed_traceback=False, argv_emulation=False)
