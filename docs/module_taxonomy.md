# Taxonomia canonica del motor

## Proposito

Este documento fija una taxonomia tecnica para guiar prioridades,
compatibilidad y extensibilidad del proyecto sin introducir un sistema de
plugins ni intentar pluginizar el arbol actual del repo.

La idea no es decidir como se cargan modulos en runtime. La idea es dejar claro
que partes del proyecto forman el contrato base del motor, que partes son
capacidades oficiales pero opcionales, y que partes deben tratarse como
`experimental/tooling`.

## Criterios

### Core obligatorio

Base que define el contrato del motor y que no debe romperse sin justificacion
fuerte. Si una pieza cae aqui, su comportamiento afecta a la promesa central del
proyecto: datos serializables mandan y editor, runtime y API operan sobre el
mismo modelo.

### Modulos oficiales opcionales

Capacidades soportadas oficialmente, integradas en el repo y cubiertas en
distinto grado por tests, pero no necesarias para considerar el motor
"operativo" en su contrato minimo.

`Opcional` no significa plugin. Significa que el motor puede seguir existiendo
como motor coherente aunque esa capacidad no sea requisito del nucleo base.

### Experimental/tooling

Utilidades, integraciones IA, harnesses o capacidades que no forman parte del
contrato minimo del motor.

`Experimental` no significa descartable. Significa que no se debe tratar como
parte del core contractual ni como base de compatibilidad dura del motor.

## Clasificacion por subsistema

| Subsistema | Clasificacion | Razon breve |
|---|---|---|
| ECS base | `core obligatorio` | Define entidades, componentes y mundo, que son la base comun del modelo. |
| `Scene` | `core obligatorio` | Es la fuente de verdad serializable del contenido editable. |
| `SceneManager` | `core obligatorio` | Coordina workspace, authoring, dirty state e `EDIT -> PLAY -> STOP`. |
| serializacion y schema/migraciones | `core obligatorio` | Fijan el contrato de datos y el guardado canonico `v2`. |
| editor base | `core obligatorio` | El editor base es core como traductor del modelo compartido, no como fuente de verdad propia. |
| jerarquia | `core obligatorio` | Ya forma parte de datos serializables, authoring comun y tests de regresion. |
| API publica (`EngineAPI`) | `core obligatorio` | Es la fachada estable para agentes, CLI, tests y automatizacion. |
| contrato comun de physics backends + fallback `legacy_aabb` | `core obligatorio` | El motor base necesita una via fisica comun y una ruta obligatoria de fallback. |
| assets | `modulos oficiales opcionales` | Son importantes y estan integrados, pero el contrato minimo del motor no debe depender de todo el pipeline de assets. |
| prefabs | `modulos oficiales opcionales` | Estan bien integrados en authoring y serializacion, pero no son condicion minima para el nucleo del motor. |
| tilemap | `modulos oficiales opcionales` | Capacidad oficial del motor, no requisito del core minimo. |
| audio | `modulos oficiales opcionales` | Capacidad soportada, pero fuera del contrato minimo de simulacion y authoring base. |
| UI serializable | `modulos oficiales opcionales` | Es una capa oficial basada en datos, pero no parte del nucleo minimo del motor. |
| backend `box2d` | `modulos oficiales opcionales` | Mejora oficial y soportada, pero no dependencia obligatoria del motor. |
| `engine/rl` | `experimental/tooling` | Integra el motor con workflows IA, no con el contrato minimo del runtime base. |
| tooling de datasets y runners | `experimental/tooling` | Extienden validacion y explotacion IA del motor, no el nucleo contractual. |
| orquestacion multiagente | `experimental/tooling` | Guía de trabajo y tooling de investigacion, no parte del motor base. |
| debug avanzado y benchmarking | `experimental/tooling` | Muy utiles para endurecimiento, pero no condicion minima para considerar el motor operativo. |

## Notas de decision

### Por que el editor base es core pero la UI no es la fuente de verdad

El editor base cae en `core obligatorio` porque el proyecto no es solo un
runtime headless: la capacidad de authoring compartido forma parte del valor del
motor. Aun asi, la UI no define el contrato. El editor debe traducir acciones al
modelo serializable comun y a las rutas compartidas de `SceneManager` y
`EngineAPI`.

### Por que la jerarquia es core

La jerarquia ya no es una affordance visual opcional. Forma parte de los datos
serializables, del flujo de authoring comun y de varias suites de tests
(`save/load`, duplicacion de subarboles, parent/child, play/stop).

### Por que assets y prefabs son oficiales opcionales

Assets y prefabs estan bien integrados y son capacidades oficiales del motor.
Pero el contrato minimo del proyecto sigue pudiendo explicarse sin exigir todo
el pipeline de assets ni el authoring basado en prefabs como condicion dura del
core.

### Por que el contrato fisico base es core pero `box2d` no

El motor necesita una via fisica comun y publica. Por eso el contrato comun de
backends y el fallback `legacy_aabb` son `core obligatorio`.

`box2d` queda como `modulo oficial opcional` porque mejora el runtime cuando la
dependencia existe, pero el motor no lo exige como base ni debe romperse por su
ausencia.

### Por que RL, multiagente y debug avanzado no son core contractual

`engine/rl`, tooling de datasets, runners, multiagente y benchmarking sirven
para investigacion, validacion y explotacion IA del motor. Son valiosos, pero
no deben condicionar la compatibilidad minima del nucleo ni desplazar el foco
del contrato serializable compartido.

## Regla de uso

Antes de promover una capacidad a `core obligatorio`, hay que justificar:

1. que afecta al contrato base de datos o de authoring compartido
2. que requiere compatibilidad fuerte y soporte estable
3. que su ausencia romperia la definicion minima de motor que este repo quiere
   sostener

Si no cumple esas condiciones, debe evaluarse primero como `modulo oficial
opcional` o como `experimental/tooling`.
