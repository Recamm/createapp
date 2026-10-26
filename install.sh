#!/bin/sh
# Usage: curl -fsSL https://raw.githubusercontent.com/OWNER/REPO/main/install.sh | sh
set -eu
repo=${CREATEAPP_REPO:-Recamm/createapp}
version=${CREATEAPP_VERSION:-latest}
case "$repo" in *[!a-zA-Z0-9_./-]*|/*|*..*|*/*/*|*/) echo 'Repositorio inválido.' >&2; exit 1;; esac
case "$repo" in */*) :;; *) echo 'Usá owner/repo.' >&2; exit 1;; esac
case "$version" in *[!a-zA-Z0-9_.-]*) echo 'Versión inválida.' >&2; exit 1;; esac
case "$(uname -s)" in Linux) system=linux;; Darwin) system=macos;; *) echo 'Usá install.ps1 para Windows.' >&2; exit 1;; esac
case "$(uname -m)" in x86_64|amd64) arch=x64;; arm64|aarch64) arch=arm64;; *) echo 'Arquitectura no soportada.' >&2; exit 1;; esac
asset="createapp-$system-$arch.tar.gz"
if [ "$version" = latest ]; then base="https://github.com/$repo/releases/latest/download"; else base="https://github.com/$repo/releases/download/$version"; fi
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
download() {
    if command -v curl >/dev/null 2>&1; then curl --fail --location --silent --show-error --retry 2 "$1" --output "$2"
    elif command -v wget >/dev/null 2>&1; then wget -q "$1" -O "$2"
    else echo 'Se necesita curl o wget para descargar el ejecutable.' >&2; exit 1; fi
}
printf 'Descargando CreateApp para %s/%s…\n' "$system" "$arch"
download "$base/$asset" "$tmp/$asset"
download "$base/SHA256SUMS" "$tmp/SHA256SUMS"
expected=$(awk -v asset="$asset" '$2 == asset || $2 == "*" asset { print $1 }' "$tmp/SHA256SUMS")
if command -v sha256sum >/dev/null 2>&1; then actual=$(sha256sum "$tmp/$asset" | awk '{print $1}')
elif command -v shasum >/dev/null 2>&1; then actual=$(shasum -a 256 "$tmp/$asset" | awk '{print $1}')
else echo 'No hay una herramienta SHA-256 disponible.' >&2; exit 1; fi
if [ -z "$expected" ] || [ "$actual" != "$expected" ]; then echo 'La descarga no coincide con su checksum. No se instaló.' >&2; exit 1; fi
mkdir "$tmp/content"
tar -xzf "$tmp/$asset" -C "$tmp/content"
bindir=${CREATEAPP_BIN_DIR:-"$HOME/.local/bin"}
mkdir -p "$bindir"
cp "$tmp/content/createapp" "$bindir/.createapp-new-$$"
chmod 755 "$bindir/.createapp-new-$$"
"$bindir/.createapp-new-$$" --version
mv -f "$bindir/.createapp-new-$$" "$bindir/createapp"
licenses=${XDG_DATA_HOME:-"$HOME/.local/share"}/createapp/licenses
mkdir -p "$licenses"
for item in LICENSE THIRD_PARTY.md third-party runtime-licenses; do
    if [ -e "$tmp/content/$item" ]; then cp -R "$tmp/content/$item" "$licenses/"; fi
done
printf 'Instalado: %s/createapp\n' "$bindir"
printf 'Terminal: "%s/createapp" .\nNavegador: "%s/createapp" . --ui\n' "$bindir" "$bindir"
case ":$PATH:" in *":$bindir:"*) :;; *) printf 'Agregá %s a tu PATH para usar el comando corto createapp.\n' "$bindir";; esac
if [ "${CREATEAPP_NO_LAUNCH:-0}" != 1 ] && [ -t 1 ] && [ -r /dev/tty ]; then
    exec "$bindir/createapp" . </dev/tty
fi
