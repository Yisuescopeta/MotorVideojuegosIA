# Matriz Unity 2D Core

Esta matriz sirve como base de trabajo del `Feature Scout`.

| Capacidad | Estado | Notas |
|-----------|--------|-------|
| ECS base | ya existe | Entidades, componentes y sistemas ya operativos |
| Escenas edit/play | ya existe | SceneManager y restauracion basica |
| API headless | parcial | Faltaba CRUD completo de authoring |
| Activacion de entidades | ya existe | Runtime, API y tooling serializable respetan `active` |
| Habilitacion de componentes | ya existe | `enabled` ya se serializa y los sistemas core lo respetan |
| Tags y layers | ya existe | Expuestos por API, escena y tooling con filtros simples |
| Camera 2D | ya existe | `Camera2D` primaria serializable con follow, framing `platformer` y clamp |
| Input Actions | ya existe | `InputMap` declarativo con API, scripting y estado consultable |
| Audio basico | ya existe | `AudioSource` serializable con API, scripting y estado no visual |
| Script behaviour adjunto | ya existe | `ScriptBehaviour` serializable con hot-reload y `public_data` accesible por API |
| Persistencia de seleccion | ya existe | La entidad seleccionada se conserva entre `EDIT`, `PLAY` y `STOP` |
| UI como traductor | parcial | Quedan rutas visuales por consolidar fuera del flujo core ya compartido |
| Prefabs | ya existe | Base disponible |
| Reglas y eventos | ya existe | Base declarativa disponible |

## Regla Global

Ningun agente puede introducir funcionalidades cuya fuente de verdad viva solo
en la interfaz o en estado no serializable; todo comportamiento editable por el
usuario debe representarse como codigo o datos accesibles por IA mediante API.
