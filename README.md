# CreateApp 0.2

Configurá skills y reglas en un **proyecto existente** desde un menú de terminal. También incluye una interfaz opcional de navegador.

Los ejecutables contienen su propio runtime. **No necesitás instalar Python, Node.js, npm ni Git para abrir CreateApp.** Las herramientas opcionales que use un asistente pueden tener sus propios requisitos.

## Estado de distribución

GitHub Actions ejecuta pruebas y builds nativos para Windows x64, Linux x64/ARM64 y macOS Intel/Apple Silicon. Cuando los cinco builds pasan, prepara una release en borrador para la versión de `runtime.py`. Revisá [Actions](https://github.com/Recamm/createapp/actions) para ver el resultado de cada plataforma.

Los comandos de descarga siguientes **requieren una release pública publicada**. Un borrador todavía no habilita las descargas públicas. Las releases existentes nunca se reemplazan automáticamente.

## Instalación con un comando

Windows x64, desde PowerShell dentro de tu proyecto:

```powershell
irm https://github.com/Recamm/createapp/releases/latest/download/install.ps1 | iex
```

Linux o macOS, desde una terminal dentro de tu proyecto:

```sh
curl -fsSL https://github.com/Recamm/createapp/releases/latest/download/install.sh | sh
```

El instalador selecciona el sistema/arquitectura, descarga el archivo de la release y comprueba su SHA-256. Instala en tu usuario, sin administrador ni sudo, y abre el configurador cuando hay una terminal interactiva.

- Windows: `%LOCALAPPDATA%\CreateApp\bin\createapp.exe`, con PATH de usuario.
- Linux/macOS: `~/.local/bin/createapp`. Si esa carpeta no está en PATH, se muestra el comando con su ruta completa; el instalador no edita tus archivos de shell.
- Las licencias se conservan en la carpeta de datos de CreateApp del usuario.
- El checksum comprueba integridad respecto de la release; no sustituye una firma de código independiente.

También podés descargar un archivo de release y extraerlo manualmente. No hay instalación permanente obligatoria: el ejecutable se puede usar desde esa carpeta.

## Uso

Terminal, preguntando la carpeta:

```sh
createapp
```

Terminal, en el proyecto actual o indicando una carpeta:

```sh
createapp .
createapp /ruta/a/mi-proyecto
```

Interfaz opcional de navegador:

```sh
createapp . --ui
```

El servidor solo escucha en la computadora local y utiliza una autorización por sesión. No hay cuenta ni backend alojado. Mantené abierta la terminal mientras usás el navegador.

Otros comandos:

```sh
createapp --help
createapp --version
createapp . --doctor
createapp . --preview configuracion.json
createapp . --apply configuracion.json
```

La interfaz web permite exportar la selección. `--preview` no modifica el proyecto; `--apply` aplica explícitamente el JSON indicado.

## Selección recomendada

El menú utiliza flechas, Espacio para marcar y Enter para continuar. Los paquetes recomendados ya están seleccionados.

| Componente | Estado inicial y responsabilidad |
| --- | --- |
| Superpowers | Activo: único coordinador del proceso |
| Ponytail | Activo: simplicidad y revisión dentro del proceso elegido |
| UI UX Pro Max | Activo: usabilidad, responsive y accesibilidad |
| Anthropic Skills | Activo: frontend-design y webapp-testing |
| Addy Osmani Agent Skills | Activo: documentación oficial, seguridad y rendimiento |
| Matt Pocock Skills | Opcional, desmarcado: handoff y diseño de módulos, o coordinador alternativo |
| Graphify | Opcional, desmarcado: mapa consultable, solo bajo pedido |
| Vercel React Best Practices | Recomendado para React/Next.js |
| Web Design Guidelines | Recomendado para web |
| Composition Patterns | Opcional, bajo pedido |
| Next Best Practices | Referencia solo cuando se elige Next.js |
| Supabase Postgres Best Practices | Referencia solo cuando se elige Postgres |

Podés elegir varios asistentes: Copilot, Codex, Claude Code, Cursor y OpenCode. Todos reciben el mismo contrato, con un asistente principal y un coordinador único. Seleccionar un asistente instala sus archivos de configuración; no instala ese producto ni contrata un modelo.

Las opciones avanzadas permiten elegir skills individuales dentro de los paquetes seleccionados. Las opciones incompatibles con el stack se omiten. Para quitar la skill del coordinador, primero elegí Proceso simple.

El preset inicial es **Equilibrado**: acordar el enfoque y ejecutar lo acordado; pruebas que reproduzcan lógica y bugs; comprobaciones adecuadas para cambios visuales/configuración. Subagentes desactivados y diseño existente conservado. Ágil aumenta autonomía; Riguroso exige TDD para cambios de comportamiento y revisión por hitos.

## Reglas compartidas

`.createapp/POLICY.md` expresa las excepciones configuradas a los procesos originales:

- Un coordinador. Si elegís Matt, reemplaza el flujo de Superpowers.
- Un plan por funcionalidad y una revisión final consolidada.
- Una política común de pruebas y autonomía, sin entrevistas ni aprobaciones duplicadas.
- Un sistema visual: UI UX orienta usabilidad, Anthropic aporta identidad y Vercel revisa.
- Las reglas de Next.js no se aplican a Vite; los patrones dependen de la versión instalada.
- Ponytail simplifica sin recortar requisitos, seguridad o accesibilidad.
- Los especialistas no abren otros procesos de coordinación recursivamente.
- Graphify no inicia análisis, watchers, servicios o llamadas a modelos automáticamente.

Se generan **perfiles locales adaptados `ca-*`**. Los originales se conservan sin modificar como referencias fijadas por commit, fuera de las carpetas que descubren skills. No se instalan los plugins oficiales completos, sus hooks, dashboards ni comandos nativos.

Estas instrucciones reducen solapamientos; no garantizan obediencia de un LLM ni neutralizan plugins globales. Si un plugin global contradice el contrato, desactivalo en esa sesión o aplicá las excepciones mediante el mecanismo de tu asistente. CreateApp no modifica instalaciones globales.

## Qué cambia en tu proyecto

- `.createapp/`: selección, contrato, guía de uso y fuentes originales verificadas.
- `.agents/skills/ca-*/` para los asistentes que comparten esa convención.
- `.claude/skills/ca-*/` si seleccionaste Claude.
- Una referencia al contrato en AGENTS.md y en el archivo propio de los asistentes seleccionados.
- `.gitignore`: agrega únicamente la carpeta de herramientas opcionales de CreateApp.

Las instrucciones existentes se conservan y se les agrega el bloque CreateApp. El código de tu app, package.json, dependencias, README y guía propia no se modifican. Los archivos de configuración en conflicto detienen la operación.

Esta versión hace la **primera configuración**. No reemplaza una instalación `.createapp` existente. Para cambiar una selección, generá en una copia del proyecto y compará sus archivos; editar config.json por sí solo no reinstala perfiles. No hay actualizaciones automáticas.

## Funciones sin Python externo y herramientas opcionales

El ejecutable incluye Python y las fuentes seleccionadas. Puede ejecutar el buscador de UI UX Pro Max así:

```sh
createapp . --ux-search "minimal productivity app" --design-system
```

Este comando verifica los scripts contra el catálogo fijado antes de ejecutarlos. Los datos y referencias quedan junto al buscador. No necesita Python externo.

Graphify conserva una instalación separada y manual. Al seleccionarlo se prepara `.createapp/setup_graphify.py`, que necesita Python 3.10+ para crear su entorno local e instalar `graphifyy==0.9.95`. La referencia de Graphify está fijada por commit por separado; no se afirma identidad exacta con el paquete PyPI. No se ejecuta `graphify install`, para evitar registrar otro perfil.

Las pruebas Python/Playwright de Anthropic también necesitan sus herramientas si se ejecutan literalmente. El asistente debe reutilizar su herramienta de navegador disponible cuando corresponda. `--doctor` informa requisitos; no los instala ni afirma que estén comprobados por encontrar un nombre en PATH.

## Fuentes y skills.sh

Catálogo revisado el 24 de octubre de 2026. Se buscaron skills en [skills.sh](https://skills.sh) y se incorporaron fuentes originales de [Vercel](https://github.com/vercel-labs/agent-skills), [Vercel openreview](https://github.com/vercel-labs/openreview) y [Supabase](https://github.com/supabase/agent-skills).

`source-cache/` incluye las fuentes revisadas para poder configurar sin conexión. `sources.lock.json` fija sus commits y hashes de blob Git. Las fuentes se preparan antes de escribir el proyecto y se verifica su contenido; no se ejecutan scripts al instalarlas.

Algunas referencias, como Web Design Guidelines, proponen consultar documentación remota actualizada al usarlas. Esa consulta dinámica se trata como referencia y no queda fijada por el hash del pack.

## Desarrollo y publicación

Para trabajar sobre el código fuente sí necesitás Python; esto no afecta al usuario del ejecutable:

```sh
python -m pip install -r requirements-build.txt
python -m unittest discover -s tests -v
python createapp.py .
python createapp.py . --ui
python scripts/build.py
```

PyInstaller compila para el sistema donde se ejecuta. El workflow `.github/workflows/release.yml` prepara Linux x64/arm64, Windows x64 y macOS Intel/Apple Silicon en runners nativos. Cada build verifica el ejecutable con PATH vacío, configura un proyecto de prueba y ejecuta el buscador UI/UX con su runtime incluido.

Al subir un tag `v*`, el workflow construye todas las variantes y crea una **release en borrador** con assets, instaladores y SHA256SUMS. Se publica después de revisar los resultados. `workflow_dispatch` permite generar artifacts sin crear una release. Ver [docs/RELEASE.md](docs/RELEASE.md).

No hay firma de código ni notarización de Apple configuradas. Windows/macOS y las arquitecturas ARM no están validados por el build local Linux. Linux depende de glibc: la release de CI usa Ubuntu 22.04; el ejecutable local incluido se construyó en glibc 2.39 y no acredita soporte para distribuciones anteriores o Alpine/musl.

## Verificación y licencia

Ver [docs/VALIDATION.md](docs/VALIDATION.md) para resultados y límites. El código propio es MIT; las fuentes y runtimes conservan sus licencias, incluidas en la distribución.
