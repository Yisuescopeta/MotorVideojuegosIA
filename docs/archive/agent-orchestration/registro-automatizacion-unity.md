# Registro de Automatizacion Unity

Este documento es la memoria operativa de la automatizacion horaria.

La sesion automatizada debe leer este archivo antes de proponer o implementar
cambios. El prompt base no debe decidir por contexto historico invisible; debe
seguir el estado de este registro.

## Objetivo

- Mantener un backlog corto y editable de funcionalidades de Unity a adaptar.
- Evitar repetir trabajo entre ejecuciones horarias.
- Separar tres estados: propuesto, implementado, verificado por humano.
- Permitir que el usuario corrija el rumbo editando solo este archivo.

## Reglas de uso para la IA

1. Leer primero este archivo y despues `docs/agent-orchestration/README.md`.
2. Usar la skill `unity-feature-adapter` cuando investigue o adapte una
   funcionalidad de Unity.
3. Si no hay tareas abiertas, investigar una funcionalidad concreta de Unity
   que encaje con el motor y anadirla como propuesta resumida.
4. Si hay una tarea marcada como propuesta pero no implementada, priorizar su
   implementacion antes de proponer otra nueva.
5. Al implementar una tarea:
   - marcarla como implementada
   - anotar archivos tocados
   - dejar pasos breves de verificacion manual
   - dejar riesgos o limites pendientes si existen
6. No marcar una tarea como verificada por humano.
7. Si el usuario escribe una incidencia, correccion o bloqueo en este archivo,
   tratarlo como instruccion prioritaria.
8. Mantener las descripciones resumidas y operativas. No convertir este archivo
   en un diario largo.

## Reglas de uso para el usuario

- Cambia prioridad, notas o bloqueos directamente aqui.
- Cuando pruebes una implementacion y funcione, marca la tarea como verificada.
- Si algo falla, anade una nota breve en `Incidencias del usuario` o en la
  propia tarea, sin tocar el prompt base.

## Leyenda de estado

- `[ ]` Propuesta pendiente de implementar
- `[~]` En progreso o parcialmente implementada
- `[x]` Implementada por la IA, pendiente de validar por humano
- `[v]` Verificada por humano
- `[!]` Bloqueada o requiere correccion prioritaria

## Cola activa

Usa una entrada por funcionalidad. Mantener orden de prioridad de arriba abajo.

### Plantilla de tarea

```md
### U-000 Nombre corto de la funcionalidad
Estado: [ ]
Origen Unity: nombre exacto de la feature, API o flujo en Unity
Objetivo: que caracteristica principal se quiere preservar en este motor
Resumen: 2-4 lineas con el comportamiento esperado y el valor para el motor
Dependencias: ninguna | U-00X | archivo o subsistema necesario
Archivos previstos: ruta1, ruta2
Archivos tocados: -
Verificacion manual:
- Paso 1
- Paso 2
Resultado esperado:
- Senal observable de que funciona
Notas IA:
- Huecos, riesgos o decisiones de adaptacion
Notas usuario:
- Observaciones, cambios de criterio o incidencias
```

## Tareas

