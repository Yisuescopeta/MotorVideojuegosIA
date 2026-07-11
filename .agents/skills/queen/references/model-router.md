# Model Router

Clasificar riesgo y seleccionar solo roles cuya disponibilidad se haya comprobado. Las rutas describen dependencias futuras, no agentes ya instalados. No cambiar modelos ni configuración en caliente. Los modelos reales se configurarán después en archivos de agentes.

## simple

Ruta: `test_strategist_fast` -> `planner_fast` -> `builder_fast` -> `code_reviewer_fast`.

Aplicar a documentación, fixtures, cambios mecánicos y tareas sin comportamiento observable.

## normal

Ruta: `test_strategist` -> `planner` -> `builder` -> `code_reviewer`.

Aplicar a bugfix localizado, feature pequeña o refactor de módulo no crítico.

## complex

Ruta: `test_strategist_deep` -> `planner_deep` -> `builder_deep` -> `code_reviewer_deep`.

Aplicar a cambios multiarchivo, sistemas compartidos, ECS, runtime/editor, export pipeline, component registry o física.

## critical

Ruta: `test_strategist_deep` -> `planner_deep` -> `builder_deep` -> `code_reviewer_deep`.

Aplicar a API pública, serialización, migraciones, Scene, World.clone, separación authoring/runtime, EngineAPI, SceneManager, legacy_aabb, riesgo de relajar tests o ciclos repetidos tras fallos importantes.

## Reglas

- Seleccionar roles existentes, no nombres de modelo.
- Comprobar disponibilidad antes de invocar cada rol.
- Bloquear con `missing_required_agent` cuando falte un rol imprescindible.
- Elevar a `critical` después de dos ciclos fallidos.

## Fallback de variantes

- Si falta una variante `fast`, usar la variante estándar o `deep`.
- Si falta una variante estándar, usar `deep`.
- Nunca sustituir una variante `deep` por `fast`.
- En tareas `complex`, una variante estándar solo puede sustituir temporalmente a `deep` si Reina reduce explícitamente el alcance de la fase, registra el riesgo y mantiene una review `deep`.
- En tareas `critical`, si falta cualquier rol `deep` imprescindible, bloquear con `missing_required_agent`.
- Nunca sustituir un agente read-only por un agente con permisos de escritura más amplios.
- Nunca sustituir un builder por la sesión raíz.
- Registrar cualquier sustitución en `model_route`.
