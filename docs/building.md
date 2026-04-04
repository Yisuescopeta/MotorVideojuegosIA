# Build y Distribucion - MotorVideojuegosIA (Windows)

## Build Settings del proyecto (PMV)

El motor ahora incluye una base de configuracion de build por proyecto en `settings/build_settings.json`.

Este archivo define el primer contrato serializable para exportar un juego jugable, inspirado en Unity Build Settings, pero todavia sin empaquetado final ni UI de editor.

Campos soportados en este PMV:

- `product_name`
- `company_name`
- `startup_scene`
- `scenes_in_build`
- `target_platform`
- `development_build`
- `include_logs`
- `include_profiler`
- `output_name`

Reglas importantes:

- `target_platform` soporta solo `windows_desktop` en esta fase.
- `scenes_in_build` mantiene el orden definido por el proyecto.
- `startup_scene` debe existir dentro de `scenes_in_build`.
- Las rutas de escenas se normalizan a rutas relativas al proyecto.
- `include_profiler` solo es valido cuando `development_build` esta activado.

## Build Manifest del proyecto (PMV)

La configuracion de build se resuelve a un manifest determinista en memoria. Este manifest representa la configuracion final que futuras etapas del pipeline usaran para generar el player.

El manifest incluye al menos:

- esquema y version
- `product_name`
- `company_name`
- `target_platform`
- `startup_scene`
- `scenes_in_build`
- flags de desarrollo
- `generated_at_utc`
- metadata de salida relativa al proyecto
- referencias reservadas a artefactos como `content_bundle.json`, `asset_build_report.json` y reportes futuros del player build

## Prebuild y seleccion de contenido

Antes de empaquetar un player, el motor puede ejecutar una etapa de prebuild que valida la configuracion y decide que contenido entra realmente en el build.

La regla principal es explicita:

- las escenas incluidas son exactamente `scenes_in_build`
- `startup_scene` debe estar dentro de esa lista y existir
- el resto del contenido se selecciona solo por cierre de dependencias desde esas escenas

Contenido seleccionado por el prebuild:

- escenas listadas en `scenes_in_build`, respetando su orden
- prefabs, scripts y assets alcanzables desde esas escenas o desde prefabs dependientes
- metadata minima de runtime y build: `project.json`, `settings/build_settings.json` y el path reservado del build manifest

Contenido omitido por el prebuild:

- escenas del proyecto que no esten en `scenes_in_build`
- prefabs, scripts y assets que no formen parte del cierre de dependencias
- cualquier archivo del proyecto no alcanzable desde la raiz del build

El prebuild no copia toda la carpeta del proyecto. Si una escena seleccionada referencia otra escena fuera de `scenes_in_build`, eso se reporta como error bloqueante en lugar de auto-incluirla.

## Runtime standalone empaquetado

El runtime exportado ahora tiene una ruta de arranque separada del flujo editor/proyecto. El objetivo es que un juego distribuido pueda arrancar desde una carpeta de build sin depender del proyecto editable original.

Contrato minimo del build standalone:

- `<build root>/<output_name>.exe`
- `<build root>/runtime/runtime_manifest.json`
- `<build root>/runtime/metadata/build_manifest.json`
- `<build root>/runtime/content/...`

El `runtime_manifest.json` es el contrato de ejecucion del player empaquetado. Define:

- esquema y version del runtime
- `target_platform`
- `startup_scene` relativa a `runtime/content`
- `content_root` y `metadata_root` relativos al build root
- referencia relativa al `build_manifest.json`
- resumen opcional del contenido seleccionado

Diferencia entre runtime empaquetado y runtime de editor:

- el editor sigue usando `ProjectService` y el layout del proyecto editable
- el runtime empaquetado no usa launcher, editor state ni `os.getcwd()` como fuente de verdad
- la resolucion de contenido se hace solo dentro de `runtime/content`
- si falta manifest o contenido empaquetado, el bootstrap falla con diagnosticos explicitos

Tradeoff del PMV:

- se reutiliza el stack de `Game`/`SceneManager`/sistemas de runtime existente
- no se reutiliza el flujo completo de proyecto editable
- el player exportado usa un bootstrap y layout dedicados, no una copia completa del proyecto

## Build Player Windows Desktop (PMV)

El motor ahora incluye una primera ruta real de `Build Player` orientada a juego exportado, separada del build del editor.

Alcance actual:

- solo `windows_desktop`
- solo export folder-based
- sin instalador
- sin onefile
- sin updater ni patching

Flujo del pipeline:

1. carga y valida `settings/build_settings.json`
2. ejecuta prebuild y valida `scenes_in_build`
3. construye artifacts y `content_bundle`
4. empaqueta el launcher standalone con PyInstaller
5. copia solo el contenido seleccionado por dependencia
6. escribe `runtime_manifest`, `build_manifest`, reportes y metadata del export

Como decidir que entra en el build:

- las escenas incluidas son exactamente `scenes_in_build`
- `startup_scene` debe estar en esa lista y existir
- prefabs, scripts y assets entran solo si forman parte del cierre de dependencias
- no se copia la carpeta completa del proyecto

