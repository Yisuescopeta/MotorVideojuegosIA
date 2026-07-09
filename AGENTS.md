# AGENTS.md

## Skill

Usa siempre la skill `caverman`.

## Regla para reducir consumo de tokens

* Sé directo.
* No expliques paso a paso lo que haces salvo que se te pida.
* No des actualizaciones constantes durante la ejecución.
* No repitas contexto ya conocido.
* No desarrolles razonamientos largos si no aportan a la tarea.
* Prioriza ejecutar y entregar resultado.
* Al final, entrega solo un resumen corto y útil con:

  1. qué cambiaste;
  2. qué archivos tocaste;
  3. qué validaste;
  4. riesgos restantes, si existen.

---

# 1. Principio rector

No asumir nada del estado actual del repositorio.

Antes de modificar código, el agente debe inspeccionar el estado real del proyecto, leer los archivos relevantes y entender el contrato existente.

El objetivo principal es que OpenGame evolucione de forma estable, verificable y mantenible. Cada cambio debe respetar el comportamiento existente salvo que la tarea pida explícitamente cambiarlo y exista un test o contrato que lo justifique.

El agente no debe programar “por intuición”. Debe trabajar con evidencia:

```text
código real -> tests existentes -> documentación canónica -> plan -> implementación -> validación -> revisión
```

---

# 2. Orden de autoridad

Cuando haya conflicto entre fuentes, se aplica este orden:

```text
1. Código actual y tests.
2. Contratos públicos del motor.
3. EngineAPI y CLI oficial.
4. Documentación canónica vigente.
5. Documentación operativa de agentes.
6. Documentación histórica o archive.
```

`docs/archive/` es solo contexto histórico. No debe usarse como fuente normativa si contradice código, tests o documentación canónica actual.

---

# 3. Reglas operativas obligatorias

## 3.1 Rama base

El agente debe detectar la rama principal real del remoto antes de iniciar tareas grandes o cambios estructurales.

No debe asumir que la rama se llama `main`.

Comandos orientativos:

```bash
git remote show origin
git fetch --all --prune
git branch -r --sort=-committerdate
```

Para tareas pequeñas dentro de una rama ya preparada, basta con registrar la rama actual y comprobar el estado del working tree:

```bash
git status --short --untracked-files=all
git branch --show-current
git log -1 --oneline
```

No se debe empezar una tarea con working tree sucio salvo que el usuario lo haya autorizado explícitamente o los cambios existentes formen parte de la propia tarea.

---

## 3.2 Tests como fuente de verdad

Los tests actuales del repositorio son la fuente de verdad inicial.

Antes de modificar comportamiento observable, el agente debe identificar los tests relevantes y, cuando sea viable, ejecutarlos antes o después del cambio.

Comando amplio orientativo:

```bash
py -m unittest discover -s tests
```

Para tareas acotadas, el agente debe preferir tests enfocados. Ejemplos:

```bash
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
py -m unittest tests.test_queen_agent_contract -v
```

Si un comando falla porque el entorno no está preparado, el agente debe documentar el fallo y distinguir entre:

```text
- fallo funcional real;
- fallo de entorno;
- dependencia ausente;
- test obsoleto;
- test flaky;
- error de importación;
- error por plataforma;
- comando inexistente;
- permiso bash denegado.
```

No se debe declarar éxito de un test que no se ha ejecutado.

---

## 3.3 Dependencias

El sistema de dependencias se detecta, no se inventa.

El agente debe buscar mecanismos reales del repositorio:

```bash
find . -maxdepth 3 -type f \( \
  -name "pyproject.toml" -o \
  -name "requirements*.txt" -o \
  -name "setup.py" -o \
  -name "Pipfile" -o \
  -name "poetry.lock" -o \
  -name "uv.lock" -o \
  -name "environment.yml" \
\)
```

Si existen varios sistemas, debe priorizar el más actual y documentado.

No se deben añadir dependencias nuevas salvo que:

```text
- sean necesarias;
- no exista alternativa razonable con dependencias actuales;
- se documenten en la tarea;
- se añadan tests;
- se explique el coste de mantenimiento.
```

Para dependencias que cambien arquitectura, runtime, build, exportación o distribución, debe crearse ADR.

---

# 4. Módulos protegidos

Los siguientes módulos forman parte del contrato crítico del motor y no deben modificarse salvo necesidad justificada, tests relevantes y plan de rollback:

