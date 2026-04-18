# Estrategia De Ramas Y Workspaces

Estado: referencia operativa para desarrollo paralelo. No redefine contratos del
motor.

## Convencion de ramas

Formato general:

```text
<tipo>/<scope>-<milestone>
```

Reglas:

- usar `kebab-case` en `scope` y `milestone`
- el `scope` nombra el subsistema principal
- el `milestone` nombra un corte pequeno y verificable
- no reutilizar una rama para cambiar de objetivo a mitad del trabajo

Tipos:

- `chore`
- `refactor`
- `feat`
- `test`
- `docs`

Ejemplos:

- `chore/repo-workspace-foundation`
- `feat/runtime-step-timing`
- `refactor/render-command-buffer`
- `test/physics-ray-regression`
- `docs/editor-handbook-sync`

## Excepcion para ramas de integracion

Las ramas de integracion no usan milestone en el nombre. Formato:

```text
integration/<dominio>
```

Ejemplos:

- `integration/base-tecnica`
- `integration/runtime`
- `integration/render`

## Convencion de workspaces

Formato:

```text
ws-<tipo>-<scope>-<milestone>
```

Reglas:

- espejo del slug de la rama sin `/`
- un workspace por rama activa
- no reutilizar un workspace viejo para otra rama

Ejemplos:

- `ws-chore-repo-workspace-foundation`
- `ws-feat-runtime-step-timing`
- `ws-test-physics-ray-regression`

## Reglas de alcance por rama

- una rama toca un subsistema principal
- una rama solo puede tocar dependencias inmediatas si la necesidad esta
  justificada en PR o milestone
- si el cambio exige tocar tres o mas subsistemas core, abrir primero una RFC lite
- no mezclar refactor amplio con feature no relacionada
- no usar una rama documental para introducir comportamiento nuevo
- no usar una rama de feature para limpiar codigo ajeno "ya que estoy"

## Cuando rebasear o mergear

- rebasear contra su base antes de abrir PR
- rebasear otra vez antes de merge si la base avanzo
- mergear a `integration/<dominio>` cuando el trabajo ya es coherente dentro del
  dominio pero aun no esta listo para troncal
- promover a rama troncal solo desde una rama limpia, validada y con alcance
  cerrado

## Politica de sincronizacion

- feature y refactor pequenos nacen desde su base o desde la rama de integracion
  activa del dominio
- las ramas de integracion absorben trabajo de un solo dominio
- si una rama queda desfasada y empieza a requerir merges defensivos frecuentes,
  debe rebasarse o partirse

## Politica de mezcla prohibida

No mezclar en una misma rama:

- refactor transversal + feature nueva
- cambio de contrato publico + arreglo incidental no relacionado
- cambios en runtime critico + reordenamiento documental amplio
- varios milestones tecnicos que no comparten la misma validacion