### U-001 SpriteRenderer sorting layers y order in layer
Estado: [x]
Origen Unity: SpriteRenderer sorting layer + order in layer
Objetivo: preservar el control explicito del orden de render entre entidades 2D
Resumen: permitir definir una capa logica de dibujo y una prioridad numerica
para que escenas y prefabs controlen que sprites se ven delante o detras.
Dependencias: revisar primero el estado actual de `RenderOrder2D`
Archivos previstos: engine/components/renderorder2d.py, engine/systems/render_system.py, tests
Archivos tocados: engine/components/renderorder2d.py, engine/api/engine_api.py, tests/test_unity_runtime_base.py
Verificacion manual:
- Crear entidad `Back` y `Front` en la misma posicion con `Sprite`.
- Ejecutar `set_sorting_layers(["Background","Foreground"])`.
- Ejecutar `set_render_order("Back","Background",0)` y `set_render_order("Front","Foreground",-5)`.
- Guardar y recargar la escena; confirmar que `RenderOrder2D` y `feature_metadata.render_2d.sorting_layers` se conservan.
- Probar `set_render_order("Front","MissingLayer",0)` y confirmar fallo controlado.
Resultado esperado:
- El sprite con mayor prioridad en la misma capa se dibuja por delante.
- La configuracion queda serializada y se conserva al recargar.
Notas IA:
- Contrato adaptado a Unity: `Default` siempre presente en la lista de sorting layers y deduplicacion de capas vacias/duplicadas.
- `order_in_layer` ahora se limita al rango Unity (`-32768..32767`) al crear/serializar y desde API.
- `set_render_order` ahora valida que la capa exista en `feature_metadata.render_2d.sorting_layers` para evitar typos silenciosos.
- No se pudo ejecutar `pytest` en esta sesion porque el entorno no tiene `python`/`py`; validacion automatica pendiente de correr en entorno con Python.
Notas usuario:
- Para la proxima sesion, no me agas las instruciones de como hacer las prubas diciendome las funciones que tengo que probar sino que me digas los pasos que tengo que hacer en el inspector para verificar que la funcionalidad se ha implementado correctamente.

### U-002 Rigidbody2D constraints (Freeze Position X/Y)
Estado: [x]
Origen Unity: Rigidbody2D.constraints + RigidbodyConstraints2D (FreezePositionX, FreezePositionY, FreezePosition)
Objetivo: preservar el bloqueo explicito de movimiento por ejes sin estado oculto
Resumen: exponer un contrato de constraints serializable, alineado con Unity,
que traduzca a `freeze_x/freeze_y` para que fisica, guardado de escena e
inspector trabajen sobre la misma fuente de verdad.
Dependencias: `RigidBody` y API de authoring compartida
Archivos previstos: engine/components/rigidbody.py, engine/api/engine_api.py, tests/test_unity_runtime_base.py
Archivos tocados: engine/components/rigidbody.py, engine/api/engine_api.py, tests/test_unity_runtime_base.py
Verificacion manual:
- En el editor, selecciona una entidad con componente `RigidBody`.
- En el Inspector, ajusta constraints a `FreezePositionX` y deja la velocidad X no nula.
- Entra en `PLAY`: confirma que la entidad no se desplaza en X aunque mantenga movimiento en Y.
- Vuelve a `EDIT`, cambia a `FreezePosition` y guarda la escena.
- Recarga la escena y confirma en Inspector que constraints sigue mostrando ambos ejes bloqueados.
Resultado esperado:
- El motor conserva constraints en JSON y respeta el bloqueo por ejes en runtime.
- Valores de constraints no soportados fallan de forma controlada desde API.
Notas IA:
- Contrato investigado en docs oficiales de Unity: `RigidbodyConstraints2D` define `None`, `FreezePositionX`, `FreezePositionY`, `FreezePosition`, `FreezeRotation` y `FreezeAll`; esta iteracion adapta solo el subconjunto de posicion (X/Y) porque el motor actual no simula rotacion fisica.
- `RigidBody` ahora serializa `constraints` y lo normaliza en carga para mantener compatibilidad con escenas antiguas que solo tengan `freeze_x/freeze_y`.
- Para mantener coherencia con escenas legacy e inspector generico, `freeze_x/freeze_y` se mantienen como base de runtime y `constraints` se deriva al serializar.
- Se anadio `EngineAPI.set_rigidbody_constraints(...)` para authoring IA-first con validacion de valores soportados.
Notas usuario:
- Si quieres paridad total con Unity, siguiente paso natural: extender a `FreezeRotation` cuando exista simulacion angular en el runtime.

## Incidencias del usuario

- Ninguna por ahora.

## Historial breve

Mover aqui solo tareas cerradas o descartadas para mantener corta la cola
activa.

### Ejemplo de cierre

```md
### U-000 Ejemplo
Estado: [v]
Resumen cierre: implementado y validado manualmente.
```
