"""Use the selected UI/UX search scripts with the executable's embedded Python."""
import csv  # Collected by PyInstaller for the dynamically loaded upstream search.
import json
import runpy
from pathlib import Path, PurePosixPath
import sys
from engine import ConfigError, LOCK, blob_hash, _read_local

def ux_search(project, arguments):
    repo = "nextlevelbuilder/ui-ux-pro-max-skill"
    prefix = ".claude/skills/ui-ux-pro-max/scripts/"
    root = Path(project).resolve() / ".createapp/vendor" / repo
    if not (root / prefix / "search.py").is_file():
        project = Path(project).resolve()
        lock = json.loads(_read_local(project, ".createapp/sources.lock.json") or b"{}")
        for addition in reversed(lock.get("additions", [])):
            name = addition.get("sources_lock", "")
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name or path.parts[:2] != (".createapp", "additions"):
                raise ConfigError("Ruta de fuentes adicionales inválida.")
            snapshot = json.loads(_read_local(project, name) or b"{}")
            if repo in snapshot.get("sources", {}):
                root = project / path.parent / "vendor" / repo
                break
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
