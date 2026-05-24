# Runtime Templates

El runtime exportado es el entrypoint del juego final. Esta separado del editor
y no incluye paneles, inspector, tooling IA, tests ni documentacion.

## Entrypoint

`engine/runtime/exported_game.py` es el entrypoint para juegos exportados.

El juego exportado arranca con:
1. `runtime_config.json` — configuracion de ventana, entry scene, modo.
2. `game.manifest.json` — manifiesto con hashes SHA-256 y assets.
3. `game.pak` o `content/` — assets, escenas, scripts empaquetados.

El runtime no importa `engine.editor`, `engine.inspector`, `tools`, `tests`,
`docs` ni `main.py`.

## Flags de runtime

```bash
MyGame.exe                              # Normal (windowed, requiere pyray)
MyGame.exe --smoke-test                 # Headless smoke test (60 frames)
MyGame.exe --headless --frames 3        # Headless con N frames
MyGame.exe --print-runtime-info         # Info de runtime y salida
```

### Modo windowed

Requiere `pyray` o `raylib`. Sin ellos, retorna codigo 2 con mensaje
`TOOLCHAIN/RUNTIME_UNAVAILABLE`. Si raylib esta disponible pero no consigue
crear la ventana, retorna codigo 2 con `ERROR: raylib window was not created`.

### Modo headless

Carga la escena inicial, ejecuta fisica/colision/eventos durante N frames
y emite eventos semanticos. Funciona sin dependencias graficas.

```bash
# Smoke test: 60 frames, eventos capturados, exit code 0 si ok
MyGame.exe --smoke-test

# Headless con frames custom y print de runtime info
MyGame.exe --headless --frames 10 --print-runtime-info
```

`--print-runtime-info` emite por stdout: version del motor, entry scene,
assets cargados, frames ejecutados y eventos detectados.

## Runtime config

`runtime_config.json` generado por el pipeline:

```json
{
  "entry_scene": "levels/main_menu_scene.json",
  "window": {
    "width": 1280,
    "height": 720,
    "resizable": true,
    "fullscreen": false
  },
  "engine_version": "2026.03",
  "project_name": "My Game",
  "mode": "release",
  "headless_smoke_frames": 60
}
```

## Carga de contenido

El runtime detecta automaticamente:

1. Si existe `game.pak` → carga assets desde ZIP determinista.
2. Si existe `content/` → carga assets desde directorio (modo `directory`).
3. Si no hay ninguno → error `CONTENT_PACK_NOT_FOUND`.

El `ContentLoader` (`engine/runtime/content_loader.py`) lee el manifiesto,
verifica hashes SHA-256 y expone assets, escenas y scripts al runtime.

## Plataformas

### Windows

- PyInstaller genera `.exe` standalone.
- `console=False` en modo release normal (ventana sin consola).
- `console=True` en modo `debug`, con `include_debug_tools: true` o con
  `console: true` en el preset.
- Requiere `pyray`/`raylib` para modo windowed.

### Linux

- PyInstaller genera binario sin extension.
- Sin `console=True`.
- Requiere `pyray` para modo windowed.

### macOS

- Requiere macOS host.
- PyInstaller genera `.app` o binario con `--windowed`.
- Xcode opcional para notarizacion.
- Sin macOS: `TOOLCHAIN_UNAVAILABLE`.

### Android

- Template Gradle en `platforms/android/template/`.
- Content pack copiado a `app/src/main/assets/`.
- AndroidManifest.xml generado automaticamente.
- Debug: `assembleDebug` → APK.
- Release: `assembleRelease` → APK firmado, `bundleRelease` → AAB.
- Requiere `ANDROID_HOME`, JDK 11+ y Gradle.

### iOS

- Template estructural en `platforms/ios/template/`.
- Requiere macOS + Xcode + Apple Developer account.
- Sin macOS: `TOOLCHAIN_UNAVAILABLE` con instrucciones claras.
- No compila automaticamente (requiere cuenta de desarrollador Apple).

## Smoke test

El smoke test se ejecuta via `--smoke-test`:

