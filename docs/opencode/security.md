# Seguridad De OpenCode En El Motor

## Objetivo

Este documento fija un threat model practico para integrar OpenCode sin abrir
una via de ejecucion peligrosa dentro del repo.

La prioridad es simple:

- seguridad antes que comodidad
- herramientas tipadas antes que shell libre
- repo y proyecto actual como limite operativo por defecto

## Supuestos De Seguridad

### Activos a proteger

- contenido fuente del proyecto: `levels/`, `prefabs/`, `scripts/`, `assets/`
- metadatos locales del proyecto en `.motor/`
- historial git del repositorio
- sistema de archivos fuera del repo
- credenciales o secretos locales

### Restriccion base

OpenCode solo debe operar con:

- rutas del proyecto actual
- CLI del motor
- tools tipadas que envuelvan comandos ya existentes
- formatos JSON compatibles con el repo

OpenCode no debe recibir acceso general a shell como camino principal.

## Amenazas Practicas Y Bloqueos

### 1. Borrado destructivo

Ejemplos:

- `rm -rf`
- borrado recursivo de carpetas del repo
- limpieza de `artifacts/` o `.motor/` sin autorizacion

Bloqueo:

- denegar comandos destructivos por politica
- exponer solo operaciones tipadas, no shell libre
- si una limpieza legitima es necesaria, debe pasar por aprobacion explicita y
  alcance acotado

### 2. Push o mutacion remota de git

Ejemplos:

- `git push`
- `git push --force`
- `git remote add`

Bloqueo:

- denegar operaciones remotas de git por defecto
- permitir como maximo lectura local: `git status`, `git diff`, `git rev-parse`
- cualquier futura excepcion debe requerir aprobacion humana explicita

### 3. Escritura fuera del repo

Ejemplos:

- editar archivos en directorios padres
- escribir en carpetas arbitrarias del usuario
- leer o editar proyectos ajenos al activo

Bloqueo:

- resolver todas las rutas contra `ProjectService`
- denegar `external_directory` por defecto
- aceptar solo rutas dentro de `project_root`, `artifacts/` y `.motor/`

### 4. Escalada por shell generalista

Ejemplos:

- shell con comandos arbitrarios
- pipelines opacos no auditables
- scripts temporales fuera del contrato del motor

Bloqueo:

- prioridad a tools tipadas
- allowlist de comandos del motor ya existentes
- validacion de argumentos antes de invocar subprocess
- registrar en artifacts cada invocacion operativa relevante

### 5. Edicion de archivos sensibles

Ejemplos:

- `*.env`
- configuracion de usuario fuera del repo
- ficheros de sistema

Bloqueo:

- deny por patron para secretos y rutas externas
- solo lectura sobre archivos de configuracion sensibles si es imprescindible
- nunca exportar secretos a `artifacts/`

### 6. Doom loop operativo

Ejemplos:

- repetir comandos fallidos de forma indefinida
- regenerar datasets enormes sin limite
- llenar `artifacts/` por reintentos sin control

Bloqueo:

- limites de reintento
- limites de workers, episodes, frames y tiempo
- aprobacion previa para workloads costosos o destructivos
- corte automatico al detectar fallos repetidos

## Politica Operativa Recomendada

### Acciones permitidas por defecto

- leer documentacion y codigo dentro del repo
- ejecutar CLI del motor con argumentos validados
- generar outputs en `artifacts/`
- actualizar metadata local en `.motor/meta/opencode/`
- usar skills desde `.agents/skills/`

### Acciones que requieren aprobacion

- editar codigo fuente del proyecto
- editar scripts
- borrar archivos existentes
- ejecutar operaciones largas o con coste alto
- modificar configuraciones de permisos

### Acciones denegadas por defecto

- `rm`, `rmdir`, borrados recursivos y equivalentes
- `git push`, `git push --force`, cambios de remoto
- escritura fuera del repo
- acceso a secretos o archivos no relacionados
- shell libre para tareas que ya tienen tool o CLI del motor

## Modelo De Aprobaciones

El repo ya maneja conceptos de sesion y aprobacion en
`.motor/meta/ai_sessions/*.json`, donde existe el campo `approval`.

Para OpenCode, la decision debe quedar reflejada en JSON exportable:

- `approvals.json` en `artifacts/opencode/<run_id>/`
- cada entrada incluye accion, alcance, decision, actor y timestamp

Regla:

- sin aprobacion resuelta, la accion peligrosa no se ejecuta
- la ausencia de aprobacion equivale a denegacion efectiva

## Modelo De Logs Y Trazabilidad

Cada sesion OpenCode debe dejar evidencia suficiente para auditoria minima:

- que pidio el usuario
- que tools o comandos se intentaron usar
- que archivos se pretendia tocar
- que aprobaciones se pidieron
- que artefactos se exportaron

Archivos propuestos:

- `transcript.json`
- `diffs.json`
- `logs.jsonl`
- `approvals.json`
- `manifest.json`

Todos bajo `artifacts/opencode/<run_id>/`.

## Fronteras De Mutacion

OpenCode solo puede mutar por rutas compatibles con la arquitectura del motor:

- contenido serializable del proyecto
- scripts del proyecto cuando la politica lo permita
- metadata local de sesion en `.motor/meta/opencode/`

OpenCode no puede:

- convertir la UI en orquestador
- introducir una base de datos paralela de cambios
- guardar estado funcional canonico en `artifacts/`

## Integracion Segura Con La CLI Real

La integracion debe envolver comandos ya existentes, por ejemplo:

- `tools/engine_cli.py smoke`
- `tools/scenario_dataset_cli.py generate-scenarios`
- `tools/scenario_dataset_cli.py run-episodes`
- `tools/scenario_dataset_cli.py replay-episode`
- `tools/parallel_rollout_runner.py`

Regla:

- la tool OpenCode valida parametros
- ejecuta el comando permitido
- registra la invocacion en `logs.jsonl`
- exporta resultados a `artifacts/`

No se rehace la CLI. No se mete una shell generica por detras.

## Checklist De Aceptacion

- [ ] Quedan identificadas acciones peligrosas concretas: borrado, `git push`,
      edicion fuera del repo y shell libre.
- [ ] Cada accion peligrosa tiene un bloqueo explicito o una politica de
      aprobacion clara.
- [ ] Se mantiene el limite operativo dentro del repo y del proyecto actual.
- [ ] Se usa JSON para approvals, transcript, diffs y logs exportados.
- [ ] `artifacts/` queda como evidencia exportada y `.motor/` como metadata
      local/build, no como fuente de verdad del contenido.
- [ ] La propuesta no depende de UI.
- [ ] La propuesta no exige rehacer el CLI unificado ni el pipeline actual de
      artefactos.
