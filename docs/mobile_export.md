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
  "min_sdk": 23,
  "target_sdk": 35,
  "orientation": "landscape",
  "bundle_mode": "packed",
  "include_debug_tools": true
}
```

Campos obligatorios Android: `application_id`. Campos obligatorios release:
`version_code`.

### Build

```bash
# Build debug (APK)
py -m motor export build "Android Debug" --project . --json

# Build release (APK firmado + AAB)
py -m motor export build "Android Release" --project . --json
```

### Debug

1. Valida `ANDROID_HOME`, JDK, Gradle.
2. Genera proyecto Android desde `platforms/android/template/`.
3. Copia content pack a `app/src/main/assets/`.
4. Genera `AndroidManifest.xml` con `application_id`, `version_code`, orientacion.
5. Ejecuta `gradlew assembleDebug` si existe wrapper; si no, `gradle assembleDebug`.
6. Copia APK a `dist/export/android/`.
7. Genera build report.

### Release

1. Todos los pasos de debug.
2. Valida keystore desde `extra.keystore_path`.
3. Configura signing en `app/build.gradle`.
4. Ejecuta `gradlew assembleRelease`/`bundleRelease` si existe wrapper; si no, `gradle`.
5. Copia APK firmado y AAB a `dist/export/android/`.
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
`{{ORIENTATION}}`) en los archivos de template.

El template Android incluye un runtime Kotlin nativo v1 con `SurfaceView`.
Carga `runtime_config.json`, escenas JSON y assets desde `app/src/main/assets/`.
Soporta el primer APK jugable para menu UI, cambio de escena, camara,
animacion spritesheet basica, fisica AABB, `PlayerController2D`, `InputMap` y
`MobileControls2D`.

Limitacion v1: no ejecuta `ScriptBehaviour` Python ni sistemas avanzados como
audio, tilemap, particulas, luces, navegacion o tweens. El exporter falla con
errores `ANDROID_RUNTIME_UNSUPPORTED_*` si una escena Android usa capacidades
todavia no portadas, para evitar APKs silenciosamente no jugables.

## Controles moviles

```bash
py -m motor mobile controls add --target Player --profile platformer --project . --json
py -m motor mobile controls add --scene levels/platformer_test_scene.json --target Player --profile platformer --project . --json
```

Este comando crea un overlay `MobileControls2D` serializable. En runtime,
`MobileControlsSystem` traduce touch/pointer a `InputMap.last_state` del
`target_entity`. En Android v1, el exporter exige que toda escena reachable con
`InputMap` + `PlayerController2D` tenga un overlay `MobileControls2D` apuntando
a esa entidad. Es modulo interno del motor, no dependencia externa.

### Sin Android SDK

Si el entorno no tiene `ANDROID_HOME`:

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
| `ANDROID_HOME` | Variable de entorno | Android exports bloqueados |
| `java` | `shutil.which("java")` | Android builds requieren JDK |
| `gradle` | `shutil.which("gradle")` o wrapper local | Compilacion Android requiere Gradle |
| macOS host | `platform.system() == "Darwin"` | iOS exports requieren macOS |
| Xcode | `shutil.which("xcodebuild")` | iOS compilacion requiere Xcode |

```bash
py -m motor export doctor --project . --json
# {
#   "success": false,
#   "data": {
#     "healthy": false,
#     "issues": ["ANDROID_HOME not set", "macOS required for iOS"],
#     "warnings": ["Gradle not found in PATH"]
#   }
# }
```

## Limitaciones reales

- **Android real build**: requiere Android SDK, JDK 11+ y Gradle. Sin ellos, se
  genera proyecto estructural pero no APK/AAB.
- **Android jugable v1**: usa runtime Kotlin nativo. Soporta menu, escena
  platformer basica, sprites/rect fallback, camara, fisica AABB y controles
  moviles. `ScriptBehaviour` Python queda para la siguiente fase.
- **Android release signing**: requiere keystore configurado en `extra`.
- **iOS real build**: requiere macOS, Xcode y Apple Developer account. Nunca
  compila automaticamente desde el pipeline.
- **Python en movil**: si `raylib-py` no soporta iOS/Android de forma estable,
  el runtime movil queda documentado como bloqueador y se prepara diseno para
  runtime nativo progresivo.
