# AGENTS.md

## 1. Propósito

Este archivo define las reglas generales para trabajar en OpenGame.

Las instrucciones específicas de una tarea, una skill o un plan activo pueden
ampliar estas reglas, pero no deben anular las normas de seguridad, alcance,
compatibilidad y validación del repositorio.

El modo predeterminado es el **flujo estándar**. Los flujos especializados, como
Reina, solo se usan cuando el usuario los activa explícitamente.

---

## 2. Estilo de trabajo

Usa la skill `caveman` cuando esté disponible.

Si no está disponible, aplica directamente estas reglas:

- Sé directo.
- No expliques paso a paso lo que haces salvo que se solicite.
- No des actualizaciones constantes durante la ejecución.
- No repitas contexto ya conocido.
- No desarrolles razonamientos largos que no aporten a la tarea.
- Prioriza ejecutar, validar y entregar el resultado.
- No ocultes errores, regresiones, incertidumbres ni comandos no ejecutados.

Al terminar, entrega un resumen breve y verificable con:

1. qué cambiaste;
2. qué archivos tocaste;
3. qué validaste;
4. riesgos o trabajo pendiente, si existen.

---

## 3. Flujo estándar

Es el modo predeterminado para correcciones, mantenimiento, documentación,
tests, features y refactors acotados.

```text
INSPECCIONAR
-> DEFINIR EL RESULTADO ESPERADO
-> PLAN BREVE SI HACE FALTA
-> IMPLEMENTAR EL CAMBIO MÍNIMO
-> EJECUTAR TESTS ENFOCADOS
-> REVISAR EL DIFF
-> DOCUMENTAR SI CAMBIA UN CONTRATO
-> REPORTAR
```

Reglas:

- Trabajar como un único agente por defecto.
- No lanzar subagentes salvo petición explícita del usuario o de una skill
  activada.
- No convertir una tarea localizada en una auditoría completa del repositorio.
- No crear planificación ceremonial para cambios simples.
- No ejecutar toda la suite si los tests enfocados son suficientes y el riesgo
  es bajo.
- No hacer commit ni push salvo solicitud explícita o flujo autorizado.

---

## 4. Estado real del repositorio

No asumir el estado actual del repositorio.

Antes de modificar archivos, inspeccionar como mínimo:

```bash
git status --short
git branch --show-current
git diff --stat
git diff --name-only
```

La fuente de verdad es, por este orden:

1. el estado real del working tree;
2. los tests y contratos existentes;
3. el código actual;
4. este `AGENTS.md` y la documentación canónica;
5. las instrucciones específicas de la tarea;
6. las suposiciones del agente.

El agente debe respetar los cambios locales existentes y no sobrescribir trabajo
ajeno.

---

## 5. Rama, remoto y cambios locales

Trabajar sobre la rama actual salvo que el usuario pida crear, cambiar o
actualizar una rama.

No se debe:

- cambiar de rama automáticamente;
- borrar cambios locales;
- restaurar archivos modificados por el usuario;
- asumir que la rama principal se llama `main`;
- ejecutar `reset`, `clean`, rebase o force-push sin autorización explícita.

Solo cuando la tarea requiera comparar con la rama principal, crear una rama
nueva o auditar divergencias, detectar la rama principal real del remoto.

Comandos orientativos:

```bash
git remote show origin
git fetch --all --prune
git branch -r --sort=-committerdate
```

No ejecutar `fetch` ni modificar referencias remotas si no aporta valor a la
tarea.

---

## 6. Tests como fuente de verdad

Los tests existentes son la autoridad inicial sobre el comportamiento
protegido.

Antes de tocar código funcional:

- localizar los tests relevantes;
- entender qué comportamiento protegen;
- ejecutar un baseline enfocado cuando sea viable;
- definir criterios de aceptación verificables;
- añadir o modificar tests si cambia comportamiento observable.

Después del cambio, ejecutar los tests enfocados aplicables.

Reglas:

- No relajar tests para conseguir verde.
- No borrar tests sin justificación explícita.
- No sustituir tests de comportamiento por tests internos más débiles.
- No declarar que un test pasó si no se ejecutó.
- Registrar los comandos reales y sus resultados.
- Si un comando documentado no existe, localizar el equivalente real.

Cuando el riesgo sea alto o el cambio afecte a varios subsistemas, ampliar la
validación según sea necesario. La suite general orientativa es:

```bash
py -m unittest discover -s tests
```

Si un test falla, clasificarlo cuando sea relevante como:

```text
- fallo funcional real;
- fallo de entorno;
- dependencia ausente;
- test obsoleto;
- test flaky;
- error de importación;
- error por plataforma.
```

---

## 7. Dependencias y entorno

El sistema de dependencias se detecta, no se inventa.

Revisar los mecanismos reales del repositorio, entre otros:

```text
pyproject.toml
requirements*.txt
setup.py
Pipfile
poetry.lock
uv.lock
environment.yml
Cargo.toml
package.json
```

Si existen varios sistemas, priorizar el utilizado por CI y por la
documentación vigente.

No instalar paquetes globales ni modificar el entorno del usuario de manera
irreversible sin necesidad y autorización.