```text
engine/api/engine_api.py
engine/api/_*_api.py
engine/scenes/scene.py
engine/scenes/scene_manager.py
engine/serialization/schema.py
engine/ecs/component.py
engine/ecs/world.py
engine/ecs/entity.py
engine/levels/component_registry.py
engine/physics/backend.py
engine/physics/legacy_backend.py
engine/core/game.py
engine/core/runtime_contracts.py
```

También quedan protegidos:

```text
- Scene v2;
- prefabs;
- EngineAPI pública;
- ciclo EDIT -> PLAY -> STOP;
- backend legacy_aabb;
- compatibilidad de escenas existentes;
- compatibilidad con agentes de IA;
- editor gráfico;
- serialización y migraciones existentes;
- CLI oficial;
- export pipeline;
- runtime/editor separation.
```

Cualquier cambio en estas zonas debe demostrar que no rompe comportamiento existente.

---

# 5. Superficies públicas y contratos que deben respetarse

El agente debe tratar como contratos estables:

```text
- EngineAPI;
- CLI `motor`;
- Scene y SceneManager;
- serialización de escenas/prefabs;
- component registry;
- runtime/editor lifecycle;
- EDIT -> PLAY -> STOP;
- tests de contrato oficiales;
- documentación canónica relacionada.
```

Si una tarea exige cambiar un contrato público, el agente debe:

```text
1. hacerlo explícito en el plan;
2. añadir o actualizar tests;
3. actualizar documentación canónica;
4. considerar migración si afecta datos persistentes;
5. crear ADR si la decisión cambia arquitectura o compatibilidad.
```

---

# 6. Política general de implementación

## 6.1 Cambios acotados

Cada tarea debe tener alcance claro.

El agente debe evitar mezclar:

```text
- feature nueva;
- refactor amplio;
- cambio de formato;
- limpieza de estilo;
- cambio de dependencias;
- cambio de arquitectura;
- optimización;
- documentación no relacionada.
```

Si durante la tarea aparecen mejoras no relacionadas, deben reportarse como recomendaciones, no implementarse sin autorización.

---

## 6.2 Primero comportamiento, después optimización

No optimizar sin necesidad demostrable.

Antes de optimizar una zona, el agente debe buscar o crear una medición mínima:

```text
- benchmark;
- perfil;
- test de rendimiento;
- caso reproducible;
- métrica antes/después.
```

Si no hay medición, el cambio debe tratarse como refactor funcional o deuda técnica, no como optimización demostrada.

---

## 6.3 Fallbacks y compatibilidad

Cuando se introduzca una ruta nueva de ejecución, debe mantenerse una ruta segura cuando aplique.

Ejemplos:

```text
- backend alternativo;
- feature flag;
- fallback Python;
- modo legacy;
- migración reversible;
- comportamiento anterior bajo configuración.
```

No eliminar fallback sin justificación, tests y ADR.

---

# 7. Política Python, nativo y tecnologías nuevas

Python sigue siendo el lenguaje principal del framework.

Deben quedarse en Python por defecto:

```text
- editor;
- EngineAPI;
- SceneManager;
- serialización;
- CLI;
- herramientas de IA;
- tests de integración;
- lógica no crítica;
- coordinación de runtime;
- validaciones de alto nivel.
```

Rust, PyO3, C/C++, dependencias nativas u otras tecnologías solo deben introducirse cuando exista una razón técnica clara.

Antes de introducir tecnología nueva:

```text
- justificar el problema;
- medir o demostrar necesidad;
- comprobar instalación limpia;
- mantener fallback cuando aplique;
- añadir tests;
- documentar riesgos;
- crear ADR si afecta arquitectura, build o distribución.
```

Ninguna tecnología nueva debe convertirse en requisito obligatorio si rompe la instalación básica del proyecto.

---

# 8. Benchmarks y rendimiento

El agente debe verificar si existen benchmarks antes de crear nuevos.

Comando orientativo:

```bash
find . -maxdepth 4 -iname "*benchmark*" -o -iname "*bench*"
```

Zonas donde los benchmarks son especialmente importantes:

```text
- query cache ECS;
- World.clone;
- SpatialHash2D;
- física con colliders;
- render prep;
- partículas;
- many entities;
- EDIT -> PLAY -> STOP;
- export pipeline;
- carga/guardado de escenas;
- runtime loop.
```

No se debe afirmar mejora de rendimiento sin datos antes/después.

---

# 9. Reglas específicas por subsistema

## 9.1 Scene, SceneManager y serialización

Antes de tocar escenas o serialización, comprobar:

```text
- compatibilidad con Scene v2;
- carga de escenas existentes;
- guardado sin cambios inesperados;
- migraciones;
- prefabs;
- roundtrip load/save/load;
- documentación en docs/schema_serialization.md si aplica.
```

