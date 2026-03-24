# Plan Extraido Para La Integracion De OpenCode

## Objetivo

Este documento condensa la informacion util del informe externo
`D:/putas/deep-research-report (2).md` para dejarla dentro del repositorio como
base de implementacion incremental.

La meta no es "meter un panel de OpenCode", sino integrar OpenCode como un
sistema reproducible, seguro y consciente del motor:

- servicio y API primero
- CLI y artifacts como superficie operativa real
- UI despues, como cliente del bridge
- skills compatibles con el estandar `SKILL.md`
- permisos y guardrails definidos desde el principio

## Principios De Integracion

- La integracion no debe depender de la UI.
- La UI no debe convertirse en fuente de verdad ni en orquestador implicito.
- OpenCode debe operar sobre contratos existentes del motor: CLI, artifacts,
  datos serializables y reglas de seguridad.
- El acceso a herramientas peligrosas debe ir por permisos granulares.
- Siempre que sea posible, conviene sustituir `bash` libre por tools tipadas y
  comandos repetibles.
- Las skills deben vivir en una fuente unica reutilizable por agentes
  compatibles, preferiblemente `.agents/skills/`.

## Alcance Funcional Minimo

### 1. OpenCode como servicio dentro del motor

- lanzar y gestionar `opencode serve`
- hacer health-check
- crear y listar sesiones
- enviar mensajes y recoger respuestas
- recuperar diffs
- atender aprobaciones y permisos
- exportar transcript, diff y logs a `artifacts/`

### 2. Seguridad y gobernanza

- politica `ask/allow/deny` por defecto
- permisos granulares para `bash`, `edit`, `read`, `skill`,
  `external_directory` y `doom_loop`
- bloqueo explicito de acciones peligrosas como `rm` o `git push`
- aislamiento del trabajo dentro del repo

### 3. Tooling engine-aware

- bridge Python para arrancar servidor, hablar con la API HTTP y exportar
  artefactos
- tools OpenCode en `.opencode/tools/` para envolver la CLI real del motor
- slash commands en `.opencode/commands/` para flujos repetibles

### 4. Skills preinstaladas

- `platformer-2d`
- `visual-novel-engine`
- `turn-based-combat-rpg`

Todas deben usar `SKILL.md`, ser concisas en instrucciones principales y mover
detalle extra a `references/` y `assets/`.

### 5. Integracion de editor

- panel opcional para sesiones, streaming, diff y aprobaciones
- sin logica privilegiada propia
- todo debe pasar por el bridge o por CLI

## Roadmap Por Fases

## Fase 1. Fundamentos De Integracion

### Objetivo

Definir el contrato de integracion, el modelo de permisos y la politica de
artefactos antes de tocar implementacion.

### Entregables

- `docs/opencode/architecture.md`
- `docs/opencode/security.md`
- checklist de acciones seguras y acciones de riesgo
- esquema de carpetas y artefactos propuesto

### Criterios de aceptacion

- queda claro que la integracion es servicio + API + CLI antes que UI
- queda definido donde se guardan transcript, diff, logs y approvals
- queda documentado como se bloquean acciones peligrosas

### Riesgos

- si esta fase se salta, la UI acaba absorbiendo responsabilidades de backend
- si no hay threat model, los permisos tienden a abrirse demasiado

## Fase 2. Configuracion Y Seguridad OpenCode

### Objetivo

Introducir la configuracion de OpenCode en el repo con reglas centrales y una
politica de permisos util pero segura.

### Entregables

- `opencode.jsonc`
- `AGENTS.md` si no existe
- `docs/opencode/setup.md`
- `docs/opencode/permissions.md`
- script o test sencillo que verifique que la configuracion minima existe

### Politica propuesta

- `*`: `ask` o `deny` con justificacion documentada
- `bash`: allow solo para prefijos seguros del motor y `git status`/`git diff`
- `edit`: deny por defecto; allow o ask segun carpetas
- `read`: mantener protegido `*.env`
- `external_directory`: `deny` o `ask`
- `doom_loop`: `ask` o `deny`
- `skill`: permitir internas, restringir externas

### Riesgos

- demasiada restriccion inutiliza el agente
- muy poca restriccion convierte la integracion en un vector de riesgo

## Fase 3. Herramientas Engine-Aware

### Objetivo

Reemplazar uso libre de shell por herramientas tipadas que invoquen la CLI real
del motor con argumentos validados.

### Entregables

- `.opencode/tools/engine-tools.ts`
- `.opencode/commands/*.md`
- `docs/opencode/tools.md`
- `docs/opencode/commands.md`

### Superficie minima recomendada

- `engine_unittest()`
- `engine_smoke(scene, frames, seed, out_dir)`
- `dataset_generate_scenarios(scene, count, seed, out_dir)`
- `dataset_run_episodes(scene, episodes, max_steps, seed, out, summary_out)`
- `dataset_replay_episode(episodes_jsonl, episode_id, out)`
- `runner_parallel_rollout(scene, workers, episodes, max_steps, seed, out_dir)`

### Restricciones

- no exponer `bash` raw dentro de los tools
- no escribir fuera de `artifacts/` o `.motor/` salvo configuracion explicita
- no duplicar logica ya implementada por la CLI del motor

## Fase 4. Bridge Python Dentro Del Motor

### Objetivo

