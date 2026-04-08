# AI Workflow Examples

This directory contains examples demonstrating how AI assistants can interact
with MotorVideojuegosIA using the **official `motor` CLI interface**.

## Official Interface

The official `motor` CLI is the primary interface for all operations:

```bash
# Official interface (documented syntax)
motor doctor --project .
motor scene create "Level 1"
motor entity create Player

# For development or when motor is not globally installed
python -m motor doctor --project .
```

### Example Scripts Execution Strategy

The Python example scripts in this directory use `python -m motor` internally
to ensure they work reliably in clean checkouts without requiring a global
`motor` binary installation:

```python
# Internal execution in examples (robust for CI/development)
cmd = [sys.executable, "-m", "motor", "doctor", "--project", "."]

# Documented official interface (for user reference)
# motor doctor --project .
```

This approach provides:
- **Maximum reproducibility**: Works in fresh clones without additional setup
- **CI/CD compatibility**: No global installation required in build environments
- **Official syntax preserved**: Documentation and user-facing commands use `motor ...`

⚠️ **Note**: The legacy interface `python -m tools.engine_cli` is deprecated
and should not be used in new scripts or documentation.

## Examples

### 01_query_capabilities.py

Discover what the engine can do - the first step when opening any project.

```bash
python examples/ai_workflows/01_query_capabilities.py
```

Demonstrates:
- Checking for motor_ai.json
- Querying engine capabilities
- Grouping capabilities by category
- Showing example CLI commands

### 02_slice_spritesheet.py

Create animation frames from a sprite sheet.

```bash
python examples/ai_workflows/02_slice_spritesheet.py
```

Demonstrates:
- Checking project health
- Listing assets
- Creating grid-based slices

### 03_create_animated_entity.py

Full workflow for creating an animated entity.

```bash
python examples/ai_workflows/03_create_animated_entity.py
```

Demonstrates:
- Creating scenes and entities
- Adding Animator components
- Setting sprite sheets
- Creating looping and non-looping animation states
- Verifying animator configuration

## Key Principles

1. **Use `motor` command**: All examples use the `motor` CLI as the primary interface
2. **JSON output**: All commands use `--json` for machine-readable output
3. **Project context**: Commands that need project context use `--project .`
4. **Error handling**: Examples handle JSON parsing and show meaningful errors
5. **Idempotent operations**: Most operations can be safely re-run

## Common Commands

```bash
# Project diagnostics
motor doctor --project .
motor capabilities

# Scene operations
motor scene list --project .
motor scene create "My Level" --project .
motor scene load levels/my_level.json --project .

# Entity operations
motor entity create Player --project .
motor component add Player Transform --data '{"x":100,"y":200}' --project .

# Asset operations
motor asset list --project .
motor asset slice grid assets/player.png --cell-width 32 --cell-height 32 --project .

# Animator operations
motor animator ensure Player --project .
motor animator set-sheet Player assets/player.png --project .
motor animator state create Player idle --slices slice_0,slice_1 --fps 8 --loop --project .
motor animator state create Player attack --slices attack_0,attack_1 --fps 12 --no-loop --project .
motor animator info Player --project .
```

## Loop/No-Loop Semantics

When creating animation states:

- `--loop` (default): Animation repeats indefinitely (e.g., idle, walk)
- `--no-loop`: Animation plays once and stops (e.g., attack, jump)

```bash
# Looping idle animation
motor animator state create Player idle --slices idle_0,idle_1 --fps 8 --loop

# Non-looping attack animation
motor animator state create Player attack --slices atk_0,atk_1 --fps 12 --no-loop
```

## Environment Setup

The examples automatically configure the Python path to find the motor CLI.
If running commands manually, ensure the project root is in PYTHONPATH:

```bash
# Animator operations
motor animator ensure Player --project .
motor animator set-sheet Player assets/player.png --project .
motor animator state create Player idle --slices slice_0,slice_1 --fps 8 --loop --project .
motor animator state create Player attack --slices attack_0,attack_1 --fps 12 --no-loop --project .
motor animator info Player --project .
```

Or on Windows:

```powershell
$env:PYTHONPATH = "C:\MejoraIA\MotorVideojuegosIA;$env:PYTHONPATH"
motor doctor --project .
```
