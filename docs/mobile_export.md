# Mobile Export

Exportacion a plataformas moviles: Android e iOS.

## Android

### Requisitos

| Tool | Comprobacion | Instalacion |
|---|---|---|
| Android SDK | `ANDROID_HOME` o `ANDROID_SDK_ROOT` | [Android Studio](https://developer.android.com/studio) |
| JDK 11+ | `java -version` | `sdk install java 17.0.0-tem` o Android Studio JDK |
| Gradle | `gradle --version` o `gradlew/gradlew.bat` | `sdk install gradle 8.5` o wrapper incluido |

`motor export doctor` verifica estos requisitos y reporta `healthy: false`
cuando faltan.

### Configuracion de entorno

```bash
# Windows
set ANDROID_HOME=C:\Users\<user>\AppData\Local\Android\Sdk

# Linux/macOS
export ANDROID_HOME=~/Android/Sdk
export PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$PATH
```

### Preset Android

```json
{
  "name": "Android Debug",
  "platform": "android",
  "architecture": "arm64-v8a",
  "mode": "debug",
  "output_path": "dist/export/android/MyGame-debug.apk",
  "entry_scene": "levels/main_menu_scene.json",
  "display_name": "My Game",
  "application_id": "com.example.mygame",
  "version_name": "0.1.0",
  "version_code": 1,
  "min_sdk": 24,
  "target_sdk": 35,
  "compile_sdk": 35,
  "orientation": "landscape",
  "bundle_mode": "packed",
  "include_debug_tools": true,
  "android_python_runtime": true
}
```

Campos obligatorios Android: `application_id`. Campos obligatorios release:
`version_code`. Para escenas jugables con `InputMap` + `PlayerController2D`,
usa `android_python_runtime: true` y `min_sdk >= 24`; asi el APK ejecuta el
mismo runtime compartido que PLAY del editor.

### Build

```bash
# Build debug (APK)
py -m motor export build "Android Debug" --project . --json

# Build release (requiere configuracion de firma)
py -m motor export build "Android Release" --project . --json
```

### Debug

1. Valida la ruta de `ANDROID_HOME`/`ANDROID_SDK_ROOT`, la plataforma
   `android-{compile_sdk}`, build-tools, JDK y Gradle.
2. Genera proyecto Android desde `platforms/android/template/`.
3. Copia content pack a `app/src/main/assets/`.
4. Genera `AndroidManifest.xml` con `application_id`, `version_code`, orientacion.
5. Ejecuta `gradlew assembleDebug` si existe wrapper; si no, `gradle assembleDebug`.
   Android usa automaticamente el debug keystore para este tipo de build.
6. Copia `app/build/outputs/apk/debug/app-debug.apk` a
   `dist/export/android/`. Si Gradle usa otro nombre, selecciona el APK debug
   mas reciente sin mezclar artefactos release.
7. Genera build report.

### Release

1. Genera y valida el proyecto Android como en debug, sin usar la configuracion
   de firma debug.
2. Exige `extra.keystore_path` o `extra.local_release_signing: true`; si faltan
   ambos, falla con `ANDROID_RELEASE_SIGNING_REQUIRED` antes de ejecutar Gradle.
3. Configura signing en `app/build.gradle`.
4. Ejecuta `gradlew assembleRelease`/`bundleRelease` si existe wrapper; si no, `gradle`.
5. Copia preferentemente `app-release.apk` y `app-release.aab` desde las rutas
   release estandar de Gradle. Si usan otro nombre, selecciona el artefacto
   release mas reciente sin mezclar artefactos debug.
6. Report incluye hashes de artefactos y redaccion de keystore.

### Keystore config

```json
{
  "extra": {
    "keystore_path": "android/keystore.jks",
    "keystore_password": "storepass",
    "key_alias": "gamekey",
    "key_password": "keypass"
  }
}
```

Las credenciales se redactan automaticamente en build reports.

Para builds release locales se puede usar:

```json
{
  "extra": {
    "local_release_signing": true
  }
}
```

Esta opcion crea y reutiliza un keystore local bajo `.motor/android/`. Es
adecuada para pruebas locales, no para publicar. Para builds distribuibles usa
un `keystore_path` explicito y conserva sus credenciales fuera de los build
files.

### Template Android

El template vive en `platforms/android/template/`:

```
settings.gradle
build.gradle
gradle.properties
app/
  build.gradle
  src/main/
    AndroidManifest.xml
    assets/               # Content pack destino
    res/
      values/
        strings.xml
        styles.xml
      drawable/
        ic_launcher.png
    java/com/motorvideojuegos/
      MainActivity.kt
```

El exporter reemplaza placeholders (`{{APPLICATION_ID}}`, `{{DISPLAY_NAME}}`,
`{{VERSION_CODE}}`, `{{VERSION_NAME}}`, `{{MIN_SDK}}`, `{{TARGET_SDK}}`,
`{{COMPILE_SDK}}`, `{{ORIENTATION}}`) en los archivos de template.
`compile_sdk` controla `compileSdk`; `target_sdk` controla `targetSdk` dentro
de `defaultConfig`.

El template Android incluye un shell Kotlin con `SurfaceView`. Con
`android_python_runtime: true`, el shell extrae solo
`runtime_config.json`, `game.manifest.json`, `levels/`, `assets/` y `scripts/`
a `filesDir`, excluye siempre `chaquopy/`, arranca Chaquopy y delega la
simulacion a `SharedGameRuntime` (`Game` + `RuntimeController`), la misma ruta
que PLAY del editor. Kotlin queda limitado a input tactil, surface Android y
render del snapshot serializado. La copia usa `android_runtime_cache_key` del
`runtime_config.json`; si el contenido empaquetado y el runtime/template Android
relevante no cambian, se reutiliza en arranques posteriores. Si el runtime compartido falla, la APK muestra una pantalla de
error visible y escribe el detalle en Logcat con tag `MotorGame`.

El fallback Kotlin nativo v1 queda solo para escenas simples sin gameplay
avanzado. El exporter falla con `ANDROID_RUNTIME_REQUIRES_SHARED_RUNTIME` si una
escena Android reachable tiene `InputMap` + `PlayerController2D` sin
`android_python_runtime: true`. Tambien falla con `ANDROID_RUNTIME_UNSUPPORTED_*`
para capacidades no soportadas por el modo elegido, evitando APKs
silenciosamente no jugables.

## Controles moviles

```bash
py -m motor mobile controls add --target Player --profile platformer --project . --json
py -m motor mobile controls add --scene levels/platformer_test_scene.json --target Player --profile platformer --project . --json
```

Este comando crea un overlay `MobileControls2D` serializable. En runtime,
`MobileControlsSystem` traduce touch/pointer a `InputMap.last_state` del
`target_entity`. En Android, el exporter exige que toda escena reachable con
`InputMap` + `PlayerController2D` tenga un overlay `MobileControls2D` apuntando
a esa entidad y use el runtime Python compartido. Es modulo interno del motor,
no dependencia externa.

`MobileControls2D.movement_mode` controla la entrada izquierda: `"joystick"`
mantiene el eje analogico por defecto y `"dpad"` usa cruceta discreta de 4
direcciones, sin diagonales.

### Sin Android SDK

Si el entorno no tiene un SDK valido en `ANDROID_HOME` o `ANDROID_SDK_ROOT`:

- Tests unitarios de Android siguen pasando.
- `motor export doctor` reporta `healthy: false` con diagnostico.
- `motor export build` genera proyecto Android jugable en staging pero falla con
  `TOOLCHAIN_UNAVAILABLE`.
- El proyecto Android generado queda en staging para inspeccion.

## iOS

### Requisitos

- macOS (obligatorio).
- Xcode 15+ con command line tools.
- Apple Developer account (para distribucion).

Sin macOS, el exporter retorna `TOOLCHAIN_UNAVAILABLE` con instrucciones claras.

### Preset iOS

```json
{
  "name": "iOS Release",
  "platform": "ios",
  "architecture": "arm64",
  "mode": "release",
  "output_path": "dist/export/ios/MyGame",
  "entry_scene": "levels/main_menu_scene.json",
  "display_name": "My Game",
  "application_id": "com.example.mygame",
  "version_name": "0.1.0",
  "version_code": 1,
  "bundle_mode": "packed",
  "include_debug_tools": false
}
```

### Template iOS

El template estructural vive en `platforms/ios/template/`:

```
MyGame/
  MyGame.xcodeproj/
  MyGame/
    Info.plist
    AppDelegate.swift
    Assets.xcassets/
    Base.lproj/
```

### Build

```bash
# Genera proyecto Xcode (no compila automaticamente)
py -m motor export build "iOS Release" --project . --json
```

El exporter genera el proyecto Xcode estructural, copia el content pack y
configura `Info.plist` con `application_id`, version y orientacion. No compila
automaticamente porque requiere Apple Developer account y configuracion de
signing manual en Xcode.

### Sin macOS

Los tests estructurales de iOS pasan en cualquier SO. El exporter reporta
`TOOLCHAIN_UNAVAILABLE` con instrucciones para exportar desde macOS.

## Doctor mobile

`motor export doctor` verifica toolchains moviles:

| Check | Detecta | Impacto si falla |
|---|---|---|
| `android_sdk_available` | Variable de entorno apuntando a un SDK existente | Android exports bloqueados |
| `android_platform_available` | `platforms/android-{compile_sdk}` para cada preset | Falla con `ANDROID_PLATFORM_MISSING` |
| `android_build_tools_available` | Al menos una version bajo `build-tools/` | Falla con `ANDROID_BUILD_TOOLS_MISSING` |
| `java` | `shutil.which("java")` | Android builds requieren JDK |
| `gradle` | Wrapper completo y ejecutable o Gradle global | Compilacion Android requiere Gradle |
| `gradle_wrapper_executable` | Permiso ejecutable de `gradlew` en Unix | Requiere `chmod +x gradlew` o Gradle global |
| macOS host | `platform.system() == "Darwin"` | iOS exports requieren macOS |
| Xcode | `shutil.which("xcodebuild")` | iOS compilacion requiere Xcode |

```bash
py -m motor export doctor --project . --json
# {
#   "success": false,
#   "data": {
#     "healthy": false,
#     "issues": [
#       "ANDROID_PLATFORM_MISSING: Install Android SDK Platform 35"
#     ],
#     "checks": {
#       "android_build_tools_available": true,
#       "gradle_wrapper_executable": true,
#       "android_platforms": [{"compile_sdk": 35}]
#     }
#   }
# }
```

## Limitaciones reales

- **Android real build**: requiere Android SDK, JDK 11+ y Gradle. Sin ellos, se
  genera proyecto estructural pero no APK/AAB.
- **Android jugable**: las escenas con gameplay usan Chaquopy +
  `SharedGameRuntime`, por lo que power-ups `ScriptBehaviour`, plataformas
  moviles, fisica, semantica 2D y orden de sistemas siguen la ruta de PLAY del
  editor. Requiere `android_python_runtime: true` y `min_sdk >= 24`.
- **Animaciones Android**: el export incluye sidecars `*.meta.json` de assets
  alcanzables. El render Android resuelve `Animator.slice_names`,
  `Sprite.source_slice`, `flip_x`, `flip_y` y entidades con `Sprite` +
  `Animator`; animaciones avanzadas sin runtime compartido se bloquean con error
  explicito.
- **Android fallback v1**: el runtime Kotlin nativo queda limitado a escenas
  simples sin gameplay avanzado.
- **Android release signing**: requiere `extra.keystore_path` para builds
  distribuibles o `extra.local_release_signing: true` para pruebas locales. El
  exporter no ejecuta un build release sin una de estas opciones.
- **iOS real build**: requiere macOS, Xcode y Apple Developer account. Nunca
  compila automaticamente desde el pipeline.
- **Render Android**: Kotlin renderiza snapshots serializados; el rect visual
  usa `Sprite`/`Animator`, y el rect fisico usa `Collider`.
