"""Build and smoke-test one native executable; release packaging is cross-platform."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime import VERSION
from catalog import DEFAULTS

def native_target():
    system = {'Linux': 'linux', 'Darwin': 'macos', 'Windows': 'windows'}.get(platform.system())
    arch = {'x86_64': 'x64', 'AMD64': 'x64', 'aarch64': 'arm64', 'arm64': 'arm64', 'ARM64': 'arm64'}.get(platform.machine())
    if not system or not arch: raise SystemExit('Plataforma no soportada por este build.')
    return f'{system}-{arch}'

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--target', default=native_target())
    p.add_argument('--output', type=Path, default=ROOT / 'release')
    args = p.parse_args()
    if args.target != native_target(): raise SystemExit('No es un compilador cruzado. Ejecutá el build en el sistema y arquitectura indicados.')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='createapp-build-') as temp:
        temp = Path(temp)
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--distpath', str(temp / 'dist'), '--workpath', str(temp / 'build'), str(ROOT / 'CreateApp.spec')], cwd=ROOT, check=True)
        binary = temp / 'dist' / ('createapp.exe' if os.name == 'nt' else 'createapp')
        subprocess.run([str(binary), '--version'], check=True)
        project = temp / 'project'
        project.mkdir()
        original = project / 'app.txt'
        original.write_text('existing project', encoding='utf-8')
        cfg = temp / 'config.json'
        cfg.write_text(json.dumps(DEFAULTS), encoding='utf-8')
        # Empty PATH verifies that neither Python nor Node executables are launched.
        empty_path = temp / 'empty-path'
        empty_path.mkdir()
        env = dict(os.environ, PATH=str(empty_path))
        subprocess.run([str(binary), str(project), '--apply', str(cfg)], env=env, check=True)
        assert original.read_text(encoding='utf-8') == 'existing project'
        assert not (project / 'package.json').exists()
        assert (project / '.createapp/POLICY.md').is_file()
        assert not (project / 'START_HERE.md').exists()
        subprocess.run([str(binary), str(project), '--ux-search', 'minimal productivity', '--design-system', '-f', 'markdown'], env=env, stdout=subprocess.DEVNULL, check=True)
        subprocess.run([str(binary), str(project), '--doctor'], env=env, check=True)
        content = temp / 'package'
        content.mkdir()
        shutil.copy2(binary, content / binary.name)
        for name in ('LICENSE', 'THIRD_PARTY.md'): shutil.copy2(ROOT / name, content / name)
        shutil.copytree(ROOT / 'third-party', content / 'third-party')
        licenses = content / 'runtime-licenses'
        licenses.mkdir()
        for package in ('questionary', 'prompt_toolkit', 'wcwidth', 'pyinstaller'):
            dist = importlib.metadata.distribution(package)
            for item in dist.files or []:
                if Path(str(item)).name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
                    src = Path(dist.locate_file(item))
                    if src.is_file():
                        dest = licenses / package / str(item).replace('..', '_')
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dest)
        python_license = Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt'
        if python_license.is_file(): shutil.copy2(python_license, licenses / 'PYTHON_LICENSE.txt')
        (content / 'README_INSTALL.txt').write_text(f'CreateApp {VERSION}\n\nEjecutá createapp desde una terminal dentro de tu proyecto existente.\ncreateapp --ui abre el navegador.\ncreateapp --help muestra las opciones.\nEl runtime está incluido. Las herramientas opcionales se revisan con --doctor.\n\nBuild: {args.target}\nSistema usado: {platform.platform()}\n', encoding='utf-8')
        archive = output / ('createapp-' + args.target + ('.zip' if os.name == 'nt' else '.tar.gz'))
        if os.name == 'nt':
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
                for file in sorted(content.rglob('*')):
                    if file.is_file(): z.write(file, file.relative_to(content))
        else:
            with tarfile.open(archive, 'w:gz') as tar:
                for file in sorted(content.iterdir()): tar.add(file, arcname=file.name)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (output / (archive.name + '.sha256')).write_text(digest + '  ' + archive.name + '\n', encoding='ascii')
        shutil.copy2(binary, output / ('createapp-' + args.target + ('.exe' if os.name == 'nt' else '')))
        print('Build y smoke test sin runtimes externos correctos:', archive)

if __name__ == '__main__': main()