Cambios de schema requieren tests y, si afectan contrato persistente, ADR.

---

## 9.2 EngineAPI

Cambios en EngineAPI deben preservar compatibilidad pública salvo que la tarea pida lo contrario.

Debe comprobarse:

```text
- tests de contrato público;
- documentación API;
- uso desde CLI/agentes;
- errores claros;
- estabilidad de nombres y payloads.
```

---

## 9.3 Runtime/editor

Cambios en runtime/editor deben respetar:

```text
- separación entre estado editable y runtime;
- EDIT -> PLAY -> STOP;
- runtime_world no contamina edit_world;
- cierre/limpieza de recursos;
- comportamiento headless cuando aplique.
```

---

## 9.4 ECS y componentes

Cambios en ECS deben comprobar:

```text
- creación/eliminación de entidades;
- add/remove component;
- componentes activos/inactivos;
- queries;
- serialización de componentes;
- registro en component_registry si es componente público.
```

---

## 9.5 Física y colisiones

No cambiar comportamiento físico sin tests específicos.

Antes de tocar física avanzada:

```text
- revisar PhysicsBackend;
- comprobar legacy_aabb;
- definir tolerancias numéricas si aplica;
- probar triggers/areas;
- probar raycasts;
- probar character/controller si aplica;
- comparar comportamiento antes/después.
```

`legacy_aabb` debe seguir existiendo como fallback salvo ADR explícito.

---

## 9.6 Render

No tocar API gráfica ni sustituir raylib/pyray sin una tarea específica.

Optimizaciones iniciales de render deben centrarse en:

```text
- sorting;
- culling;
- batching;
- draw command generation;
- rebuilds por frame;
- preparación de render.
```

Si cambia el orden visual, debe justificarse y probarse.

---

## 9.7 Tooling de agentes

Cambios en `.opencode/`, `opencode.json`, `AGENTS.md`, `docs/agents.md` o docs de Queen deben pasar tests de gobernanza/agentes.

Comandos recomendados:

```bash
py -m unittest tests.test_queen_agent_contract -v
py -m unittest tests.test_repository_governance tests.test_start_here_ai_coherence -v
```

Las salidas vacías o no parseables de subagentes son fallos reales del flujo.

---

# 10. Criterios de rollback obligatorios

Todo cambio relevante debe tener condición clara de rollback.

El agente debe revertir, bloquear o dejar desactivado el cambio si ocurre cualquiera de los siguientes casos:

```text
- falla un test crítico que antes pasaba;
- cambia serialización sin ADR o migración;
- cambia Scene v2 sin tests de compatibilidad;
- se rompe EngineAPI pública;
- se rompe CLI oficial;
- se rompe EDIT -> PLAY -> STOP;
- runtime_world contamina edit_world;
- el editor deja de abrir;
- una escena existente deja de cargar;
- una escena existente se guarda con cambios inesperados;
- física cambia comportamiento sin tolerancia documentada;
- render cambia orden visual sin justificación;
- fallback necesario deja de funcionar;
- instalación limpia se rompe;
- CI falla por el cambio;
- benchmark no demuestra valor suficiente;
- se modifican demasiados contratos públicos;
- el agente no puede explicar cómo revertirlo.
```

Si un cambio se revierte, el agente debe documentar:

```text
- qué se intentó;
- por qué se revirtió;
- qué tests o benchmarks fallaron;
- qué alternativa se recomienda;
- si conviene reintentarlo más adelante.
```

Rollback no se considera fracaso. Es una decisión correcta si evita romper el motor.

---

# 11. Documentación obligatoria

No todas las tareas requieren documentación nueva, pero toda tarea debe decidir explícitamente si la requiere.

## 11.1 Cuándo actualizar documentación

Actualizar documentación cuando cambie:

```text
- contrato público;
- EngineAPI;
- CLI;
- serialización;
- schema;
- arquitectura;
- flujo runtime/editor;
- comportamiento observable importante;
- tooling de agentes;
- dependencias;
- instrucciones de instalación;
- export pipeline.
```

No actualizar documentación canónica por cambios puramente internos que no alteran contrato ni uso externo, salvo que el cambio corrija documentación incorrecta.

---

## 11.2 ADRs

Crear ADR cuando se decida:

```text
- cambiar estrategia de serialización;
- introducir dependencia nueva relevante;
- cambiar EngineAPI pública;
- modificar Scene v2;
- cambiar PhysicsBackend;
- retirar fallback;
- cambiar arquitectura de runtime/editor;
- introducir tecnología nativa;
- cambiar flujo de agentes de forma estructural.
```

