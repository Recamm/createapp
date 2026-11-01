# Validación de CreateApp

## 0.2.2: skills incrementales en Windows

Fecha: 1 de noviembre de 2026.

- 64 pruebas ejecutadas: 61 aprobadas y 3 omitidas (enlaces simbólicos no disponibles y dos pruebas del instalador POSIX).
- Detección de perfiles instalados; selección exclusivamente de skills faltantes compatibles, sin cambiar asistentes ni coordinador. Menú, API autenticada y CLI con `--add-skills` y `--dry-run`.
- Conservación de perfiles, instrucciones, política anterior y versiones de fuentes. Las fuentes agregadas se guardan en snapshots separados; prueba con un commit nuevo del mismo proveedor sin reemplazar el anterior.
- Cancelación y selección vacía sin escrituras. Repetición sin reinstalación. Fallos de descarga y escritura con rollback; rechazo de cambios entre vista previa, confirmación y preparación.
- Navegador integrado Chromium sobre un proyecto temporal: primera configuración sin Debug, reapertura con solo faltantes, agregado real de Debug y Find Skills, reapertura sin ofrecerlas de nuevo. Vista a 390 px sin desbordamiento horizontal.
- Compilación Windows x64 con PyInstaller 6.22.3 y Python 3.11.9. Smoke del binario con PATH vacío: primera configuración, vista previa incremental, agregado de UX y Find Skills, preservación de archivos y fuentes previas, repetición con cero agregados y buscador UX desde el snapshot nuevo.
- Paquete local verificado por SHA-256 e instalación de 0.2.2 conservando un respaldo del ejecutable anterior. Sin Python ni Node externos para configurar o agregar skills.

Pendiente: publicar una release pública 0.2.2 para distribuir el catálogo y esta función a otros equipos. No se hicieron commit, push ni publicación. Los demás sistemas requieren sus runners nativos. La prueba de navegador fue en Chromium integrado, no Safari/iPhone real; el script completo de smoke de navegador se actualizó, pero no se ejecutó aquí como proceso independiente.

## 0.2.1: verificación local en Windows

Fecha: 1 de noviembre de 2026.

- 53 pruebas ejecutadas: 50 aprobadas y 3 omitidas (enlaces simbólicos no disponibles y dos pruebas del instalador POSIX).
- Compilación nativa Windows x64 con PyInstaller 6.22.3 y Python 3.11.9, en un entorno de build aislado.
- El ejecutable debe responder con la versión exacta del código y generar todos los paquetes del catálogo. La comprobación de build verifica los perfiles ca-* y sus referencias originales, incluidos Impeccable y Find Skills.
- Ejecución del binario con PATH vacío: generación de 15 perfiles y 299 fuentes, diagnóstico y buscador UI/UX. No requiere Python ni Node externos.
- Reproducción del problema de distribución: la instalación pública 0.2.0 solo contenía siete paquetes. Reinstalar esa misma release no incorporaba los cambios de main.
- Instalación local de 0.2.1 a partir del archivo Windows verificado por SHA-256, preservando el ejecutable anterior. El comando instalado abre el menú interactivo.
- Interfaz del ejecutable instalado: nueve paquetes disponibles; Impeccable y Find Skills son opcionales y ambos perfiles aparecen en la vista previa al seleccionarlos, sin aplicar cambios al repositorio.
- Corrección de la validación HTML del nombre para navegadores con expresiones regulares en modo Unicode v; acepta nombres con guiones y rechaza caracteres fuera del formato admitido.

El paquete local no reemplazó la release pública. El reemplazo mediante el actualizador interactivo se cubrió con mocks, no con una actualización automática real; los demás sistemas requieren sus runners nativos.

## 0.2.0: registro histórico

Fecha: 24 de octubre de 2026.

Comprobado en esta entrega:

- 25 pruebas automatizadas del motor, servidor, selecciones, preservación de archivos, cancelación y scripts de instalación POSIX.
- Selección de varios asistentes con un único contrato y skills individuales; los originales de la app se conservan.
- Compilación real Linux x64 con PyInstaller 6.22.3.
- Ejecución del binario con PATH vacío: versión, configuración real, diagnóstico y buscador UI/UX. No utiliza Python ni Node externos para esas operaciones.
- Menú real de terminal en un PTY, con los valores iniciales seleccionados y cancelación sin escritura.
- Interfaz Chromium: presets, Matt opcional, coordinador alternativo, dos asistentes, desactivar una skill individual y configurar un proyecto existente.
- Preservación de package.json y un archivo de aplicación durante la prueba de navegador.
- Interfaz a 390 px sin desbordamiento horizontal. No equivale a Safari/iPhone real.
- Instalador POSIX con una release simulada: instalación correcta y rechazo de un archivo cuyo checksum no coincide.
- Fuentes revisadas disponibles en la caché; verificación por hash antes de usarlas.

Pendiente:

- Ejecución de GitHub Actions: consultar el resultado de cada commit en https://github.com/Recamm/createapp/actions. La verificación local no sustituye esos resultados.
- Compilar, probar y distribuir Windows, macOS y Linux ARM64 en sus runners. Los workflows están preparados; estos builds no se ejecutaron localmente.
- Ejecutar install.ps1 en Windows. El workflow de pruebas analiza su sintaxis en su runner, pero aún no se ejecutó en GitHub.
- Firma de código y notarización de los ejecutables.
- Prueba WebKit/Safari/iPhone: faltan dependencias WebKit en el entorno de comprobación.
- Verificar la obediencia de los asistentes con un modelo real. Los archivos y adaptadores se comprobaron; un LLM puede ignorar instrucciones.
- Instalar y ejecutar Graphify completo, que sigue siendo opcional y tiene requisitos propios.

El ejecutable Linux local se compiló en glibc 2.39. La release de CI se configura con Ubuntu 22.04 para ampliar la compatibilidad, pero ese build todavía debe ejecutarse y verificarse.
