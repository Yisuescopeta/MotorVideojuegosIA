# Nota de Diseño: Arquitectura CLI MotorVideojuegosIA

## Resumen

Esta nota documenta la arquitectura oficial de la CLI de MotorVideojuegosIA, estableciendo una interfaz pública inequívoca, localizable y ejecutable mediante `python -m motor`.

## Fecha
2025-01-21

## Arquitectura Final

### 1. Estructura de Capas

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTRYPOINTS                                   │
├─────────────────────────────────────────────────────────────────┤
│  motor [command] [options]          (script instalado)          │
│  python -m motor [command] [options] (ejecución como módulo)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              motor/__main__.py                                   │
│  - Punto de entrada para `python -m motor`                      │
│  - Sin lógica, solo delega a motor.cli:main()                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              motor/__init__.py                                   │
│  - Exporta API pública estable                                   │
│  - create_motor_parser()                                         │
│  - run_motor_command()                                           │
│  - cli_main(), main()                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              motor/cli.py                                        │
│  - ArgumentParser con prog="motor"                               │
│  - Descripción: "Official CLI for MotorVideojuegosIA"           │
│  - dispatch_command() - enrutamiento a handlers                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              motor/cli_core.py                                   │
│  - Implementaciones de comandos                                  │
│  - cmd_doctor(), cmd_capabilities(), etc.                       │
│  - Lógica de negocio y manejo de errores                        │
└─────────────────────────────────────────────────────────────────┘
```

### 2. API Pública Estable

La siguiente API es pública y estable (no cambiará sin aviso previo):

```python
from motor.cli import (
    create_motor_parser,   # Crear ArgumentParser para introspección
    run_motor_command,     # Ejecutar comando con lista de args
    cli_main,              # Punto de entrada retornando exit code
    main,                  # Punto de entrada llamando sys.exit()
)
```

### 3. Compatibilidad Hacia Atrás (Deprecated)

```
┌─────────────────────────────────────────────────────────────────┐
│          tools/engine_cli.py - DEPRECATED                        │
├─────────────────────────────────────────────────────────────────┤
│  ROL: Wrapper de compatibilidad temporal                        │
│                                                                    │
│  - Muestra deprecation warning al usar                          │
│  - Delega a motor.cli (interfaz oficial)                        │
│  - No debe usarse en código nuevo                               │
│                                                                    │
│  python -m tools.engine_cli  →  WARNING + motor.cli             │
└─────────────────────────────────────────────────────────────────┘
```

**Nota**: tools/engine_cli.py existe únicamente para:
1. Scripts legacy que aún lo referencian
2. Proporcionar mensaje de migración claro
3. Prevenir ruptura de flujos de trabajo existentes

### 4. Separación de Responsabilidades

| Componente | Responsabilidad | Estabilidad |
|------------|----------------|-------------|
| `motor/__main__.py` | Entrypoint para `python -m motor` | Estable |
| `motor/__init__.py` | Exportar API pública | Estable |
| `motor/cli.py` | Parsing de argumentos, dispatch | Estable |
| `motor/cli_core.py` | Implementación de comandos | Interna |
| `tools/engine_cli.py` | Compatibilidad legacy | Deprecated |

### 5. Uso Correcto

#### Como usuario final:
```bash
# Oficial
motor doctor --project . --json
python -m motor doctor --project . --json

# Legacy (muestra warning)
python -m tools.engine_cli doctor --project .  # DEPRECATED
```

#### Como desarrollador:
```python
# Ejecutar comandos
from motor.cli import run_motor_command
exit_code = run_motor_command(["doctor", "--project", ".", "--json"])

# Introspección del parser
from motor.cli import create_motor_parser
parser = create_motor_parser()
```

### 6. Tests de Contrato

Los siguientes tests garantizan que la interfaz no se desvíe:

- `test_motor_cli_contract.py` - 12 tests de contrato ejecutable
- `test_motor_interface_coherence.py` - Coherencia registry-CLI
- `test_motor_registry_consistency.py` - Consistencia comandos
- `test_motor_entrypoint.py` - Validación de entrypoints

### 7. Identidad del Parser

El parser oficial tiene:
- `prog = "motor"`
- Descripción: "Official CLI for MotorVideojuegosIA"
- Versión: "%(prog)s 2026.03 (MotorVideojuegosIA)"

Esto asegura que `--help` identifique inequívocamente la interfaz.

## Decisiones de Diseño

1. **Una sola interfaz pública**: `motor` es la única interfaz CLI soportada.

2. **tools.engine_cli como deprecated**: No hay dos interfaces públicas en paralelo.

3. **API programática explícita**: Se exportan funciones específicas para uso programático.

4. **Capas separadas**: Parsing (cli.py) separado de implementación (cli_core.py).

5. **Tests de contrato ejecutables**: Los tests verifican que los comandos reales funcionan, no solo que existen.

## Migración desde Código Legacy

Si tienes código usando `tools.engine_cli`:

```python
# Antes (deprecated)
from tools.engine_cli import cmd_doctor
# o
python -m tools.engine_cli doctor --project .

# Después (oficial)
from motor.cli_core import cmd_doctor
# o
python -m motor doctor --project .
# o
from motor.cli import run_motor_command
run_motor_command(["doctor", "--project", "."])
```

## Referencias

- `motor/__init__.py` - API pública
- `motor/cli.py` - Implementación CLI
- `motor/__main__.py` - Entrypoint módulo
- `tools/engine_cli.py` - Documentación de compatibilidad