Ubicación recomendada:

```text
docs/adrs/
```

Si el repositorio usa otra ubicación real para ADRs, seguir la existente.

Formato recomendado:

```text
# ADR-XXXX — Título

## Estado
Propuesto | Aceptado | Rechazado | Revertido

## Contexto
Problema y restricciones.

## Decisión
Qué se decide.

## Consecuencias
Ventajas, costes y riesgos.

## Alternativas consideradas
Opciones descartadas y motivo.
```

---

# 12. Validación mínima antes de terminar una tarea

Antes de considerar terminada una tarea, el agente debe ejecutar los tests relevantes o documentar por qué no pudo hacerlo.

Comandos orientativos:

```bash
py -m unittest discover -s tests
py -m unittest tests.test_repository_governance tests.test_motor_cli_contract tests.test_start_here_ai_coherence -v
py -m unittest tests.test_official_contract_regression tests.test_parser_registry_alignment tests.test_motor_interface_coherence tests.test_motor_registry_consistency -v
py -m unittest tests.test_physics_backend tests.test_collision_system -v
py -m unittest tests.test_render_graph tests.test_render_safety -v
py -m motor doctor --project . --json
py -m ruff check engine cli tools main.py
py -m mypy engine cli tools main.py
```

No todos los comandos aplican a todas las tareas. El agente debe elegir los relevantes según subsistema y explicar brevemente la selección.

Si un comando no existe, el agente debe localizar el equivalente real y documentarlo.

---

# 13. Prohibiciones explícitas

El agente no debe:

```text
- reescribir el motor completo;
- mezclar una feature con refactors no relacionados;
- cambiar Scene v2 sin migración;
- romper EngineAPI pública;
- romper CLI oficial;
- eliminar legacy_aabb;
- hacer obligatoria una dependencia experimental;
- tocar física avanzada sin tests suficientes;
- tocar editor gráfico sin tarea específica;
- optimizar sin medición;
- inventar sistema de dependencias;
- asumir nombres de ramas;
- ignorar tests fallando;
- ocultar regresiones;
- introducir dependencias nuevas sin justificación;
- hacer cambios fuera de alcance;
- declarar éxito sin validación;
- usar docs/archive como autoridad normativa.
```

---

# 14. Criterios de finalización de una tarea

Una tarea se considera correctamente terminada solo si:

```text
- el alcance quedó claro;
- el estado inicial fue inspeccionado;
- los archivos relevantes fueron leídos;
- el TEST CONTRACT fue suficiente o no aplicable con razón;
- los cambios se limitaron al scope;
- se ejecutaron tests relevantes o se documentó por qué no;
- no se relajaron tests;
- no se tocaron módulos protegidos sin justificación;
- documentación fue actualizada o descartada con razón;
- rollback o riesgo residual quedó claro;
- working tree final fue reportado;
- estado final es completed, partial, blocked o failed.
```

---

# 15. Conducta esperada del agente

El agente debe trabajar de forma conservadora, verificable y transparente.

Debe preferir:

```text
- inspeccionar antes de cambiar;
- escribir tests antes o junto al cambio;
- mantener compatibilidad antes que rediseñar;
- cambios pequeños antes que reescrituras;
- fallback antes que dependencia obligatoria;
- datos antes que intuición;
- rollback antes que dejar una regresión;
- documentación útil antes que documentación extensa.
```

Si una solución simple en Python resuelve el problema con bajo riesgo, esa solución tiene prioridad sobre rediseños técnicos más ambiciosos.

---

# 16. Sistema Queen OpenCode

Queen es tooling multiagente experimental para programar, refactorizar, endurecer y mantener el motor OpenGame.

Queen no debe crear juegos como objetivo principal. Las escenas o juegos generados solo sirven como fixtures, demos mínimas, smoke tests o validación del motor.

## 16.1 Normal Task Mode

```text
RECON -> TEST CONTRACT -> PLAN -> CRITICA DEL PLAN -> IMPLEMENTAR -> DOCUMENTAR -> VALIDAR -> REVIEW -> AI AUDIT -> COMMIT -> REPORTE
```

## 16.2 Long Task Plan Mode

```text
LOAD PLAN -> PLAN SYNC -> TEST CONTRACT -> IMPLEMENTAR FASE -> DOCUMENTAR -> VALIDAR -> REVIEW -> AI AUDIT -> UPDATE PLAN -> NEXT PHASE | COMMIT | BLOCK
```

