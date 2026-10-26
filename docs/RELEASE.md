# Publicar CreateApp

El instalador de un comando requiere una release pública accesible sin login. El código no contiene credenciales y usa únicamente el GITHUB_TOKEN del workflow para crear el borrador.

1. El repositorio es `Recamm/createapp`. El contenido de la carpeta fuente ocupa su raíz, incluyendo `.github/`.
2. Si se usa otro owner/repo, ajustar los valores por defecto de install.sh/install.ps1 y los enlaces del README. También se pueden proporcionar CREATEAPP_REPO y CREATEAPP_VERSION al instalador.
3. Revisar las pruebas del workflow Tests en Windows, macOS y Linux.
4. Cada push a `main`, tag `v*` o ejecución manual de Build native releases compila los cinco targets. Si la versión de `runtime.py` aún no tiene release, prepara un borrador con un tag que apunta al commit compilado. Un tag explícito debe coincidir con esa versión.
5. Revisar los cinco builds y sus smoke tests. Publicar el borrador desde [Releases](https://github.com/Recamm/createapp/releases) para habilitar `/releases/latest/download/`.
6. Para la siguiente release, incrementar `runtime.VERSION` y subir el cambio. Las releases existentes, incluso borradores, no se modifican automáticamente; los builds posteriores de la misma versión quedan como artifacts en Actions.

## Targets

| Target | Runner | Formato |
| --- | --- | --- |
| linux-x64 | ubuntu-22.04 | tar.gz |
| linux-arm64 | ubuntu-22.04-arm | tar.gz |
| windows-x64 | windows-2022 | zip |
| macos-x64 | macos-15-intel | tar.gz |
| macos-arm64 | macos-14 | tar.gz |

Windows ARM64 nativo no está incluido. La compatibilidad fuera de esos runners requiere pruebas adicionales. No se intenta compilar Windows o macOS desde Linux.

## Assets de release

- createapp-PLATAFORMA-ARQUITECTURA.zip/tar.gz
- SHA256SUMS
- install.sh e install.ps1

Cada archivo incluye un ejecutable y licencias. SHA256SUMS reúne hashes de los cinco archivos; se sirve desde la misma release. Es verificación de integridad, no una firma independiente de autenticidad.

El build usa PyInstaller 6.22.3 y Questionary 2.1.1. Las dependencias de build tienen rangos transitivos; no se afirma reproducibilidad bit a bit. El contenido de las skills sí queda fijado por el catálogo de fuentes.

## Lo que queda por configurar para una distribución madura

- Firma Authenticode en Windows y firma/notarización de Apple con credenciales del responsable del proyecto.
- Pruebas reales de instalación en equipos limpios además de los runners.
- Una política de actualización del catálogo que conserve las decisiones de cada proyecto.

Los instaladores no desactivan protecciones del sistema ni eliminan la cuarentena de macOS. Se debe revisar y autorizar el ejecutable por los mecanismos del sistema cuando corresponda.
