"""
GRAMÁTICA OFICIAL MOTORVIDEOJUEGOSIA CLI
=======================================

Documento de especificación gramatical única y consistente para la CLI oficial.

ÚLTIMA ACTUALIZACIÓN: 2025-01-21
VERSIÓN: 2026.03

PRINCIPIOS FUNDAMENTALES
------------------------
1. Sustantivos en singular: scene, entity, component, asset, animator, project
2. Verbos simples y explícitos: create, list, load, save, add, remove, info
3. Jerarquía consistente: motor <noun> [<subnoun>] <verb> [<args>]
4. Sin aliases documentados como interfaz oficial
5. Los aliases legacy (si existen) son compatibilidad temporal, no contrato

ESTRUCTURA GENERAL
------------------
motor <SCOPE> [<SUBSCOPE>] <ACTION> [<ARGS>] [--json]

Comandos principales:
- capabilities          Listar capacidades del motor
- doctor                Diagnóstico del proyecto
- project               Operaciones de proyecto
- scene                 Operaciones de escenas
- entity                Operaciones de entidades
- component             Operaciones de componentes
- animator              Operaciones de animación
- asset                 Operaciones de assets

GRAMÁTICA DETALLADA
-------------------

### INTROSPECCIÓN
motor capabilities [--json]
motor doctor [--project <path>] [--json]

### PROYECTO
motor project info [--project <path>] [--json]
motor project bootstrap-ai [--project <path>] [--json]

### ESCENAS
motor scene list [--project <path>] [--json]
motor scene create <name> [--project <path>] [--json]
motor scene load <path> [--project <path>] [--json]
motor scene save [--project <path>] [--json]

### ENTIDADES
motor entity create <name> [--components <json>] [--project <path>] [--json]

### COMPONENTES
motor component add <entity> <component> [--data <json>] [--project <path>] [--json]

### ANIMATOR (estados como subcomando)
motor animator info <entity> [--project <path>] [--json]
motor animator set-sheet <entity> <asset> [--project <path>] [--json]
motor animator ensure <entity> [--sheet <asset>] [--project <path>] [--json]

# Estados de animación (subcomando 'state')
motor animator state create <entity> <state> --slices <s1,s2,...>
    [--fps <n>] [--loop|--no-loop] [--set-default] [--auto-create]
    [--project <path>] [--json]

motor animator state remove <entity> <state> [--project <path>] [--json]

### ASSETS
motor asset list [--search <query>] [--project <path>] [--json]

# Slices como subcomando de asset
motor asset slice list <asset> [--project <path>] [--json]
motor asset slice grid <asset> --cell-width <n> --cell-height <n>
    [--margin <n>] [--spacing <n>] [--pivot-x <f>] [--pivot-y <f>]
    [--naming-prefix <str>] [--project <path>] [--json]

motor asset slice auto <asset> [--pivot-x <f>] [--pivot-y <f>]
    [--naming-prefix <str>] [--alpha-threshold <n>] [--preview]
    [--project <path>] [--json]

motor asset slice manual <asset> --slices <json>
    [--pivot-x <f>] [--pivot-y <f>] [--naming-prefix <str>]
    [--project <path>] [--json]

CAMBIOS RESPECTO A VERSIONES ANTERIORES
---------------------------------------
- "upsert-state" → "animator state create" (jerarquía clara)
- "remove-state" → "animator state remove" (jerarquía clara)
- "project manifest" → "project info" (consistencia con otros comandos info)
- "assets" (plural) → "asset" (singular, consistente)
- Los comandos de slice ahora son SIEMPRE bajo "asset slice"

COMPATIBILIDAD
--------------
Los siguientes aliases pueden funcionar por compatibilidad pero NO son
parte de la gramática oficial y no deben documentarse como tal:
- motor animator upsert-state (legacy, usar 'animator state create')
- motor animator remove-state (legacy, usar 'animator state remove')
- motor project manifest (legacy, usar 'project info')

EJEMPLOS VÁLIDOS
----------------
motor doctor --project . --json
motor scene create "Level 1" --project .
motor entity create Player --components '{"Transform":{"x":100}}'
motor component add Player Sprite --data '{"asset_path":"player.png"}'
motor animator state create Player idle --slices idle_0,idle_1,idle_2 --fps 8 --loop
motor asset slice grid assets/tiles.png --cell-width 32 --cell-height 32

VALIDACIÓN
----------
Tests que verifican esta gramática:
- test_motor_cli_contract.py::RegistryToCLIExecutableContractTests
- test_motor_interface_coherence.py::RegistryToCLICoherenceTests
- test_motor_registry_consistency.py::MotorRegistryConsistencyTests

Si se detecta una segunda sintaxis oficial para la misma operación,
los tests deben fallar.
"""