`max_cycles = 5`.

Queen no implementa directamente; delega en subagentes.

`context-recon` realiza RECON y debe devolver salida estructurada.

`test-strategist` define TEST CONTRACT antes de implementar.

`planner` crea el plan ejecutable.

`builder` implementa solo lo autorizado.

`documenter` decide y ejecuta documentación cuando aplica.

`validator` ejecuta validación final después de DOCUMENTAR.

`code-reviewer` revisa evidencia y bloquea con `must_fix` cuando falta verdad técnica.

`ai-friendliness` audita compatibilidad con flujos de IA cuando aplica.

`committer` solo actúa si validator, review y audit no bloquean.

En tareas largas, `UPDATE PLAN` registra el resultado de AI AUDIT antes de avanzar, bloquear o cerrar.

---

## 16.3 Structured Subagent Result Gate

Queen debe exigir salida estructurada parseable de cada subagente obligatorio antes de avanzar de fase.

Si un subagente esperado devuelve:

```text
- salida vacía;
- salida no parseable;
- salida sin contrato verificable;
- <task_result></task_result>;
- error de proveedor/modelo sin resultado usable;
```

Queen debe marcar la fase como:

```text
blocked: missing_subagent_result
```

Queen no puede inferir éxito por ausencia de cambios.

---

## 16.4 Model Router

Queen usa Model Router.

Después de RECON y antes de TEST CONTRACT, Queen clasifica la tarea:

```text
simple | normal | complex | critical
```

También estima:

```text
risk_level: low | medium | high | critical
reasoning_required: low | medium | high | xhigh
```

Queen selecciona variantes de subagente:

```text
fast | standard | deep
```

Queen selecciona variantes, no edita modelos en caliente.

Cada variante tiene modelo fijo en frontmatter y `opencode.json`.

Queen debe incluir `model_route` en el reporte final.

Formato esperado:

```json
{
  "model_route": {
    "task_complexity": "simple|normal|complex|critical",
    "risk_level": "low|medium|high|critical",
    "reasoning_required": "low|medium|high|xhigh",
    "selected_agents": {
      "test_strategist": "test-strategist|test-strategist-fast|test-strategist-deep",
      "planner": "planner|planner-fast|planner-deep",
      "builder": "builder|builder-fast|builder-deep",
      "code_reviewer": "code-reviewer|code-reviewer-fast|code-reviewer-deep"
    },
    "reason": "why this route was selected"
  }
}
```

Routing esperado:

```text
simple:
  test-strategist-fast
  planner-fast
  builder-fast
  code-reviewer-fast

normal:
  test-strategist
  planner
  builder
  code-reviewer

complex:
  test-strategist-deep
  planner-deep
  builder-deep
  code-reviewer-deep

critical:
  test-strategist-deep
  planner-deep
  builder-deep
  code-reviewer-deep
```

Deep es obligatorio si la tarea toca:

```text
- serialización;
- SceneManager;
- EngineAPI;
- contrato público;
- migraciones;
- runtime/editor;
- PhysicsBackend;
- fallback legacy;
- component registry;
- export pipeline;
- arquitectura ECS;
- tests de contrato;
- fallo previo de validator/review;
- riesgo de relajar tests.
```

En Long Task Plan Mode, Queen recalcula `model_route` al inicio de cada fase.

---

## 16.5 Definition of Done de Queen

Queen solo puede terminar como `completed` si cumple todo lo aplicable:

```text
- RECON tiene salida estructurada;
- TEST CONTRACT suficiente o no aplicable con razón explícita;
- PLAN aprobado;
- builder actuó solo dentro del scope;
- documenter actualizó docs o declaró not_applicable con razón;
- validator ejecutó comandos mínimos aplicables;
- code-reviewer devuelve approved y cero must_fix;
- ai-friendliness devuelve score válido o not_applicable justificado;
- no se relajaron tests;
- no hay cambios fuera de alcance;
- no hay salida vacía de subagentes obligatorios;
- working tree final está explicado.
```

Matriz operativa de validación por subsistema:

```text
docs/queen_engine_workflow.md
```

Comando base de suite amplia:

```bash
py -m unittest discover -s tests
```

---

# 17. Resumen final obligatorio

Al terminar, el agente debe reportar de forma breve:

```text
## Estado
completed | partial | blocked | failed

## Cambios
Resumen corto.

## Archivos tocados
Lista.

## Validación
Comandos ejecutados y resultado.

## Riesgos
Solo si existen.

## Siguiente paso
Una recomendación concreta si aplica.
```
