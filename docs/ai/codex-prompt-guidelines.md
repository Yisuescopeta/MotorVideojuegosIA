# Guia De Prompts Para Codex

Estado: referencia operativa para pedir cambios pequenos, verificables y con
alcance cerrado.

## Regla base

Un prompt bueno define objetivo, perimetro y validacion. No delega a Codex la
decision de que mas tocar "ya que esta en el repo".

## Formato recomendado

Usa este esqueleto:

```text
Objetivo:
Rama objetivo:
Milestone:
Subsistema principal:
Archivos permitidos:
Archivos excluidos:
Restricciones:
Criterios de aceptacion:
Validaciones a ejecutar:
```

## Que debe especificar el prompt

- un objetivo unico y observable
- la rama objetivo exacta
- el milestone o corte tecnico concreto
- el subsistema principal
- archivos o carpetas permitidos
- archivos o carpetas excluidos, en especial runtime critico
- restricciones explicitas de alcance
- criterios de aceptacion verificables
- validaciones reales a ejecutar

## Normas de alcance

- nombrar exclusiones explicitas
- prohibir expansion de alcance "por limpieza"
- prohibir refactors amplios si no son el objetivo
- decir si el trabajo es solo lectura, solo validacion o implementacion
- si el prompt afecta contrato publico, pedir la doc canonica correspondiente

## Como pedir milestones pequenos

- pedir un solo comportamiento o un solo paquete documental por vez
- usar nombres de milestone cortos y cerrables
- separar wiring, contrato y UI si se pueden validar por separado
- abrir otra tarea si aparece un cruce con otro subsistema core

## Como pedir solo lectura o validacion

Cuando no quieres cambios de codigo, dilo literal:

```text
No edites archivos. Revisa consistencia, resume riesgos y ejecuta solo estas
validaciones:
```

Cuando quieres cambios pequenos con validacion controlada:

```text
No toques archivos fuera de esta lista. Si detectas deuda ajena, reportala como
riesgo y no la arregles en esta tarea.
```

## Prompt bueno

```text
Objetivo: actualizar la plantilla PR para ramas paralelas.
Rama objetivo: chore/repo-workspace-foundation
Milestone: repo-pr-template
Subsistema principal: gobernanza documental
Archivos permitidos: .github/pull_request_template.md, docs/README.md
Archivos excluidos: engine/, motor/, README.md, AGENTS.md
Restricciones: no anadas features del motor; no cambies tests salvo que un link de gobernanza lo exija.
Criterios de aceptacion: la plantilla PR pide objetivo, subsistemas, archivos criticos, validaciones y riesgos; docs/README enlaza el recurso nuevo.
Validaciones a ejecutar: py -m unittest tests.test_repository_governance -v
```

## Prompt malo

```text
Arregla la organizacion del repo y deja todo listo para trabajar mejor.
```

Problemas del prompt malo:

- no define objetivo cerrado
- no define rama ni milestone
- no limita archivos
- no excluye areas criticas
- no fija criterios de aceptacion
- invita a expansion de alcance
