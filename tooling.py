"""Use the selected UI/UX search scripts with the executable's embedded Python."""
import csv  # Collected by PyInstaller for the dynamically loaded upstream search.
import runpy
from pathlib import Path
import sys
from engine import ConfigError, LOCK, blob_hash

def ux_search(project, arguments):
    repo = "nextlevelbuilder/ui-ux-pro-max-skill"
    prefix = ".claude/skills/ui-ux-pro-max/scripts/"
    root = Path(project).resolve() / ".createapp/vendor" / repo
    for entry in LOCK["sources"][repo]["files"]:
        if entry["path"].startswith(prefix) and entry["path"].endswith(".py"):
            path = root / entry["path"]
            if not path.is_file() or blob_hash(path.read_bytes()) != entry["sha"]:
                raise ConfigError("Los scripts UI/UX faltan o cambiaron respecto del catálogo. Revisá las fuentes antes de ejecutarlos.")
    script = root / prefix / "search.py"
    old_argv, old_path = sys.argv, sys.path[:]
    try:
        sys.argv = [str(script), *arguments]
        sys.path.insert(0, str(script.parent))
        runpy.run_path(str(script), run_name="__main__")
    finally:
        sys.argv, sys.path[:] = old_argv, old_path
