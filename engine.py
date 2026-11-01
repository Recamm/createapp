"""Local project initialization. Python standard library only; no shell execution."""
from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import time
import urllib.parse
import urllib.request

from catalog import DEFAULTS, AGENTS, PACKS, ROLES, roles_for
from policy import policy, adapter_block, wrapper
from runtime import cache_dir

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / "sources.lock.json").read_text(encoding="utf-8"))
MAX_SOURCE_BYTES = 8 * 1024 * 1024

class ConfigError(ValueError):
    pass

def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"

def detect_stack(target):
    package = target / "package.json"
    if package.exists():
        try:
            p = json.loads(package.read_text(encoding="utf-8"))
            dependencies = {**p.get("dependencies", {}), **p.get("devDependencies", {})}
            if "next" in dependencies: return "nextjs"
            if "react" in dependencies: return "react-vite" if "vite" in dependencies else "web"
        except (ValueError, OSError, TypeError):
            raise ConfigError("No se pudo interpretar package.json. Corregilo o elegí el stack manualmente.")
    if (target / "pyproject.toml").exists() or (target / "requirements.txt").exists(): return "python"
    return "web"

def validate(raw, workspace):
    if not isinstance(raw, dict): raise ConfigError("La configuración debe ser un objeto JSON.")
    extra = set(raw) - set(DEFAULTS)
    if extra: raise ConfigError("Campos desconocidos: " + ", ".join(sorted(extra)))
    c = copy.deepcopy(DEFAULTS)
    c.update(raw)
    if "agents" not in raw: c["agents"] = [c["agent"]]
    for key in ("name", "directory", "agent", "stack", "template", "mode", "coordinator", "testing", "autonomy", "design", "database", "goal"):
        if not isinstance(c[key], str): raise ConfigError(f"{key} debe ser texto.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,59}", c["name"]): raise ConfigError("Usá un nombre de 1 a 60 caracteres: minúsculas, números y guiones.")
    if len(c["goal"]) > 12000: raise ConfigError("El objetivo admite hasta 12.000 caracteres.")
    for k in ("parallel", "vercel_react", "vercel_web", "vercel_composition"):
        if type(c[k]) is not bool: raise ConfigError(f"{k} debe ser verdadero o falso.")
    if not isinstance(c["packs"], list) or any(not isinstance(x, str) for x in c["packs"]): raise ConfigError("La selección de paquetes no es válida.")
    if set(c["packs"]) - {p["id"] for p in PACKS}: raise ConfigError("Se seleccionó un paquete no reconocido.")
    c["packs"] = sorted(set(c["packs"]))
    if not isinstance(c["agents"], list) or not c["agents"] or any(not isinstance(x, str) or x not in AGENTS for x in c["agents"]):
        raise ConfigError("Seleccioná al menos un asistente válido.")
    c["agents"] = sorted(set(c["agents"]))
    if c["agent"] not in c["agents"]: raise ConfigError("El asistente principal debe estar seleccionado.")
    if c["skills"] is not None:
        if not isinstance(c["skills"], list) or any(not isinstance(x, str) or x not in ROLES for x in c["skills"]):
            raise ConfigError("La selección de skills individuales no es válida.")
        c["skills"] = sorted(set(c["skills"]))
        needed = {"superpowers": "workflow", "matt": "matt-workflow"}.get(c["coordinator"])
        if needed and needed not in c["skills"]:
            raise ConfigError("El coordinador requiere su skill de proceso. Seleccionala o elegí Proceso simple.")
    choices = {"agent": set(AGENTS), "stack": {"auto", "react-vite", "nextjs", "web", "python"}, "template": {"config-only"}, "mode": {"fast", "balanced", "rigorous"}, "coordinator": {"superpowers", "matt", "simple"}, "testing": {"balanced", "strict"}, "autonomy": {"milestones", "autonomous", "guided"}, "design": {"balanced", "existing", "expressive"}, "database": {"none", "postgres"}}
    for key, values in choices.items():
        if c[key] not in values: raise ConfigError(f"Opción inválida en {key}.")
    if c["coordinator"] in ("superpowers", "matt") and c["coordinator"] not in c["packs"]:
        raise ConfigError("El coordinador elegido debe estar habilitado. También podés elegir Proceso simple.")
    directory = c["directory"].strip().replace("\\", "/")
    if not directory or len(directory) > 200 or directory.startswith("/") or ":" in directory or any(x == ".." for x in directory.split("/")):
        raise ConfigError("La carpeta debe ser relativa al espacio de trabajo, sin '..' ni unidades absolutas.")
    if any(ord(x) < 32 for x in directory): raise ConfigError("La carpeta contiene caracteres inválidos.")
    root = Path(workspace).resolve()
    target = root.joinpath(directory)
    for ancestor in [target, *target.parents]:
        if ancestor == root: break
        if ancestor.is_symlink(): raise ConfigError("La carpeta de destino no puede atravesar enlaces simbólicos.")
    target = target.resolve()
    if not target.is_relative_to(root): raise ConfigError("La carpeta está fuera del espacio de trabajo.")
    if not target.is_dir(): raise ConfigError("Elegí la carpeta de un proyecto existente. CreateApp no crea aplicaciones ni carpetas de proyecto.")
    c["directory"] = directory
    if c["stack"] == "auto": c["stack"] = detect_stack(target)
    return c, target

