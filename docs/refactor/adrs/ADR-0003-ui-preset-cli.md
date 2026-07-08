# ADR-0003 - CLI y API publica para presets UI serializables

## Estado

Aceptado

## Contexto

OpenGame ya tenia primitives UI serializables (`Canvas`, `RectTransform`,
`UIText`, `UIButton`, `UIImage`) y comandos CLI atomicos para crearlas, pero no
tenia una ruta oficial para materializar interfaces genericas repetibles desde
`motor`.

El objetivo era exponer presets UI MVP por la CLI oficial y por `UIAPI` sin:

- escribir JSON de escena manualmente;
- tocar `World` o `Scene` directo;
- crear runtime paralelo;
- romper parser, registry o contratos publicos existentes.

## Decision

Se introducen dos superficies publicas nuevas en `UIAPI`:

- `list_ui_presets()`
- `create_ui_preset(preset_id, replace=False)`

Y dos comandos oficiales:

- `motor ui preset list`
- `motor ui preset add <preset_id>`

Los presets viven en `engine/ui/presets.py` como definiciones puras y
deterministas. `create_ui_preset()` materializa el arbol usando solo metodos
publicos (`create_canvas`, `create_ui_element`, `create_ui_text`,
`create_ui_button`, `set_entity_active`) dentro de una transaccion publica.

`--replace` regenera solo la raiz estable del preset y su arbol de descendientes.

## Consecuencias

- La CLI oficial puede crear UI reusable sin scripts auxiliares.
- Parser y capability registry siguen alineados con comandos implementados.
- Fallos a mitad de creacion revierten cambios via rollback transaccional.
- El contrato de deteccion/regeneracion depende de nombres raiz estables por preset.

## Alternativas consideradas

- Escribir escenas UI manualmente desde CLI: rechazada por romper fuente de
  verdad serializable del motor.
- Mutar `SceneManager` o `World` directo desde CLI: rechazada por saltarse la API publica.
- Reusar un canvas compartido para todos los presets: rechazada para MVP por
  aumentar colisiones y complejidad de reemplazo.
- Crear runtime/preset builder paralelo: rechazado por duplicar contrato oficial.
