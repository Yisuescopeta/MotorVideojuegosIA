# Platformer demo package

Este paquete prepara un vertical slice 2D muy pequeño para `MotorVideojuegosIA` sin tocar todavía el motor ni implementar el juego final.

## Objetivo

Validar de forma realista estas áreas ya presentes en `main`:

- tilemap y authoring serializable
- animación runtime + authoring
- audio runtime
- física/gameplay 2D básica
- flujo de escena/entidades compatible con `Scene`, `SceneManager` y `EngineAPI`

## Contenido

- `asset_manifest.md`: inventario exacto de assets elegidos
- `attribution_and_licenses.md`: licencias y atribuciones
- `selection_notes.md`: criterios de selección y encaje con el motor
- `opencode_prompt.md`: prompt final para OpenCode
- `fetch_selected_assets.py`: script para descargar los assets visuales elegidos y generar los SFX placeholder del prototipo
- `assets/`: estructura destino del paquete

## Nota importante sobre assets

El conector GitHub disponible para esta tarea no me permite escribir blobs binarios grandes de forma fiable directamente dentro del repositorio. Para no dejarte un paquete incompleto, he dejado:

1. la documentación cerrada
2. la estructura final de carpetas
3. un script reproducible que descarga los assets visuales seleccionados desde las fuentes concretas elegidas
4. un generador local de SFX placeholder para salto, coleccionable, victoria y derrota

Con eso, el paquete queda listo para poblarse de forma determinista dentro de la propia rama antes de implementar el demo jugable.

## Ruta elegida

Se usa `demo/platformer_demo_package/` porque agrupa claramente assets, documentación y prompt de implementación bajo una única raíz fácil de localizar y separada del código del motor.
