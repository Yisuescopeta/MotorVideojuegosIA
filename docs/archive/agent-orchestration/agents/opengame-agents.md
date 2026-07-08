# AGENTS.md — Reglas de trabajo para agentes de código en OpenGame

Este documento define las reglas obligatorias que debe seguir cualquier agente de código, incluyendo Codex, al trabajar en el repositorio OpenGame.

El objetivo es permitir una refactorización incremental, segura, medible y reversible del motor sin romper el editor, la API pública, las escenas existentes, el runtime ni la compatibilidad con agentes de IA.

---

## 1. Principio rector

No asumir nada del estado actual del repositorio.

Antes de modificar código, el agente debe inspeccionar, medir y documentar. La única fuente de verdad es el estado real de la rama principal remota en el momento de empezar.

El objetivo no es “meter Rust”, reescribir el motor ni hacer una migración tecnológica. El objetivo es que OpenGame sea más estable, medible, mantenible y rápido donde los datos demuestren que merece la pena.

---

## 2. Reglas operativas obligatorias

### 2.1 Rama base

El agente debe detectar la rama principal real del remoto antes de trabajar.

No debe asumir que la rama se llama `main`.

Debe inspeccionar:

```bash
git remote show origin
git fetch --all --prune
git branch -r --sort=-committerdate
```

La rama de trabajo debe partir de la rama principal remota detectada.

---

### 2.2 Tests como fuente de verdad

Los tests actuales del repositorio son la fuente de verdad inicial.

Antes de tocar código funcional, el agente debe ejecutar la suite disponible y guardar el resultado como baseline.

Comando orientativo:

```bash
python -m pytest
```

Si el comando falla porque el entorno no está preparado, el agente debe documentar el fallo y localizar el sistema de dependencias real antes de continuar.

Los fallos deben clasificarse como:

```text
- fallo funcional real;
- fallo de entorno;
- dependencia ausente;
- test obsoleto;
- test flaky;
- error de importación;
- error por plataforma.
```

No se debe iniciar una refactorización profunda si la línea base de tests es ambigua.

---

### 2.3 Dependencias

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

Si existen varios sistemas, debe priorizar el más actual y documentado en el repositorio.

Si no existe un sistema claro, debe documentarlo como deuda de entorno antes de proponer cambios.

---

### 2.4 Benchmarks

No se debe optimizar sin benchmark antes/después.

El agente debe verificar si existen benchmarks reales antes de crear otros nuevos.

Debe buscar:

```bash
find . -maxdepth 4 -iname "*benchmark*" -o -iname "*bench*"
```

Benchmarks o escenarios que deben verificarse o crearse si faltan:

```text
- query cache ECS;
- World.clone;
- SpatialHash2D;
- física con colliders;
- render prep;
- partículas;
- many entities;
- EDIT -> PLAY -> STOP.
```

Si un benchmark mencionado en un plan no existe, el agente debe crear un benchmark mínimo y reproducible antes de optimizar esa zona.

---

## 3. Módulos protegidos