1. Carga entry scene.
2. Ejecuta 60 frames de fisica/colision/input/scripts headless.
3. Verifica integridad del content pack (SHA-256).
4. Emite eventos semanticos (collisions, collectibles, hazards, goals).
5. Verifica que no haya errores de carga ni crashes.
6. Retorna exit code 0 si todo ok, 1 si errores, 3 si content pack corrupto.

Integrado en el pipeline de build: `WindowsExporter` ejecuta smoke test
automaticamente despues de generar el ejecutable.

> **⚠ Importante**: el smoke test verifica carga basica + N frames headless, pero
> **no valida la ventana real** ni equivale a jugabilidad completa. No valida:
> - Render de sprites/texturas reales (solo headless)
> - Input de teclado/mouse real (solo inyectado)
> - Interaccion UI (botones, cambio de escena por click)
> - ScriptBehaviour ejecutandose con eventos reales
>
> Para validacion de jugabilidad real, ver `test_export_runtime_playability.py`.

## Tests de jugabilidad

`tests/test_export_runtime_playability.py` contiene pruebas enfocadas que
verifican el runtime exportado sin requerir PyInstaller ni builds completos:

| Clase | Que verifica |
|---|---|
| `TestExportRuntimeSceneLoading` | Carga exitosa, escena faltante, emision de eventos, cambio de escena |
| `TestExportRuntimeFrame` | Incremento de frames, tolerancia a world=None, shutdown seguro |
| `TestExportRuntimeGameplay` | Input inyectado mueve Player (izquierda, derecha, salto), gravedad empuja hacia abajo |
| `TestExportRuntimeUI` | Click en UIButton tipo `load_scene` cambia escena, hover sin click no cambia escena |
| `TestExportRuntimeRealMenu` | Menu real `main_menu_scene.json` usa `load_scene_flow` hacia `platformer_test_scene.json` |
| `TestExportRuntimeSystemsIntegration` | Todas las propiedades accesibles, 30 frames sin crash con todos los sistemas |

Ejecucion:

```bash
py -m unittest tests.test_export_runtime_playability -v
```

## Separacion editor/runtime

| Componente | Editor | Runtime exportado |
|---|---|---|
| `engine.editor.*` | Cargado | No cargado |
| `engine.inspector.*` | Cargado | No cargado |
| `tools.*` | Cargado | No cargado |
| `docs/` | Cargado | Excluido |
| `tests/` | Cargado | Excluido |
| `main.py` | Usado | No usado |
| `engine/runtime/exported_game.py` | No usado | Entrypoint |
| Content pack | Opcional | Obligatorio |

El runtime exportado solo incluye sistemas necesarios para ejecutar el juego.
La clase `ExportRuntime` (`engine/runtime/export_runtime.py`) wirea estos
sistemas en orden:

| Sistema | Funcion |
|---|---|
| `InputSystem` | Captura input de teclado (real en windowed, inyectado en headless) |
| `CharacterControllerSystem` | Movimiento slide-based con backend fisico o fallback AABB |
| `PlayerControllerSystem` | Traduce InputMap + PlayerController2D a fuerzas |
| `PhysicsSystem` | Gravedad, fuerzas, impulsos, PGS solver |
| `CollisionSystem` | Deteccion AABB, eventos `collision_contact` |
| `AnimationSystem` | Animator state machine, spritesheet frames |
| `RenderSystem` | Render de sprites, tilemaps y formas; usa `RuntimeProjectService` para cargar texturas desde `content/` |
| `UISystem` | Procesa mouse real, resuelve interaccion con Canvas/UIButton/UIText |
| `UIRenderSystem` | Renderiza UI overlay encima del mundo |
| `ScriptBehaviourSystem` | Ejecuta `on_play`/`on_update`/`on_stop` via importlib (sin hot-reload) |

El `RenderSystem` en modo runtime usa `RuntimeProjectService` en lugar de
`AssetService`/`ProjectService` del editor. Las texturas se cargan desde
el directorio `content/` (directory mode) o desde `game.pak` (packed mode).

> **Nota**: El sistema de audio no esta implementado en `ExportRuntime`.
> La UI usa `UISystem` + `UIRenderSystem` reales (no "UI serializable" solo
> data). Los scripts ejecutan `ScriptBehaviourSystem` real con importlib
> fallback (sin hot-reload manager del editor).
