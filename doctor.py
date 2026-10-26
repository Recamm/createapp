"""Report dependencies for selected tools without installing or running them."""
import json
from pathlib import Path
import shutil
import sys
from catalog import roles_for
from runtime import VERSION, project_defaults

def inspect(project):
    project = Path(project).resolve()
    cfg = project / ".createapp/config.json"
    config = json.loads(cfg.read_text(encoding="utf-8")) if cfg.is_file() else project_defaults(project)
    roles = roles_for(config)
    checks = []
    if {"browser-test", "graph"} & set(roles):
        python = next((p for n in ("python3", "python", "py") if (p := shutil.which(n))), None)
        checks.append({"tool": "Python externo", "found": bool(python), "path": python, "purpose": "Pruebas Python/Playwright y Graphify. CreateApp y su comando --ux-search incluyen runtime. La versión externa debe comprobarse antes de usarla."})
    if "browser-test" in roles:
        checks.append({"tool": "Playwright y navegadores", "found": None, "purpose": "No se instalan ni se prueban automáticamente. Reutilizar la herramienta de navegador del asistente si está disponible."})
    if "graph" in roles:
        binary = project / ".createapp/tools/graphify" / ("Scripts/graphify.exe" if sys.platform == "win32" else "bin/graphify")
        checks.append({"tool": "Graphify local", "found": binary.is_file(), "path": str(binary), "purpose": "Opcional, instalación manual; sin watchers automáticos."})
    return {"version": VERSION, "project": str(project), "standalone": bool(getattr(sys, "frozen", False)), "configured": cfg.is_file(), "checks": checks}
