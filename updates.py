"""Check each invocation and install a pinned public release only after consent."""
import base64
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

from runtime import VERSION

RELEASE_API = "https://api.github.com/repos/Recamm/createapp/releases/latest"
RELEASE_URL = "https://github.com/Recamm/createapp/releases/latest"
MAX_RELEASE_BYTES = 256 * 1024
MAX_INSTALLER_BYTES = 128 * 1024


def _version_tuple(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    match = re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
    return tuple(int(part) for part in match.groups()) if match else None


def internet_available():
    try:
        proxy = urllib.parse.urlsplit(urllib.request.getproxies().get("https", ""))
        host = proxy.hostname or "api.github.com"
        port = proxy.port or (443 if not proxy.hostname or proxy.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=1):
            return True
    except (OSError, ValueError):
        return False


def check_for_updates():
    latest = None
    tag = None
    if internet_available():
        try:
            request = urllib.request.Request(RELEASE_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "CreateApp/" + VERSION})
            with urllib.request.urlopen(request, timeout=2) as response:
                data = response.read(MAX_RELEASE_BYTES + 1)
            if len(data) > MAX_RELEASE_BYTES:
                raise ValueError("Release response too large")
            release = json.loads(data)
            if isinstance(release, dict) and not release.get("draft") and not release.get("prerelease"):
                version = _version_tuple(release.get("tag_name"))
                if version is not None:
                    tag = release["tag_name"]
                    latest = ".".join(str(part) for part in version)
        except (OSError, ValueError, HTTPException):
            pass
    current_version = _version_tuple(VERSION)
    latest_version = _version_tuple(latest)
    status = "unavailable"
    if current_version is not None and latest_version is not None:
        status = "available" if latest_version > current_version else "current"
    return {"status": status, "current": VERSION, "latest": latest, "tag": tag, "url": RELEASE_URL}


def update_message(result):
    if result["status"] == "available":
        return f"CreateApp {result['latest']} disponible (actual: {result['current']})."
    return ""


def install_update(result):
    tag = result.get("tag")
    if result.get("status") != "available" or _version_tuple(tag) is None or _version_tuple(tag) != _version_tuple(result.get("latest")):
        raise ValueError("Invalid release version")
    windows = sys.platform == "win32"
    installer_name = "install.ps1" if windows else "install.sh"
    url = f"https://github.com/Recamm/createapp/releases/download/{tag}/{installer_name}"
    request = urllib.request.Request(url, headers={"User-Agent": "CreateApp/" + VERSION})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = response.read(MAX_INSTALLER_BYTES + 1)
    if not data or len(data) > MAX_INSTALLER_BYTES:
        raise ValueError("Invalid installer size")
    folder = Path(tempfile.mkdtemp(prefix="createapp-update-"))
    launched = False
    try:
        installer = folder / installer_name
        installer.write_bytes(data)
        environment = os.environ.copy()
        environment.update(CREATEAPP_NO_LAUNCH="1", CREATEAPP_VERSION=tag, CREATEAPP_REPO="Recamm/createapp", PYINSTALLER_RESET_ENVIRONMENT="1")
        if getattr(sys, "frozen", False):
            if "LD_LIBRARY_PATH_ORIG" in environment:
                environment["LD_LIBRARY_PATH"] = environment["LD_LIBRARY_PATH_ORIG"]
            else:
                environment.pop("LD_LIBRARY_PATH", None)
        if windows:
            environment["CREATEAPP_UPDATE_PID"] = str(os.getpid())
            environment["CREATEAPP_UPDATE_SCRIPT"] = str(installer)
            worker = """$ErrorActionPreference = 'Stop'
try {
    Wait-Process -Id ([int]$env:CREATEAPP_UPDATE_PID) -ErrorAction SilentlyContinue
    & ([scriptblock]::Create([IO.File]::ReadAllText($env:CREATEAPP_UPDATE_SCRIPT))) -Repository 'Recamm/createapp' -Version $env:CREATEAPP_VERSION -NoLaunch
    Write-Host 'CreateApp actualizado. Volve a ejecutar tu comando.'
} catch {
    Write-Host ('No se pudo actualizar CreateApp: ' + $_.Exception.Message) -ForegroundColor Red
} finally {
    Remove-Item -LiteralPath ([IO.Path]::GetDirectoryName($env:CREATEAPP_UPDATE_SCRIPT)) -Recurse -Force -ErrorAction SilentlyContinue
}
[void](Read-Host 'Pulsa Enter para cerrar')
"""
            encoded = base64.b64encode(worker.encode("utf-16le")).decode("ascii")
            powershell = str(Path(environment.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe")
            subprocess.Popen([powershell, "-NoProfile", "-EncodedCommand", encoded], env=environment, creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010))
            launched = True
        else:
            subprocess.run(["sh", str(installer)], env=environment, check=True)
    finally:
        if not launched:
            shutil.rmtree(folder, ignore_errors=True)


def offer_update(result):
    message = update_message(result)
    if not message:
        return False
    print(message, file=sys.stderr, flush=True)
    if not sys.stdin.isatty():
        print("Ejecuta CreateApp desde una terminal interactiva para actualizar.", file=sys.stderr, flush=True)
        return False
    print("Actualizar la instalacion de usuario ahora? [s/N] ", end="", file=sys.stderr, flush=True)
    try:
        answer = input().strip().lower()
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return True
    except EOFError:
        print(file=sys.stderr)
        return False
    if answer not in ("s", "si", "s\u00ed", "y", "yes"):
        return False
    try:
        install_update(result)
    except (OSError, ValueError, HTTPException, subprocess.SubprocessError) as exc:
        print(f"No se pudo actualizar CreateApp: {exc}. Se continua con la version actual.", file=sys.stderr, flush=True)
        return False
    message = "CreateApp se cerrara; el actualizador continuara en otra ventana." if sys.platform == "win32" else "CreateApp actualizado. Volve a ejecutar tu comando."
    print(message, file=sys.stderr, flush=True)
    return True