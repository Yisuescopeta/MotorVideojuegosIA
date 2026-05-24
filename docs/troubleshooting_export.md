# Troubleshooting: Export Pipeline

Guia de diagnostico y solucion para problemas comunes de exportacion.

## Doctor primero

Siempre ejecuta `doctor` antes de diagnosticar:

```bash
py -m motor export doctor --project . --json
```

El campo `healthy` indica si el entorno esta listo para builds reales:

```json
{
  "success": true,
  "data": {
    "healthy": false,
    "issues": ["PyInstaller not found"],
    "warnings": ["pip not importable"]
  }
}
```

`healthy: false` significa que los builds reales fallaran con
`TOOLCHAIN_UNAVAILABLE`, pero el pipeline genera artefactos estructurales
(content pack, proyecto Android, report).

## Errores comunes

### TOOLCHAIN_UNAVAILABLE

El build requiere una herramienta externa que no esta instalada.

#### PyInstaller not found

```bash
py -m pip install pyinstaller
```

Desktop builds (Windows, Linux, macOS) requieren PyInstaller.
Usa el mismo interprete que reporta `python_executable` en
`py -m motor export doctor --project . --json`.

#### ANDROID_HOME not set

```bash
# Windows
set ANDROID_HOME=C:\Users\<user>\AppData\Local\Android\Sdk

# Linux/macOS
export ANDROID_HOME=~/Android/Sdk
```

Android builds requieren Android SDK.

#### Java not found

```bash
# Instalar JDK 11+ (sdkman, apt, brew, o Android Studio)
sdk install java 17.0.0-tem
```

#### Gradle not found

```bash
sdk install gradle 8.5
```

O usar el wrapper incluido en el template Android.

#### macOS export requires a macOS host

Exporta macOS desde una Mac o usa CI con runners macOS (GitHub Actions
`macos-latest`). Exportar macOS desde Windows/Linux no es posible.

#### iOS export requires macOS and Xcode

Igual que macOS, requiere macOS host. Ademas requiere Xcode 15+ y Apple
Developer account para distribucion.

### ENTRY_SCENE_NOT_FOUND

La escena inicial definida en el preset no existe:

```json
{
  "code": "ENTRY_SCENE_NOT_FOUND",
  "path": "levels/main_menu_scene.json",
  "hint": "Create the scene or update export_presets.motor.json"
}
```

**Solucion:**
1. Verifica que la escena existe en `levels/`.
2. Corrige `entry_scene` en `export_presets.motor.json`.
3. O crea la escena: `py -m motor scene create "Main Menu" --project . --json`.

### UNSAFE_OUTPUT_PATH

El `output_path` del preset contiene rutas absolutas o traversal (`../`) fuera
del proyecto:

```json
{
  "code": "UNSAFE_OUTPUT_PATH",
  "path": "/home/user/Desktop/MyGame",
  "hint": "Use a relative path within the project, e.g. dist/export/windows/MyGame"
}
```

**Solucion:** usa rutas relativas dentro del proyecto como
`dist/export/windows/MyGame`.

### UNKNOWN_PRESET_FIELD

El preset contiene un campo no reconocido por el schema:

```json
{
  "code": "UNKNOWN_PRESET_FIELD",
  "field": "graphics_api",
  "hint": "Remove unknown field or use 'extra' for platform-specific options"
}
```

**Solucion:** elimina el campo o muevelo a `extra`.

### CONTENT_PACK_NOT_FOUND (runtime)

El runtime exportado no encuentra `game.pak` ni `content/`:

```
ERROR: CONTENT_PACK_NOT_FOUND - Neither game.pak nor content/ found
```

**Causas:**
- El build no genero content pack (fallo en fase de pack).
- El content pack no se copio al directorio de salida.
- Se intento ejecutar el runtime sin build previo.

**Solucion:** ejecuta `py -m motor export pack "Preset" --project . --json`
y verifica que `.motor/build/staging/<preset>/game.pak` existe.

## Diagnostico de toolchains

### Verificar PyInstaller

```bash
pyinstaller --version
pip show pyinstaller
```

### Verificar Android SDK

```bash
echo %ANDROID_HOME%              # Windows
echo $ANDROID_HOME               # Linux/macOS
ls %ANDROID_HOME%\platforms       # Ver SDK platforms
ls %ANDROID_HOME%\build-tools     # Ver build-tools
```

### Verificar Java

```bash
java -version
echo %JAVA_HOME%                 # Windows
echo $JAVA_HOME                  # Linux/macOS
```

### Verificar Gradle

```bash
gradle --version
```

## Modo debug para diagnosticos

El modo `debug` en presets incluye mas assets, tooling IA y excluye menos
archivos. Util para diagnosticar problemas de grafo de contenido:

```json
{
  "mode": "debug",
  "include_debug_tools": true,
  "include_all_assets": true
}
```

```bash
py -m motor export build "Windows Debug" --project . --json
```

## Validacion paso a paso

Para aislar problemas, ejecuta cada fase por separado:

```bash
# 1. Validar presets
py -m motor export presets validate --project . --json

# 2. Validar un preset especifico
py -m motor export presets validate --project . --name "Windows Desktop" --json

# 3. Doctor (toolchains)
py -m motor export doctor --project . --json

# 4. Content pack (sin build de plataforma)
py -m motor export pack "Windows Desktop" --project . --json

# 5. Build completo
py -m motor export build "Windows Desktop" --project . --json
```