def source_files(roles):
    selected = {}
    for _, repo, _, _ in roles.values():
        # The lock contains only reviewed subdirectories, including sibling references.
        selected[repo] = LOCK["sources"][repo]
    return selected

def graphify_setup():
    return '''"""Install Graphify in this project's private venv, only when run explicitly."""
import argparse
from pathlib import Path
import subprocess
import sys
import venv

p = argparse.ArgumentParser(description="Instala Graphify 0.9.95 en .createapp/tools/graphify, sin registrar hooks ni skills globales.")
p.parse_args()
root = Path(__file__).resolve().parent / "tools" / "graphify"
if root.is_symlink() or root.parent.is_symlink():
    raise SystemExit("La ruta de herramientas no puede ser un enlace simbólico.")
venv.EnvBuilder(with_pip=True).create(root)
python = root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
subprocess.run([str(python), "-m", "pip", "install", "graphifyy==0.9.95"], check=True)
binary = root / ("Scripts/graphify.exe" if sys.platform == "win32" else "bin/graphify")
print("Listo. Consultá los comandos con:", str(binary), "--help")
print("No se registraron hooks ni se analizó el proyecto.")
'''

def generated_files(config, target):
    roles = roles_for(config)
    files = {".createapp/config.json": json_text(config), ".createapp/POLICY.md": policy(config)}
    agents = config["agents"]
    skill_roots = sorted({".claude/skills" if agent == "claude" else ".agents/skills" for agent in agents})
    skill_root = ", ".join(skill_roots)
    for root in skill_roots:
        for name, data in roles.items(): files[f"{root}/ca-{name}/SKILL.md"] = wrapper(name, data, config)
    # Keep root and host-specific entry points small; the contract has a single copy.
    adapters = ["AGENTS.md"]
    if "copilot" in agents: adapters.append(".github/copilot-instructions.md")
    if "claude" in agents: adapters.append("CLAUDE.md")
    if "cursor" in agents: adapters.append(".cursor/rules/createapp.mdc")
    for path in adapters:
        text = adapter_block(config)
        if path.endswith(".mdc"): text = "---\ndescription: Reglas de coordinación de este proyecto\nalwaysApply: true\n---\n\n" + text
        existing = target / path
        if existing.is_symlink(): raise ConfigError(f"{path} es un enlace simbólico.")
        if existing.exists():
            if not existing.is_file(): raise ConfigError(f"{path} no es un archivo.")
            original = existing.read_text(encoding="utf-8")
            if "<!-- createapp:start -->" in original: raise ConfigError("Este proyecto ya tiene CreateApp. Esta versión conserva la instalación: usá otro destino o editá config y POLICY manualmente.")
            if path.endswith(".mdc"): raise ConfigError("Ya existe la regla createapp.mdc. Elegí otro destino.")
            text = original.rstrip() + "\n\n" + text
        files[path] = text
    ignore = target / ".gitignore"
    if ignore.is_symlink(): raise ConfigError(".gitignore es un enlace simbólico.")
    original_ignore = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    files[".gitignore"] = original_ignore.rstrip() + "\n\n# CreateApp: archivos locales\n.createapp/tools/\n"
    if "graphify" in config["packs"]: files[".createapp/setup_graphify.py"] = graphify_setup()
    files[".createapp/START_HERE.md"] = f"""# {config['name']}

## Arrancar

La configuración se agrega al proyecto existente. No se crea ni modifica el código de la aplicación.

La instalación de dependencias es explícita. CreateApp no ejecuta npm, pip, Git, despliegues ni servicios externos durante la generación. Las herramientas que necesiten las skills se comprueban con `createapp . --doctor`.

## Empezar con tu asistente

Abrí esta carpeta con {AGENTS[config['agent']]} y enviá:

> Leé AGENTS.md, .createapp/POLICY.md y .createapp/config.json. Revisá el código existente y trabajá con el coordinador y la autonomía configurados. Usá solo los perfiles ca-* que correspondan a la tarea. Primero resumí el objetivo y el siguiente paso; después avanzá hasta verificarlo.

## Objetivo inicial

{config['goal'] or 'Todavía no definido. Describí qué problema debe resolver la aplicación antes de implementarla.'}

## Qué se instaló

- Perfiles locales adaptados para roles concretos; no plugins oficiales completos.
- Fuentes originales en `.createapp/vendor/`, fijadas a commits y verificadas con hashes de blob Git.
- Un contrato de coordinación en `.createapp/POLICY.md` y la selección en `config.json`.
- `{len(roles)}` perfiles en `{skill_root}/`, con activación limitada al rol.

Los paquetes opcionales y herramientas se describen en la configuración. Si elegiste Graphify, ejecutá manualmente `python .createapp/setup_graphify.py`; luego consultá el ejecutable local con --help. No hace falta registrar otra skill con graphify install.
Los perfiles no garantizan obediencia del modelo ni eliminan conflictos con plugins globales. Si otra instalación ignora el contrato, desactivala en esa sesión.
No se instaló una PWA, autenticación, base de datos ni CI por seleccionar referencias de esas tecnologías. Son decisiones de implementación posteriores.

## Cambios y actualizaciones

Volvé a ejecutar `createapp` en este proyecto para elegir únicamente skills faltantes del catálogo actual. También podés usar `createapp --ui` o `createapp . --add-skills impeccable find-skills`; `--dry-run` muestra ese plan sin escribir. Se conservan los perfiles existentes, las fuentes fijadas y las decisiones del contrato. Las nuevas fuentes quedan separadas en `.createapp/additions/`.
Podés editar POLICY.md para cambiar acuerdos; editar config.json por sí solo no reinstala ni elimina perfiles. Este modo no actualiza ni quita skills instaladas ni cambia el coordinador. Una actualización de fuentes existentes requiere revisión y migración explícitas; nunca se reemplazan silenciosamente.
"""
    return files, roles