Los siguientes módulos forman parte del contrato crítico del motor y no deben modificarse salvo necesidad justificada, tests de contrato y plan de rollback:

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
- serialización y migraciones existentes.
```

Cualquier cambio en estas zonas debe demostrar que no rompe comportamiento existente.

---

## 4. Política Python/Rust

Python sigue siendo el lenguaje principal del framework.

Deben quedarse en Python:

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

Rust/PyO3 solo puede usarse para hotspots numéricos o algorítmicos medidos.

Candidatos posibles para Rust, siempre después de benchmarks:

```text
- SpatialHash2D;
- queries físicas;
- colisiones AABB;
- partículas CPU;
- render prep;
- culling;
- batching;
- pathfinding;
- bucles calientes claramente identificados.
```

Rust/PyO3 debe ser opcional hasta demostrar instalación estable.

El motor debe funcionar sin toolchain Rust instalado.

Todo módulo Rust debe tener fallback Python.

---

## 5. Criterios para activar Rust por defecto

Rust no debe activarse por defecto al introducir un módulo nativo.

Debe empezar desactivado o en modo experimental.

Solo puede activarse por defecto si cumple todos estos criterios:

```text
- benchmark antes/después disponible;
- mejora >= 2x frente a Python optimizado;
- tests de equivalencia Python/Rust;
- fallback Python probado;
- instalación sin Rust sigue funcionando;
- CI no se rompe;
- no cambia el comportamiento funcional;
- no rompe API pública;
- no rompe serialización;
- no rompe EDIT -> PLAY -> STOP;
- el overhead Python/Rust no consume la mejora.
```

Si cualquiera de esos puntos falla, Rust queda desactivado o se elimina la integración experimental.

---

## 6. Reglas específicas para hotspots

### 6.1 Query cache ECS

La invalidación global del cache de queries debe tratarse primero como problema algorítmico en Python.

Antes de cambiarla:

```text
- añadir tests de comportamiento actual;
- añadir métricas hit/miss;
- crear o verificar benchmark de query cache;
- comprobar add/remove component;
- comprobar componentes deshabilitados;
- comprobar entidades activas/inactivas.
```

No migrar esta zona a Rust antes de intentar una optimización Python segura.

---

### 6.2 World.clone

`World.clone()` solo puede optimizarse si se demuestra aislamiento mutable entre `edit_world` y `runtime_world`.

Tests obligatorios:

```text
- EDIT -> PLAY -> STOP conserva estado editable;
- runtime_world no modifica edit_world;
- listas mutables no se comparten;
- diccionarios mutables no se comparten;
- componentes con datos mutables no se comparten;
- jerarquías padre/hijo se conservan;
- prefabs se conservan;
- feature_metadata se conserva;
- roundtrip de serialización no cambia.
```

Si hay duda sobre mutabilidad, se conserva el clone actual.

La corrección tiene prioridad sobre el rendimiento.

---

### 6.3 SpatialHash2D

`SpatialHash2D` es candidato preferente para Rust, pero no debe ser la primera tarea técnica.

Solo se puede migrar después de tener:

```text
- tests de equivalencia;
- benchmark de spatial queries;
- benchmark de física que use el spatial hash;
- fallback Python;
- feature flag;
- medición frente a Python optimizado;
- instalación nativa probada.
```

Debe compararse el resultado como conjunto de IDs cuando el orden no sea parte del contrato.

Los raycasts o candidatos por rayo deben tener tests específicos, incluyendo rayos diagonales.

---

### 6.4 Física avanzada

No introducir Rapier2D, Box2D nuevo, migración del solver PGS o migración de `IslandBuilder` sin datos suficientes.

Antes de tocar física avanzada:

```text
- tests sólidos de física;
- benchmarks de física legacy;
- contrato PhysicsBackend revisado;
- tolerancias numéricas documentadas;
- pruebas de character controller;
- pruebas de triggers/areas;
- pruebas de raycasts;
- comparación de comportamiento antes/después.
```

`legacy_aabb` debe seguir existiendo como fallback.

---

### 6.5 Render prep

No tocar la API gráfica ni sustituir raylib/pyray al inicio.

Las optimizaciones iniciales deben centrarse en preparación de render:

```text
- sorting;
- culling;
- batching;
- draw command generation;
- rebuilds por frame;
- spatial index de render.
```

Todo cambio debe tener prueba visual o funcional mínima, además de benchmark.

---

## 7. Criterios de rollback obligatorios

Todo cambio relevante debe tener una condición clara de rollback.

El agente debe revertir o dejar desactivado el cambio si ocurre cualquiera de los siguientes casos:

```text
- falla un test crítico que antes pasaba;
- cambia la salida de serialización sin ADR explícito;
- cambia Scene v2 sin migración y tests de compatibilidad;
- se rompe EngineAPI pública;
- se rompe EDIT -> PLAY -> STOP;
- runtime_world contamina edit_world;
- el editor deja de abrir;
- una escena existente deja de cargar;
- una escena existente se guarda con cambios inesperados;
- física cambia comportamiento sin tolerancia documentada;
- el render cambia el orden visual sin justificación;
- Python fallback no funciona;
- el proyecto deja de instalarse sin Rust;
- PyO3/maturin rompe instalación limpia;
- CI falla por la integración nueva;
- benchmark Python mejora menos de lo esperado y aumenta complejidad;
- módulo Rust mejora <2x frente a Python optimizado;
- overhead FFI elimina la mejora nativa;
- el cambio requiere modificar demasiados contratos públicos;
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

El rollback no se considera fracaso. Se considera una decisión correcta si evita romper el motor.

---

## 8. Documentación obligatoria por fase

Cada fase debe terminar con documentación mínima en `docs/refactor/`.

El agente no debe cerrar una fase sin dejar un informe escrito.

### 8.1 Documentos iniciales obligatorios

Durante la fase de baseline deben generarse o actualizarse:

```text
docs/refactor/baseline_environment.md
docs/refactor/baseline_tests.md
docs/refactor/baseline_benchmarks.md
docs/refactor/branch_audit.md
docs/refactor/protected_modules.md
```

### 8.2 Informe obligatorio por fase

Cada fase posterior debe generar un documento con este formato:

```text
docs/refactor/phase_<numero>_<nombre>_result.md
```

Ejemplos:

