# CLI

El punto de entrada unificado es:

```bash
py -3 tools/engine_cli.py <subcomando> [...]
```

## Subcomandos

`validate`

```bash
py -3 tools/engine_cli.py validate --target scene --path levels/demo_level.json
py -3 tools/engine_cli.py validate --target assets
py -3 tools/engine_cli.py validate --target all --path levels/demo_level.json
```

`migrate`

```bash
py -3 tools/engine_cli.py migrate levels/demo_level.json --output artifacts/demo_level_migrated.json
```

`build-assets`

```bash
py -3 tools/engine_cli.py build-assets
py -3 tools/engine_cli.py build-assets --bundle
```

`run-headless`

```bash
py -3 tools/engine_cli.py run-headless levels/demo_level.json --frames 120 --seed 123
py -3 tools/engine_cli.py run-headless levels/demo_level.json --frames 5 --debug-dump artifacts/debug_dump.json
```

`profile-run`

```bash
py -3 tools/engine_cli.py profile-run levels/demo_level.json --frames 600 --out artifacts/profile_report.json
py -3 tools/engine_cli.py profile-run levels/demo_level.json --frames 120 --out artifacts/profile_edit.json --mode edit
```

`smoke`

Ejecuta en orden:
1. validacion de escena
2. validacion de assets
3. migracion a un artefacto temporal reproducible
4. build de assets
5. run headless corto
6. profile run corto

```bash
py -3 tools/engine_cli.py smoke --scene levels/demo_level.json --frames 5 --seed 123 --out-dir artifacts/cli_smoke
```

## Artefactos esperados

`smoke` deja por defecto:

- `artifacts/cli_smoke/smoke_migrated_scene.json`
- `artifacts/cli_smoke/smoke_debug_dump.json`
- `artifacts/cli_smoke/smoke_profile.json`

## Notas

- Todos los comandos funcionan sin UI.
- `profile-run` exporta un JSON versionado compatible con el profiler interno.
- `run-headless --debug-dump` exporta la geometria serializable del pass `Debug`.