---

## 8. Alcance y cambios mínimos

Implementar el cambio mínimo suficiente para cumplir la tarea.

No se debe:

- ampliar el alcance sin necesidad;
- mezclar una corrección con refactors no relacionados;
- aplicar cambios masivos de formato junto a cambios funcionales;
- introducir dependencias nuevas sin justificar su necesidad;
- reescribir componentes completos cuando una modificación localizada sea
  suficiente;
- ocultar deuda, regresiones o limitaciones detectadas.

Si aparece un problema fuera del alcance, documentarlo y continuar únicamente
si bloquea la tarea actual.

---

## 9. Contratos y módulos protegidos

Los siguientes módulos forman parte del contrato crítico del motor y requieren
especial cuidado:

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

También están protegidos:

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

Un cambio en estas zonas debe incluir, según aplique:

- justificación explícita;
- tests de contrato;
- compatibilidad hacia atrás;
- documentación canónica;
- estrategia de rollback;
- validación enfocada y de regresión.

No modificar un contrato público de forma accidental.

---

## 10. Documentación

No crear documentación ceremonial para cada tarea.

Actualizar la documentación cuando cambie alguno de estos elementos:

- API pública;
- CLI;
- serialización o schema;
- arquitectura;
- instalación o dependencias;
- comportamiento observable;
- compatibilidad o migraciones;
- flujos operativos utilizados por usuarios o agentes.

Los cambios internos localizados que no alteren contratos pueden indicar
explícitamente que no requieren documentación.

Las decisiones arquitectónicas relevantes deben documentarse en la ubicación
canónica existente del repositorio.

---

## 11. Validación antes de terminar

Antes de considerar terminada una tarea:

1. ejecutar los tests relevantes;
2. revisar el diff completo;
3. comprobar que no existen cambios fuera de alcance;
4. confirmar que la documentación necesaria está actualizada;
5. reportar pruebas no ejecutadas y riesgos restantes.

Comandos orientativos de revisión:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

No declarar la tarea completada si:

- faltan tests necesarios;
- existe una regresión nueva no aceptada;
- hay cambios fuera de alcance;
- faltan documentos contractuales necesarios;
- el resultado no cumple los criterios de aceptación.

---

## 12. Operaciones prohibidas

No ejecutar sin autorización explícita:

```text
- git reset --hard;
- git clean -fd;
- git checkout -- .;
- git restore .;
- rebase de ramas compartidas;
- force-push;
- borrados recursivos destructivos;
- instalación global de dependencias;
- cambios irreversibles en el entorno.
```

Además, no se debe:

- borrar o revertir cambios del usuario;
- ignorar tests fallando;
- ocultar regresiones;
- asumir nombres de ramas;
- hacer push sin solicitud explícita;
- lanzar subagentes en el flujo estándar por conveniencia.

---

## 13. Modo Reina

Reina es un flujo especializado para tareas largas, críticas o divididas en
varias fases.

No es el modo predeterminado y no debe activarse automáticamente por la
complejidad estimada de una tarea.

Solo se usa cuando el usuario:

- invoca explícitamente `$queen`;
- pide «modo Reina»;
- solicita ejecutar un plan con Reina.

La definición detallada de Reina debe vivir en su skill y en su documentación
canónica, no en este archivo.

Ruta prevista en Codex:

```text
.agents/skills/queen/SKILL.md
```

Este archivo solo establece que:

- el flujo estándar sigue siendo el predeterminado;
- la sesión raíz de Codex actúa como orquestador cuando Reina está activa;
- Reina puede usar subagentes especializados;
- su activación debe ser explícita;
- si la skill no existe o no puede cargarse, el agente debe indicarlo en lugar
  de improvisar una implementación equivalente.

La configuración de Reina para OpenCode permanece en sus archivos canónicos:

```text
.opencode/agents/
.opencode/commands/queen.md
opencode.json
```

### Contrato operativo

Flujo normal:

```text
RECON -> TEST CONTRACT -> PLAN -> CRITICA DEL PLAN -> IMPLEMENTAR -> DOCUMENTAR -> VALIDAR -> REVIEW -> AI AUDIT -> COMMIT -> REPORTE
```

Para Long Task Plan se carga el plan activo, se sincroniza antes de cada fase y
se mantiene la autoridad operativa en `docs/queen_engine_workflow.md`.

`phase_status` describe una fase; `task_status` describe la tarea completa.
`phase completed != task completed`: una fase completada no cierra el trabajo.
Definition of Done aplica solo al final de una tarea completa, no a una fase
individual. Estados finales permitidos: `completed`, `partial`, `blocked` y
`failed`. `max_cycles = 5` limita los ciclos de Reina.

---

## 14. Commit y push

Por defecto:

- no hacer commit salvo solicitud explícita o flujo autorizado;
- no hacer push salvo solicitud explícita;
- no considerar un commit como prueba suficiente de que la tarea está completa.

Antes de cualquier commit:

- revisar alcance;
- ejecutar las validaciones aplicables;
- revisar el diff;
- confirmar que no se incluyen archivos ajenos a la tarea.