```text
docs/refactor/phase_1_query_cache_result.md
docs/refactor/phase_2_world_clone_result.md
docs/refactor/phase_3_frame_allocations_result.md
docs/refactor/phase_4_pyo3_minimal_result.md
docs/refactor/phase_5_spatial_hash_result.md
```

### 8.3 Estructura mínima del informe de fase

Cada informe debe incluir:

```text
# Resultado de fase

## Objetivo
Qué se pretendía conseguir.

## Estado inicial
Commit base, rama, tests relevantes y benchmarks antes del cambio.

## Archivos inspeccionados
Lista de archivos revisados.

## Cambios realizados
Descripción concreta de lo modificado.

## Cambios descartados
Qué se decidió no hacer y por qué.

## Tests ejecutados
Comandos ejecutados y resultado.

## Benchmarks ejecutados
Comandos ejecutados, datos antes/después y conclusión.

## Riesgos detectados
Riesgos nuevos o riesgos que siguen abiertos.

## Rollback
Cómo revertir el cambio si aparece una regresión.

## Decisión
Continuar, mantener desactivado, revertir o replanificar.

## Siguiente recomendación
Qué debería hacer el siguiente agente.
```

### 8.4 ADRs

Las decisiones importantes deben documentarse como ADRs en:

```text
docs/refactor/adrs/
```

Crear un ADR cuando se decida:

```text
- cambiar comportamiento interno de ECS;
- cambiar estrategia de serialización;
- introducir Rust/PyO3;
- activar un módulo Rust por defecto;
- cambiar PhysicsBackend;
- cambiar comportamiento físico;
- modificar Scene v2;
- modificar EngineAPI pública;
- retirar un fallback;
- introducir una dependencia nueva.
```

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

## 9. Validación mínima antes de terminar cualquier tarea

Antes de considerar terminada una tarea, el agente debe ejecutar los tests relevantes.

Comandos orientativos:

```bash
python -m pytest
python -m pytest tests -k "ecs or world or component"
python -m pytest tests -k "scene or serialization or prefab"
python -m pytest tests -k "play or stop or runtime"
python -m pytest tests -k "physics or collision"
python -m pytest tests -k "render or particles"
```

No todos los comandos aplican a todas las tareas. El agente debe elegir los relevantes y documentar por qué.

Para Rust/PyO3:

```bash
cargo test
python -m maturin develop
python -c "import engine.native"
python -m pytest tests -k "native or spatial_hash"
```

Si un comando no existe, el agente debe localizar el equivalente real y documentarlo.

---

## 10. Prohibiciones explícitas

El agente no debe:

```text
- reescribir el motor completo;
- migrar globalmente a Rust;
- crear un lenguaje propio;
- cambiar Scene v2 sin migración;
- romper EngineAPI pública;
- eliminar legacy_aabb;
- hacer Rust obligatorio;
- activar Rust por defecto sin benchmark >=2x;
- tocar física avanzada sin tests suficientes;
- tocar editor gráfico en fases iniciales;
- optimizar sin benchmark;
- mezclar refactor funcional con cambios de formato;
- inventar sistema de dependencias;
- asumir nombres de ramas;
- ignorar tests fallando;
- ignorar fallback Python;
- introducir dependencias nuevas sin ADR;
- ocultar regresiones.
```

---

## 11. Criterios de finalización del plan

El plan se considera correctamente ejecutado solo si:

```text
- se partió de la rama principal remota real;
- el commit base quedó registrado;
- el entorno se detectó desde archivos reales del repo;
- los tests actuales se ejecutaron y documentaron;
- los benchmarks se verificaron o crearon;
- las ramas relevantes se auditaron antes de tocar módulos críticos;
- las primeras optimizaciones fueron Python salvo justificación medida;
- SpatialHash2D no se migró a Rust sin tests y benchmarks;
- World.clone no se optimizó sin pruebas de aislamiento mutable;
- PyO3 siguió siendo opcional hasta demostrar instalación estable;
- el siguiente hotspot se eligió con datos;
- Rust no se activó por defecto sin >=2x y fallback probado;
- EngineAPI, Scene v2, SceneManager, prefabs y backend legacy siguen intactos salvo justificación explícita;
- todo cambio importante tiene documentación, benchmark y rollback.
```

---

## 12. Conducta esperada del agente

El agente debe trabajar de forma conservadora, verificable y transparente.

Debe preferir:

```text
- inspeccionar antes de cambiar;
- medir antes de optimizar;
- documentar antes de continuar;
- mantener compatibilidad antes de mejorar rendimiento;
- revertir antes que dejar una regresión;
- Python seguro antes que Rust innecesario;
- fallback antes que dependencia obligatoria;
- datos antes que intuición.
```

Si una optimización no demuestra valor real, se descarta o se deja desactivada.

Si Python resuelve el cuello de botella con menor riesgo, Python gana.