Agregar un modulo Python que controle el ciclo de vida del servidor OpenCode y
su API HTTP para poder usar todo sin editor.

### Entregables

- modulo tipo `engine_integrations/opencode/`
- `OpenCodeServerProcess`
- `OpenCodeClient`
- subcomandos `opencode` en la CLI unificada
- exportacion de transcript, diff, logs y approvals a `artifacts/opencode/`

### Responsabilidades del bridge

- arrancar y parar `opencode serve`
- health-check
- crear sesiones
- enviar prompts
- leer mensajes
- recuperar diff
- contestar permisos
- exportar artefactos
- exponer status por CLI

### Requisitos de calidad

- no depender de UI
- fallar de forma accionable si OpenCode no esta instalado
- cubrir al menos lifecycle, requests HTTP y generacion de artefactos

## Fase 5. Skills Preinstaladas Por Genero

### Objetivo

Crear tres skills profesionales, compatibles con el estandar `SKILL.md` y con
progresive disclosure.

### Ubicacion recomendada

`.agents/skills/`

### Skills objetivo

#### `platformer-2d`

- vertical slice de plataformas
- movimiento, salto, colisiones, camara, checkpoints, muerte y respawn
- game feel: coyote time, jump buffering, variable jump, corner correction,
  momentum transfer
- integracion con escenas y tests/smokes reales del motor

#### `visual-novel-engine`

- runtime data-driven para dialogo y elecciones
- separacion clara entre datos, logica y UI
- flags, branching, save/load, replay, audio cues
- validacion offline del guion y tests de rutas criticas

#### `turn-based-combat-rpg`

- modelo data-driven de combate
- loop de turno como state machine
- orden por prioridad + velocidad con desempate determinista
- efectos, estados, logs de combate y replay por seed

### Entregables

- `.agents/skills/<skill>/SKILL.md`
- `.agents/skills/<skill>/references/...`
- `.agents/skills/<skill>/assets/...`
- validador interno de estructura y frontmatter

### Restricciones

- no duplicar las mismas skills en varias rutas salvo necesidad real
- no convertir la primera version en un paquete de scripts; primero
  instrucciones, referencias y plantillas
- no pedir features inexistentes como si ya estuvieran en el motor

## Fase 6. Integracion En Editor

### Objetivo

Construir un panel opcional que consuma el bridge ya existente.

### Entregables

- panel de sesiones
- streaming de mensajes
- visor de diff
- flujo de approvals

### Restricciones

- el panel no puede editar el repo por su cuenta
- toda accion debe tener equivalente por CLI o bridge
- no se permite esconder logica de negocio en la capa visual

## Orden Recomendado De Ejecucion

1. Documentar contrato y threat model.
2. Crear `opencode.jsonc`, `AGENTS.md` y docs de setup.
3. Definir permisos granulares.
4. Envolver la CLI del motor con custom tools.
5. Crear slash commands.
6. Implementar lifecycle del servidor OpenCode.
7. Implementar cliente HTTP para sesiones, mensajes, diff y permisos.
8. Integrarlo en la CLI del motor.
9. Crear infraestructura de skills y su validador.
10. Crear `platformer-2d`.
11. Crear `visual-novel-engine`.
12. Crear `turn-based-combat-rpg`.
13. Añadir panel de editor si sigue teniendo sentido.

## Artefactos Y Estructura Recomendada

### Documentacion

- `docs/opencode/architecture.md`
- `docs/opencode/security.md`
- `docs/opencode/setup.md`
- `docs/opencode/permissions.md`
- `docs/opencode/tools.md`
- `docs/opencode/commands.md`

### Configuracion OpenCode

- `opencode.jsonc`
- `.opencode/tools/`
- `.opencode/commands/`

### Integracion en motor

- `engine_integrations/opencode/` o equivalente segun layout real
- soporte CLI en `main.py` o en el parser unificado ya existente

### Skills

- `.agents/skills/platformer-2d/`
- `.agents/skills/visual-novel-engine/`
- `.agents/skills/turn-based-combat-rpg/`

### Artefactos

- `artifacts/opencode/<timestamp>_<session>/`

Contenido esperado:

- `transcript.json`
- `diff.patch` o equivalente
- `permissions.json`
- logs y reportes derivados

## Decisiones De Prioridad Extraidas Del Informe

- Seguridad antes que comodidad.
- Servicio y CLI antes que editor.
- Tools tipados antes que shell libre.
- Skills sobre una ruta unica compartida.
- Validacion y artefactos desde el principio para mantener trazabilidad.

## Lista De Trabajo Inmediata

La siguiente iteracion deberia empezar por estos pasos, en este orden:

1. Crear `docs/opencode/` con arquitectura, seguridad y setup.
2. Revisar la CLI real existente para mapear comandos seguros.
3. Diseñar `opencode.jsonc` con permisos por patron.
4. Confirmar la ruta exacta donde encajara el bridge Python.
5. Preparar el esqueleto de `.opencode/` y `.agents/skills/` sin implementar aun
   comportamiento profundo.

## Uso De Este Documento

Este archivo debe tratarse como resumen operativo del informe externo. Si en
iteraciones posteriores hace falta bajar a mas detalle, conviene crear los
documentos definitivos en `docs/opencode/` y dejar este roadmap como indice de
alto nivel.