def preview(raw, workspace):
    config, target = validate(raw, workspace)
    if (target / ".createapp").exists(): raise ConfigError("El destino ya contiene .createapp. Ejecutá createapp sin --apply/--preview, o usá --add-skills para agregar solo faltantes.")
    files, roles = generated_files(config, target)
    appendable = {"AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", ".gitignore"}
    conflicts = []
    for name in files:
        dest = target / name
        for ancestor in [dest, *dest.parents]:
            if ancestor == target: break
            if ancestor.is_symlink(): raise ConfigError(f"No se escribe a través del enlace: {ancestor.name}")
        if dest.exists() and (name not in appendable or not dest.is_file()): conflicts.append(name)
    sources = source_files(roles)
    messages = ["Perfiles adaptados, sin hooks globales ni comandos oficiales de plugins. Las reglas son instrucciones para el asistente, no aislamiento técnico."]
    if config["coordinator"] == "matt": messages.append("Matt es el único coordinador; el flujo de Superpowers queda desactivado.")
    if config["stack"] == "auto": messages.append("No se detectó stack.")
    if config["template"] == "config-only": messages.append("Se generan reglas y skills. El código existente se conserva; no se crea una app nueva.")
    if "graphify" in config["packs"]: messages.append("Graphify queda preparado. La instalación de su CLI requiere ejecutar el script local indicado.")
    if "impeccable" in roles: messages.append("Impeccable se incluye como referencia bajo pedido, sin motor, hooks, detector ni modos live/generate.")
    if "find-skills" in roles: messages.append("Find Skills permite búsquedas bajo pedido con conexión; no instala Node/npm, el CLI ni otras skills.")
    digest = hashlib.sha256(json_text(config).encode()).hexdigest()
    return {"config": config, "target": str(target), "config_hash": digest, "roles": list(roles), "files": sorted(files), "conflicts": conflicts, "warnings": messages, "sources": [{"repo": r, "commit": s["commit"], "files": len(s["files"]), "bytes": sum(x["size"] for x in s["files"])} for r, s in sources.items()]}

