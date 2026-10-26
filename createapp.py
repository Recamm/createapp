#!/usr/bin/env python3
"""Run CreateApp's local configurator or initialize from a JSON config."""
from __future__ import annotations
import argparse
import concurrent.futures
import copy
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sys
import threading
import urllib.parse
import webbrowser

from catalog import AGENTS, DEFAULTS, PACKS, ROLES
from runtime import VERSION, cache_dir, project_defaults
from engine import ConfigError, HERE, LOCK, fetch_blob, initialize, preview, detect_stack

class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, workspace, cache=None):
        super().__init__(address, Handler)
        self.workspace = Path(workspace).resolve()
        self.cache = cache
        self.token = secrets.token_urlsafe(32)
        self.job = {"state": "idle", "messages": []}
        self.job_lock = threading.Lock()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server_port}"

    def generate(self, config):
        def progress(message):
            with self.job_lock: self.job["messages"].append(message)
        try:
            result = initialize(config, self.workspace, self.cache, progress)
            with self.job_lock: self.job.update(state="done", result=result)
        except Exception as exc:
            with self.job_lock: self.job.update(state="error", error=str(exc))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, body, mime="application/json; charset=utf-8"):
        if not isinstance(body, bytes): body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") not in allowed_hosts: return False
        origin = self.headers.get("Origin")
        if origin and origin not in {self.server.base_url, f"http://localhost:{self.server.server_port}"}: return False
        return hmac.compare_digest(self.headers.get("X-CreateApp-Token", ""), self.server.token)

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.css": ("app.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "application/javascript; charset=utf-8")}
        if path in assets:
            filename, mime = assets[path]
            self.send(200, (HERE / "web" / filename).read_bytes(), mime)
            return
        if not self.authorized(): self.send(403, {"error": "Abrí la dirección completa que muestra la terminal para autorizar esta sesión local."}); return
        if path == "/api/catalog":
            self.send(200, {"defaults": project_defaults(self.server.workspace), "packs": PACKS, "agents": AGENTS, "detected_stack": detect_stack(self.server.workspace), "skills": {name: {"pack": data[0], "description": data[3]} for name, data in ROLES.items()}, "workspace": str(self.server.workspace), "reviewed": LOCK["reviewed"]})
        elif path == "/api/status":
            with self.server.job_lock: state = copy.deepcopy(self.server.job)
            self.send(200, state)
        else: self.send(404, {"error": "Ruta no encontrada."})

    def do_POST(self):
        if not self.authorized(): self.send(403, {"error": "Sesión local no autorizada."}); return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json": self.send(415, {"error": "Se requiere JSON."}); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536: raise ConfigError("Solicitud demasiado grande o vacía.")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict): raise ConfigError("La solicitud debe ser un objeto.")
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/preview":
                self.send(200, preview(body, self.server.workspace))
            elif path == "/api/initialize":
                p = preview(body.get("config"), self.server.workspace)
                if p["config_hash"] != body.get("config_hash"): raise ConfigError("La configuración cambió. Actualizá la vista previa.")
                if p["conflicts"]: raise ConfigError("Hay conflictos con archivos existentes.")
                with self.server.job_lock:
                    if self.server.job["state"] == "running": raise ConfigError("Ya hay una generación en curso.")
                    self.server.job = {"state": "running", "messages": ["Preparando el proyecto…"]}
                threading.Thread(target=self.server.generate, args=(p["config"],), daemon=True).start()
                self.send(202, {"state": "running"})
            else: self.send(404, {"error": "Ruta no encontrada."})
        except (ConfigError, ValueError, TypeError, OSError) as exc:
            self.send(400, {"error": str(exc)})

def main():
    p = argparse.ArgumentParser(description="CreateApp: configurar skills y reglas de un proyecto existente. Terminal por defecto; --ui abre el navegador.")
    p.add_argument("project", nargs="?", type=Path, help="Carpeta del proyecto existente; si se omite se pregunta en terminal.")
    p.add_argument("--workspace", type=Path, help=argparse.SUPPRESS)
    p.add_argument("--ui", action="store_true", help="Abrir la interfaz opcional de navegador.")
    p.add_argument("--doctor", action="store_true", help="Mostrar requisitos de las herramientas seleccionadas, sin instalar nada.")
    p.add_argument("--version", action="version", version="CreateApp " + VERSION)
    p.add_argument("--ux-search", nargs=argparse.REMAINDER, help="Ejecutar el buscador UI/UX seleccionado con el runtime incluido. Debe ser la última opción.")
    p.add_argument("--port", type=int, default=0, help="Puerto local; 0 elige uno libre.")
    p.add_argument("--no-browser", action="store_true", help="Mostrar la URL sin abrir el navegador.")
    p.add_argument("--apply", type=Path, metavar="CONFIG.json", help="Generar directamente desde una configuración exportada.")
    p.add_argument("--preview", type=Path, metavar="CONFIG.json", help="Mostrar el plan sin escribir el proyecto.")
    p.add_argument("--prefetch", action="store_true", help="Descargar todas las fuentes del catálogo a la caché para uso offline posterior.")
    p.add_argument("--cache", type=Path, default=cache_dir(), help="Caché de blobs verificados.")
    args = p.parse_args()
    project = (args.workspace or args.project or Path.cwd()).expanduser().resolve()
    try:
        if not project.is_dir(): raise ConfigError("La carpeta del proyecto debe existir.")
        if args.ux_search is not None:
            from tooling import ux_search
            ux_search(project, args.ux_search)
            return
        if args.doctor:
            from doctor import inspect
            print(json.dumps(inspect(project), ensure_ascii=False, indent=2))
            return
        if args.prefetch:
            tasks = [(r, s, e) for r, s in LOCK["sources"].items() for e in s["files"]]
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                futures = [pool.submit(fetch_blob, r, s, e, args.cache) for r, s, e in tasks]
                for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
                    future.result()
                    if n % 25 == 0 or n == len(tasks): print(f"Fuentes: {n}/{len(tasks)}", flush=True)
            return
        config_path = args.apply or args.preview
        if config_path:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            result = initialize(raw, project, args.cache, print) if args.apply else preview(raw, project)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if not args.ui:
            if not sys.stdin.isatty():
                raise ConfigError("Usá una terminal interactiva, --ui para navegador o --preview/--apply con un JSON.")
            from terminal import run
            run(args.project or args.workspace, args.cache)
            return
        server = AppServer(("127.0.0.1", args.port), project, args.cache)
        url = server.base_url + "/#token=" + server.token
        print("CreateApp está listo. Abrí esta dirección en tu navegador:", flush=True)
        print(url, flush=True)
        print("Destino raíz:", project, flush=True)
        print("Ctrl+C para cerrar. El servidor solo escucha en tu computadora.", flush=True)
        if not args.no_browser: webbrowser.open(url)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
    except (ConfigError, OSError, ValueError) as exc:
        p.exit(1, "Error: " + str(exc) + "\n")

if __name__ == "__main__": main()
