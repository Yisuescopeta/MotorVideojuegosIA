# Taxonomia canonica del motor

Este documento clasifica los subsistemas del repo para guiar compatibilidad,
prioridad de tests y lectura documental. No introduce un sistema de plugins.

## Categorias

### Core obligatorio

Base que define el contrato minimo del motor. Si una pieza cae aqui, romperla
afecta a la promesa central: datos serializables mandan y editor, runtime, API y
CLI trabajan sobre el mismo modelo.

### Modulos oficiales opcionales

Capacidades soportadas oficialmente e integradas en el repo, pero no necesarias
para que el motor conserve su contrato minimo.

`Opcional` no significa plugin. Significa que el motor puede seguir siendo
coherente aunque esa capacidad no sea requisito del nucleo base.

### Experimental/tooling

Utilidades, integraciones IA, research, datasets, runners, benchmarks o
orquestacion. Pueden ser valiosos, pero no son contrato duro del motor.

## Clasificacion por subsistema

| Subsistema | Clasificacion | Razon |
|---|---|---|
| ECS base | `core obligatorio` | Define entidades, componentes y mundo. |
| `Scene` | `core obligatorio` | Es la fuente de verdad serializable. |
| `SceneManager` | `core obligatorio` | Coordina workspace, authoring, dirty state e `EDIT -> PLAY -> STOP`. |
| contratos internos de escena/runtime (`engine/scenes/contracts.py`, `engine/core/runtime_contracts.py`) | `core obligatorio` | Fijan limites de integracion entre runtime, authoring, workspace y API. |
| serializacion y schema/migraciones | `core obligatorio` | Fijan `scene schema_version = 2`, `prefab schema_version = 2` y guardado canonico. |
| editor base | `core obligatorio` | Traduce authoring al modelo compartido. |
| jerarquia | `core obligatorio` | Forma parte de datos serializables y tests de authoring. |
| `EngineAPI` | `core obligatorio` | Fachada estable para agentes, tests, CLI y automatizacion. |
| contrato comun de physics backends + fallback `legacy_aabb` | `core obligatorio` | Garantiza una ruta fisica base y queries publicas. |
| assets | `modulos oficiales opcionales` | Integrados y soportados, pero no requisito del nucleo minimo. |
| prefabs | `modulos oficiales opcionales` | Integrados en authoring/serializacion, pero no condicion minima. |
| tilemap | `modulos oficiales opcionales` | Capacidad oficial basada en datos, fuera del nucleo minimo. |
| audio | `modulos oficiales opcionales` | Capacidad soportada, no requisito de simulacion base. |
| UI serializable | `modulos oficiales opcionales` | Capa oficial basada en datos, no core minimo. |
| backend `box2d` | `modulos oficiales opcionales` | Mejora oficial opcional; `legacy_aabb` mantiene el core. |
| `engine/navigation` | `experimental/tooling` | Infraestructura de pathfinding independiente, sin integracion core obligatoria. |
| `engine/rl` | `experimental/tooling` | Integra workflows IA/RL, no el contrato minimo del runtime. |
| agente nativo clean-room (`engine/agent`) | `experimental/tooling` | Orquesta sesiones IA, herramientas, permisos y UI de asistencia sin cambiar el contrato persistente del motor. |
| datasets y runners | `experimental/tooling` | Explotacion y validacion IA, no nucleo contractual. |
| orquestacion multiagente archivada | `experimental/tooling` | Material de trabajo e investigacion, no contrato vigente. |
| debug avanzado y benchmarking | `experimental/tooling` | Utiles para endurecimiento, no condicion minima. |

## Decisiones

### Editor base

El editor base es `core obligatorio` porque el proyecto incluye authoring como
parte del contrato. Aun asi, la UI no es fuente de verdad: debe traducir al
modelo serializable y a `SceneManager`/`EngineAPI`.

### Jerarquia

La jerarquia es core porque afecta save/load, duplicacion de subarboles,
parenting, seleccion y authoring compartido.

### Assets y prefabs

Assets y prefabs son oficiales, pero el contrato minimo puede explicarse sin
exigir todo el pipeline de assets o authoring basado en prefabs.

### Physics

El contrato comun de backends y el fallback `legacy_aabb` son core. `box2d` es
un modulo oficial opcional porque no debe ser dependencia obligatoria.

### RL y tooling IA

RL, multiagente, datasets y runners existen para investigacion y automatizacion.
Deben tratarse como `experimental/tooling`, aunque tengan tests y utilidad real.

## Regla de promocion

Antes de promover una capacidad a `core obligatorio`, justificar:

1. que afecta al contrato base de datos o authoring compartido
2. que requiere compatibilidad fuerte
3. que su ausencia romperia la definicion minima del motor

Si no cumple esas condiciones, clasificarla primero como
`modulos oficiales opcionales` o `experimental/tooling`.