def blob_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def fetch_blob(repo, source, entry, cache):
    path = PurePosixPath(entry["path"])
    if path.is_absolute() or ".." in path.parts or "\\" in entry["path"]: raise ConfigError("Ruta inválida en el catálogo de fuentes.")
    if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]): raise ConfigError("Commit inválido en el catálogo.")
    if not re.fullmatch(r"[0-9a-f]{40}", entry["sha"]): raise ConfigError("Hash inválido en el catálogo.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo): raise ConfigError("Repositorio inválido.")
    cached = cache / entry["sha"]
    for candidate in (cached, HERE / "source-cache" / entry["sha"]):
        if candidate.is_file():
            data = candidate.read_bytes()
            if blob_hash(data) == entry["sha"]: return data
    url = f"https://raw.githubusercontent.com/{repo}/{source['commit']}/{urllib.parse.quote(entry['path'], safe='/')}"
    last_error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CreateApp/1.0"})
            with urllib.request.urlopen(req, timeout=25) as response:
                data = response.read(MAX_SOURCE_BYTES + 1)
            if len(data) > MAX_SOURCE_BYTES or blob_hash(data) != entry["sha"]: raise ConfigError("El contenido descargado no coincide con el hash fijado: " + entry["path"])
            cache.mkdir(parents=True, exist_ok=True)
            # Same blobs can appear in different repositories. Atomic writes prevent races.
            fd, tempname = tempfile.mkstemp(dir=cache)
            with os.fdopen(fd, "wb") as f: f.write(data)
            os.replace(tempname, cached)
            return data
        except ConfigError: raise
        except (OSError, ValueError) as exc:
            last_error = exc
            if attempt < 2: time.sleep(0.3 * (attempt + 1))
    raise ConfigError(f"No se pudo descargar {repo}/{entry['path']}: {last_error}")

def _read_local(target, name):
    path = target / name
    if any(parent.is_symlink() for parent in [path, *path.parents] if parent == target or target in parent.parents):
        raise ConfigError("No se accede a través de enlaces simbólicos: " + name)
    if path.exists() and not path.is_file(): raise ConfigError("Se esperaba un archivo: " + name)
    return path.read_bytes() if path.exists() else None

def installation(project):
    target = Path(project).absolute()
    if target.is_symlink(): raise ConfigError("El proyecto no puede ser un enlace simbólico.")
    if not (target / ".createapp").exists(): return None
    content = _read_local(target, ".createapp/config.json")
    if content is None: raise ConfigError("La carpeta .createapp no contiene una configuración válida.")
    raw = json.loads(content)
    if not isinstance(raw, dict): raise ConfigError("La configuración instalada debe ser un objeto JSON.")
    config, target = validate(dict(raw, directory="."), target)
    roots = sorted({".claude/skills" if agent == "claude" else ".agents/skills" for agent in config["agents"]})
    installed = [name for name in ROLES if any(_read_local(target, f"{root}/ca-{name}/SKILL.md") is not None for root in roots)]
    candidates = copy.deepcopy(config)
    candidates.update(packs=[pack["id"] for pack in PACKS], vercel_react=True, vercel_web=True, vercel_composition=True)
    available = [name for name in roles_for(candidates, include_unselected=True) if name not in installed]
    return {"config": config, "installed": installed, "available": available}

def _addition_plan(names, project):
    target = Path(project).absolute()
    state = installation(target)
    if state is None: raise ConfigError("Primero configurá este proyecto con CreateApp.")
    if not isinstance(names, list) or any(not isinstance(name, str) or name not in ROLES for name in names):
        raise ConfigError("La selección de skills nuevas no es válida.")
    selected = sorted(set(names) - set(state["installed"]))
    if set(selected) - set(state["available"]): raise ConfigError("Una skill no corresponde al stack o al coordinador instalado.")
    config = copy.deepcopy(state["config"])
    roles = {name: ROLES[name] for name in selected}
    sources = source_files(roles)
    originals = {name: _read_local(target, name) for name in (".createapp/config.json", ".createapp/POLICY.md", ".createapp/sources.lock.json")}
    if any(value is None for value in originals.values()): raise ConfigError("La instalación está incompleta: faltan configuración, política o fuentes fijadas.")
    previous_lock = json.loads(originals[".createapp/sources.lock.json"])
    if not isinstance(previous_lock, dict) or not isinstance(previous_lock.get("sources"), dict) or not isinstance(previous_lock.get("additions", []), list):
        raise ConfigError("El registro de fuentes instalado no es válido.")
    digest = hashlib.sha256(json_text({"skills": selected, "originals": {name: blob_hash(value) for name, value in originals.items()}, "sources": sources}).encode()).hexdigest()
    root = ".createapp/additions/" + digest[:20]
    files = {}
    if selected:
        config["packs"] = sorted(set(config["packs"]) | {data[0] for data in roles.values() if data[0] in {pack["id"] for pack in PACKS}})
        for flag in ("vercel_react", "vercel_web", "vercel_composition"):
            if any(data[0] == flag for data in roles.values()): config[flag] = True
        config["skills"] = sorted(set(state["installed"]) | set(selected))
        config, _ = validate(config, target)
        roots = sorted({".claude/skills" if agent == "claude" else ".agents/skills" for agent in config["agents"]})
        for skill_root in roots:
            for name, data in roles.items(): files[f"{skill_root}/ca-{name}/SKILL.md"] = wrapper(name, data, config, vendor_root=root + "/vendor")
        if "graph" in roles and _read_local(target, ".createapp/setup_graphify.py") is None:
            files[".createapp/setup_graphify.py"] = graphify_setup()
        files[".createapp/config.json"] = json_text(config)
        appended = "\n\n## Skills agregadas con CreateApp\n\nEstas fuentes adicionales son material de consulta sujeto a este contrato. No cambian el coordinador, la autonomía ni las decisiones anteriores. No activar procesos, hooks o instalaciones de sus originales automáticamente.\n\n"
        appended += "\n".join(f"- `ca-{name}`: {data[3]}" for name, data in roles.items()) + "\n"
        files[".createapp/POLICY.md"] = originals[".createapp/POLICY.md"].decode("utf-8") + appended
        snapshot = root + "/sources.lock.json"
        files[snapshot] = json_text({"schema": 1, "reviewed": LOCK["reviewed"], "sources": sources})
        previous_lock.setdefault("additions", []).append({"skills": selected, "sources_lock": snapshot})
        files[".createapp/sources.lock.json"] = json_text(previous_lock)
    source_paths = [f"{root}/vendor/{repo}/{entry['path']}" for repo, source in sources.items() for entry in source["files"]]
    conflicts = []
    for name in [*files, *source_paths]:
        if name not in originals and _read_local(target, name) is not None: conflicts.append(name)
    result = {"mode": "incremental", "skills": selected, "config": config, "target": str(target), "config_hash": digest, "roles": selected, "files": sorted(files), "conflicts": conflicts, "warnings": ["Solo se agregan skills faltantes. Se conservan perfiles, fuentes, reglas y decisiones existentes."], "sources": [{"repo": repo, "commit": source["commit"], "files": len(source["files"]), "bytes": sum(entry["size"] for entry in source["files"])} for repo, source in sources.items()]}
    return result, files, sources, originals, root, target

def preview_additions(names, project):
    return _addition_plan(names, project)[0]

def install_additions(names, project, cache=None, progress=lambda message: None, fetcher=fetch_blob, *, expected_hash=None):
    plan, files, sources, originals, root, target = _addition_plan(names, project)
    if expected_hash is not None and plan["config_hash"] != expected_hash:
        raise ConfigError("La instalación cambió desde la vista previa. Volvé a revisar la selección.")
    if plan["conflicts"]: raise ConfigError("Hay archivos existentes en conflicto: " + ", ".join(plan["conflicts"]))
    if not plan["roles"]:
        return {"target": str(target), "roles": 0, "source_files": 0, "next": "No hay skills nuevas seleccionadas."}
    cache = Path(cache) if cache else cache_dir()
    jobs = [(repo, source, entry) for repo, source in sources.items() for entry in source["files"]]
    with tempfile.TemporaryDirectory(prefix="createapp-add-") as temporary:
        stage = Path(temporary)
        for name, value in files.items():
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(value, encoding="utf-8", newline="")
        progress(f"Preparando {len(plan['roles'])} skills nuevas…")
        for repo, source, entry in jobs:
            dest = stage / root / "vendor" / repo / entry["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(fetcher(repo, source, entry, cache))
        current = preview_additions(names, target)
        if current["config_hash"] != plan["config_hash"] or current["conflicts"]:
            raise ConfigError("La instalación cambió durante la preparación. Volvé a revisar la selección.")
        _write_stage(stage, target, originals, set(originals))
    progress("Skills nuevas agregadas. La instalación anterior se conservó.")
    return {"target": str(target), "roles": len(plan["roles"]), "source_files": len(jobs), "next": "Los nuevos perfiles ca-* ya están disponibles para tus asistentes."}

def _write_stage(stage, target, originals, replaceable):
    backups, written, new_dirs = {}, [], []
    try:
        for src in sorted(stage.rglob("*")):
            if not src.is_file(): continue
            rel = src.relative_to(stage)
            relative_name = rel.as_posix()
            dest = target / rel
            if any(parent.is_symlink() for parent in [dest, *dest.parents] if parent == target or target in parent.parents):
                raise ConfigError("Apareció un enlace simbólico en el destino.")
            if dest.exists():
                if relative_name not in replaceable: raise ConfigError("Un archivo apareció en el destino: " + relative_name)
                if dest.read_bytes() != originals.get(relative_name): raise ConfigError("Un archivo cambió antes de escribir: " + relative_name)
                backups[dest] = dest.read_bytes()
            elif originals.get(relative_name) is not None:
                raise ConfigError("Un archivo del proyecto desapareció durante la preparación.")
            else: backups[dest] = None
            missing = []
            ancestor = dest.parent
            while not ancestor.exists():
                missing.append(ancestor)
                ancestor = ancestor.parent
            dest.parent.mkdir(parents=True, exist_ok=True)
            new_dirs.extend(reversed(missing))
            with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as handle:
                handle.write(src.read_bytes())
                tempname = handle.name
            try: os.replace(tempname, dest)
            finally:
                if os.path.exists(tempname): os.unlink(tempname)
            written.append(dest)
    except Exception:
        for dest in reversed(written):
            if backups[dest] is None: dest.unlink(missing_ok=True)
            else: dest.write_bytes(backups[dest])
        for directory in reversed(new_dirs):
            try: directory.rmdir()
            except OSError: pass
        raise

def initialize(raw, workspace, cache=None, progress=lambda message: None, fetcher=fetch_blob):
    p = preview(raw, workspace)
    if p["conflicts"]: raise ConfigError("Hay archivos que ya existen: " + ", ".join(p["conflicts"]))
    config, target = validate(p["config"], workspace)
    files, roles = generated_files(config, target)
    originals = {name: (target / name).read_bytes() if (target / name).exists() else None for name in files}
    sources = source_files(roles)
    cache = Path(cache) if cache else cache_dir()
    # Stage everything before touching the project. A failed download leaves no partial project.
    with tempfile.TemporaryDirectory(prefix="createapp-") as temporary:
        stage = Path(temporary)
        for name, value in files.items():
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(value.encode("utf-8"))
        jobs = [(repo, source, entry) for repo, source in sources.items() for entry in source["files"]]
        def download(item):
            repo, source, entry = item
            data = fetcher(repo, source, entry, cache)
            dest = stage / ".createapp" / "vendor" / repo / entry["path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return entry["path"]
        progress(f"Preparando {len(jobs)} archivos de fuentes verificadas…")
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(download, j) for j in jobs]
            for count, future in enumerate(concurrent.futures.as_completed(futures), 1):
                future.result()
                if count % 20 == 0 or count == len(jobs): progress(f"Fuentes preparadas: {count}/{len(jobs)}")
        chosen_lock = {"schema": 1, "reviewed": LOCK["reviewed"], "sources": sources}
        (stage / ".createapp" / "sources.lock.json").write_text(json_text(chosen_lock), encoding="utf-8")
        # Recheck after downloads, before applying any write.
        current = preview(config, workspace)
        if current["conflicts"]: raise ConfigError("El destino cambió mientras se descargaban las fuentes.")
        now_files, _ = generated_files(config, target)
        if now_files != files: raise ConfigError("Un archivo de instrucciones cambió durante la preparación. Volvé a revisar la vista previa.")
        progress("Escribiendo la configuración local…")
        _write_stage(stage, target, originals, {"AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", ".gitignore"})
    progress("Proyecto preparado.")
    return {"target": str(target), "roles": len(roles), "source_files": len(jobs), "next": "Abrí .createapp/START_HERE.md en el proyecto."}
