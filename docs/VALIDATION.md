# Validación de CreateApp 0.2.0

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
