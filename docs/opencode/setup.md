# Setup De OpenCode En Este Repo

## Objetivo

Este repo anade una configuracion de proyecto para OpenCode sin afectar a
desarrolladores que no lo usan.

Archivos introducidos:

- `opencode.jsonc`
- `AGENTS.md`

## Que Hace `opencode.jsonc`

`opencode.jsonc` centraliza las instrucciones de proyecto usando la opcion
`instructions` de OpenCode.

En este repo carga:

- `docs/architecture.md`
- `docs/cli.md`
- `docs/rl.md`
- `docs/opencode/*.md`

OpenCode combina esas instrucciones con `AGENTS.md`, asi que:

- las reglas comunes viven en un punto central reutilizable
- `AGENTS.md` se mantiene corto
- no hace falta duplicar el mismo contrato en multiples archivos

## Como Arrancarlo

### Opcion 1. Desde la raiz del repo

Abre una terminal en la raiz del proyecto y arranca OpenCode desde ahi.

Ejemplo:

```powershell
cd C:\Users\usuario\Downloads\MotorVideojuegosIA-main\MotorVideojuegosIA-main
opencode
```

### Opcion 2. Forzando este archivo de configuracion

Si tu instalacion de OpenCode no autodetecta `opencode.jsonc` como config de
proyecto, fuerza el archivo explicitamente.

PowerShell:

```powershell
$env:OPENCODE_CONFIG = "$PWD\\opencode.jsonc"
opencode
```

Sesion puntual:

```powershell
cmd /c "set OPENCODE_CONFIG=%CD%\\opencode.jsonc && opencode"
```

## Que Debe Esperar Un Usuario De OpenCode Aqui

- OpenCode recibe el contrato del motor antes de actuar.
- Las reglas del repo priorizan data-first, no-UI-source-of-truth y validacion
  no visual.
- La configuracion no cambia el flujo normal del repo para quien no use
  OpenCode.

## Validacion Recomendada

- Confirmar que OpenCode arranca desde la raiz del repo.
- Confirmar que ve `AGENTS.md`.
- Confirmar que carga instrucciones desde `docs/architecture.md`,
  `docs/cli.md`, `docs/rl.md` y `docs/opencode/*.md`.

## Notas

- OpenCode soporta JSON y JSONC para configuracion.
- La documentacion oficial describe `instructions` como el mecanismo recomendado
  para reutilizar reglas y evitar duplicacion.