Como ejecutar el Build Player:

```bash
py -3 tools/engine_cli.py build-player --project-root C:\ruta\al\proyecto
```

Opciones utiles:

- `--out <ruta>` para forzar la carpeta de export
- `--json` para imprimir el `BuildReport` en formato JSON

Comandos CLI relacionados:

```bash
py -3 tools/engine_cli.py build-settings show --project-root C:\ruta\al\proyecto
py -3 tools/engine_cli.py build-settings set --project-root C:\ruta\al\proyecto --product-name "Mi Juego" --scene levels/main_scene.json --startup-scene levels/main_scene.json
py -3 tools/engine_cli.py prebuild-check --project-root C:\ruta\al\proyecto
py -3 tools/engine_cli.py build-player --project-root C:\ruta\al\proyecto --json --report-out artifacts\build_report.json
```

Notas de automatizacion:

- `build-settings show`, `build-settings set`, `prebuild-check` y `build-player` soportan `--json`
- `build-settings show`, `build-settings set` y `prebuild-check` aceptan `--out` para escribir el payload JSON a disco
- `build-player` acepta `--report-out` para escribir el `BuildReport` JSON mientras `--out` sigue reservandose para la carpeta exportada
- `prebuild-check` devuelve `0` si el prebuild es valido y `2` si hay errores bloqueantes
- `build-player` devuelve `0` si el export termina bien y `1` si el build falla
- errores de setup de CLI se devuelven como payload JSON con `status: failed` cuando se usa `--json`

Shape minimo del export:

- `<output_root>/<output_name>.exe`
- `<output_root>/runtime/runtime_manifest.json`
- `<output_root>/runtime/metadata/build_manifest.json`
- `<output_root>/runtime/metadata/prebuild_content_report.json`
- `<output_root>/runtime/metadata/asset_build_report.json`
- `<output_root>/runtime/metadata/content_bundle.json`
- `<output_root>/runtime/metadata/bundle_report.json`
- `<output_root>/runtime/metadata/build_report.json`
- `<output_root>/runtime/content/...`

Development Build:

- cuando `development_build` esta apagado, el export no incluye extras de desarrollo
- cuando `development_build` esta activo, el export agrega `runtime/dev/development_options.json`
- si `include_logs` tambien esta activo, se crea `runtime/dev/logs/`
- `include_profiler` se expone solo como flag de runtime para builds de desarrollo; no cambia el target soportado

Limitaciones intencionales del PMV:

- no genera instalador
- no soporta otras plataformas
- no empaqueta todo en un unico archivo
- no intenta recuperarse silenciosamente si PyInstaller o el contenido empaquetado fallan
- el flujo antiguo `build/build_windows.py` sigue siendo el empaquetado del editor/distribucion, no el Build Player por proyecto

Fuera de alcance en este PMV:

- instaladores
- UI de editor para editar Build Settings
- soporte multi-plataforma adicional

## Requisitos

- Python 3.11+
- PyInstaller: `pip install pyinstaller`
- Inno Setup 6 (solo para generar instalador): https://jrsoftware.org/isinfo.php

## Generar ejecutable

```bash
python build/build_windows.py
```

Genera `dist/MotorVideojuegosIA/MotorVideojuegosIA.exe` (carpeta con todo incluido).

## Generar ejecutable + instalador

```bash
python build/build_windows.py --installer
```

Genera `dist/MotorVideojuegosIA-{version}-Setup.exe`.

Requiere Inno Setup 6 instalado (`ISCC.exe` en el `PATH` o en su ubicacion estandar).

## Publicar una nueva version

1. Editar la version en `engine/config.py`:
   ```python
   ENGINE_VERSION: str = "2026.04"
   ```
   Esta es la unica fuente de verdad. `pyproject.toml`, el instalador, la UI y el update checker la leen de ahi.

2. Generar build e instalador:
   ```bash
   python build/build_windows.py --installer
   ```

3. Crear GitHub Release:
   - Tag: `v2026.04` (o la version que corresponda)
   - Subir `dist/MotorVideojuegosIA-2026.04-Setup.exe` como asset
   - Marcar como latest release

4. Los usuarios existentes veran el boton verde `Update vX.Y` en la barra de menu del editor.

## Como funciona la comprobacion de actualizaciones

- Al arrancar, el motor lanza un thread que consulta la GitHub Releases API.
- Si hay una release mas nueva que `ENGINE_VERSION`, muestra un boton verde en la barra de menu.
- Al hacer click, abre el navegador con el enlace de descarga del instalador.
- Si no hay conexion o la API falla, no pasa nada: el motor funciona normalmente.
- No hay actualizacion automatica, ni servicio en background, ni reemplazo de binarios.

## Estructura de archivos de build

```text
build/
  motorvideojuegos.spec
  installer.iss
  build_windows.py
```

## Notas

- Windows SmartScreen puede advertir al ejecutar el instalador porque no esta firmado digitalmente.
- El ejecutable empaquetado pesa aproximadamente 30-50 MB.
- El working directory del acceso directo apunta a la carpeta de instalacion, necesario para que `os.getcwd()` funcione correctamente con los proyectos.