Si `pack` funciona pero `build` falla, el problema esta en el exporter de
plataforma, no en el content pack.

## Content pack: assets faltantes

Si el juego exportado no carga ciertos assets en runtime:

1. Verifica que los assets estan referenciados estaticamente en escenas JSON
   (`texture_path`, `asset_path`, `sprite_sheet`, etc.).
2. Assets cargados dinamicamente por scripts Python (`load_texture(nombre)`)
   no se detectan automaticamente.
3. Usa `include_all_assets: true` en el preset para incluirlos todos.
4. Usa `mode: "debug"` para incluir tooling y exclusión menos agresiva.

```bash
# Inspeccionar manifiesto generado
cat .motor/build/staging/Windows_Desktop/game.manifest.json
```

## Reportes de build

Los build reports quedan en `.motor/build/export_reports/`. Incluyen:

- Artefactos con hashes SHA-256.
- Warnings y errores accionables.
- Duracion y timestamps.
- Entorno (Python, OS, toolchains).

```bash
# Leer ultimo report
ls .motor/build/export_reports/ | sort | tail -1
cat .motor/build/export_reports/<ultimo>.json
```

Los reports estan sanitizados: credenciales y keystores aparecen como
`[REDACTED]`.

## Runtime exportado: windowed no arranca

Si el ejecutable exportado falla en modo windowed:

1. Verifica la configuracion y la entry scene:

```bat
My_Game.exe --print-runtime-info
```

2. Ejecuta el smoke test headless:

```bat
My_Game.exe --smoke-test
```

Este smoke test no valida ventana real, render, input real ni UI interactiva.

3. Ejecuta el modo windowed real y revisa el codigo de salida:

```bat
My_Game.exe
echo %ERRORLEVEL%
```

4. Verifica que `pyray` esta instalado en el entorno de build:

```bash
py -c "import pyray; print('pyray OK')"
```

5. Si no esta, el runtime retorna codigo 2: `TOOLCHAIN/RUNTIME_UNAVAILABLE`.
   Si raylib esta pero no se crea ventana, retorna codigo 2 con
   `ERROR: raylib window was not created`.
6. Instala `raylib` nativa y `pyray`:

```bash
py -m pip install raylib pyray
```

## Runtime exportado: crash o freeze

1. Ejecuta smoke test: `MyGame.exe --smoke-test`.
   - El smoke test ejecuta `verify_integrity()` primero. Si retorna codigo 3,
     el content pack esta corrupto o tiene archivos faltantes.
2. Si smoke test falla, el problema esta en la carga de escena o fisica.
3. Ejecuta con `--headless --frames 1 --print-runtime-info` para ver informacion
   de carga sin simulacion larga.
4. Verifica que la entry scene existe en el content pack.
5. Verifica que el content pack incluye todos los assets referenciados.

## CI y automatizacion

Para CI, ejecuta en orden:

```bash
py -m motor export presets validate --project . --json
py -m motor export doctor --project . --json
py -m motor export pack "Windows Desktop" --project . --json
py -m motor export build "Windows Desktop" --project . --json
```

El exit code es 0 si `success: true`, 1 si `success: false`. Los reports quedan
en `.motor/build/export_reports/` para post-procesamiento.

## Errores no cubiertos

Si encuentras un error no listado aqui:

1. Ejecuta `py -m motor export doctor --project . --json` y guarda la salida.
2. Ejecuta `py -m motor export presets validate --project . --json`.
3. Revisa el build report en `.motor/build/export_reports/`.
4. Abre un issue en el repo con la salida JSON de los 3 comandos.

No uses scripts sueltos ni modifiques `export_presets.motor.json` sin pasar por
validacion — los errores de schema se detectan pero no previenen el commit.

## Content pack: verificacion de integridad

El content pack incluye verificacion de integridad automatica:

- `verify_pak()` se ejecuta despues de `write_pak()` durante el build.
- Si detecta archivos corruptos o con hash incorrecto, el build falla con
  `Content pack integrity check failed`.
- En runtime, `--smoke-test` ejecuta `ContentLoader.verify_integrity()`.
- Si la integridad falla en runtime, el smoke test retorna codigo 3 y lista
  los archivos corruptos/faltantes.

Para verificar manualmente:

```bash
# Verificar content pack generado
py -m motor export pack "Windows Desktop" --project . --json
# Si falla con error de integridad, revisa game.manifest.json y game.pak
```

## Android: errores de keystore

Los errores de keystore usan codigos accionables:

### ANDROID_KEYSTORE_MISSING
El preset no tiene configurado `keystore_path` en `extra`:
```json
{
  "extra": {
    "keystore_path": "keystore/release.keystore",
    "keystore_password": "...",
    "key_alias": "mygame"
  }
}
```

### ANDROID_KEYSTORE_NOT_FOUND
El archivo de keystore no existe en la ruta configurada.
- Verifica que la ruta relativa apunte a un archivo existente.
- Crea un keystore con: `keytool -genkey -v -keystore release.keystore ...`

El `build.gradle` generado NUNCA contiene rutas absolutas de keystore ni
passwords. Usa `rootProject.file('keystore.jks')` y variables de entorno
(`RELEASE_STORE_PASSWORD`, `RELEASE_KEY_PASSWORD`) exclusivamente.
