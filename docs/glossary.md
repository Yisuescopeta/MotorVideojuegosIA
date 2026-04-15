# Glosario

Conceptos breves para orientarse antes de leer las referencias profundas.

## `Scene`

Fuente persistente de verdad del motor. Contiene entidades, componentes
serializables, reglas, `feature_metadata` y referencias de prefab. Ver
[architecture.md](architecture.md) y [schema_serialization.md](schema_serialization.md).

## `World`

Proyeccion operativa usada por editor y runtime. No es formato de persistencia
ni debe convertirse en authoring state por accidente. Ver [architecture.md](architecture.md).

## `SceneManager`

Coordina workspace, escenas abiertas, dirty state, historial, transacciones y el
ciclo `EDIT -> PLAY -> STOP`. Ver [architecture.md](architecture.md).

## `EngineAPI`

Fachada publica estable para agentes, tests, CLI y automatizacion. Los flujos
publicos deben preferirla sobre internals privados. Ver [api.md](api.md).

## `motor`

CLI publica oficial del proyecto. Usa `py -m motor` si el paquete no esta
instalado en modo editable. Ver [cli.md](cli.md).

## `feature_metadata`

Bloque serializable para configuracion transversal de escena, como render,
fisica o scene flow. Ver [schema_serialization.md](schema_serialization.md).

## `core obligatorio`

Base minima del contrato del motor: datos serializables, authoring compartido,
runtime, `EngineAPI`, CLI y fallback fisico comun. Ver [module_taxonomy.md](module_taxonomy.md).

## `modulos oficiales opcionales`

Capacidades soportadas oficialmente pero no necesarias para explicar el nucleo
minimo del motor. `Opcional` no significa plugin. Ver [module_taxonomy.md](module_taxonomy.md).

## `experimental/tooling`

Research, automatizacion, datasets, runners o integraciones utiles que no son
contrato duro del motor. Ver [module_taxonomy.md](module_taxonomy.md).

## `legacy_aabb`

Backend fisico base que debe seguir disponible como fallback. `box2d` puede ser
opcional, pero no reemplaza esta garantia. Ver [architecture.md](architecture.md).

## `motor_ai.json`

Artefacto machine-readable generado dentro de cada proyecto para orientar a una
IA. No es documentacion canonica versionada del repo raiz. Ver
[MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md).

## `START_HERE_AI.md`

Guia generada por proyecto junto con `motor_ai.json`. Se crea con
`py -m motor project bootstrap-ai --project .` y debe distinguir capacidades
implementadas de capacidades planificadas. Ver [MOTOR_AI_JSON_CONTRACT.md](MOTOR_AI_JSON_CONTRACT.md).

