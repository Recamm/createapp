"""Paths that work both from source and inside a standalone executable."""
import os
from pathlib import Path
import sys

VERSION = "0.2.0"
DATA = Path(__file__).resolve().parent

def cache_dir():
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "CreateApp/blobs"

def project_defaults(project):
    import copy
    import re
    from catalog import DEFAULTS
    result = copy.deepcopy(DEFAULTS)
    name = re.sub(r"[^a-z0-9-]+", "-", Path(project).name.lower()).strip("-")[:60]
    result["name"] = name or "mi-app"
    return result
