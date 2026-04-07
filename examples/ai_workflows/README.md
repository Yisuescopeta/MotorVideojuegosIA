# AI Workflow Examples for MotorVideojuegosIA

This directory contains practical examples for AI assistants working with the motor.

## Quick Reference

```bash
# Discover capabilities
python -m tools.engine_cli capabilities --json

# Check project health
python -m tools.engine_cli doctor --project . --json

# List available scenes
python -m tools.engine_cli scene list --project . --json
```

## Examples

### 1. Query Capabilities (01_query_capabilities.py)

Shows how to discover what the engine can do.

```bash
python examples/ai_workflows/01_query_capabilities.py
```

### 2. Slice a Sprite Sheet (02_slice_spritesheet.py)

Demonstrates grid-based slicing for animation.

```bash
python examples/ai_workflows/02_slice_spritesheet.py
```

### 3. Create Animated Entity (03_create_animated_entity.py)

Full workflow: scene → entity → animator → states.

```bash
python examples/ai_workflows/03_create_animated_entity.py
```

## Common Patterns

### Pattern 1: Detect and Validate Project

```python
from pathlib import Path
import subprocess
import json

project_path = Path(".")

# Validate project health
result = subprocess.run(
    ["python", "-m", "tools.engine_cli", "doctor", 
     "--project", str(project_path), "--json"],
    capture_output=True, text=True
)
diagnosis = json.loads(result.stdout)

if diagnosis["data"]["healthy"]:
    print("Project is ready for AI workflows")
else:
    print(f"Issues found: {diagnosis['data']['issues']}")
```

### Pattern 2: Execute Headless Command

```python
import subprocess
import json

def motor_command(*args, project="."):
    """Execute a motor CLI command and return parsed JSON."""
    cmd = ["python", "-m", "tools.engine_cli"] + list(args) + ["--project", project, "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

# Example: Create a scene
result = motor_command("scene", "create", "My Level")
if result["success"]:
    print(f"Scene created: {result['data']['path']}")
```

### Pattern 3: Component Data Builder

```python
def build_transform(x=0, y=0, rotation=0):
    return {
        "Transform": {
            "enabled": True,
            "x": x,
            "y": y,
            "rotation": rotation,
            "scale_x": 1.0,
            "scale_y": 1.0,
        }
    }

def build_animator(sprite_sheet=""):
    return {
        "Animator": {
            "enabled": True,
            "sprite_sheet_path": sprite_sheet,
            "animations": {},
        }
    }
```

## Error Handling

Always check the `success` field in responses:

```python
result = motor_command("entity", "create", "Player")
if not result["success"]:
    print(f"Error: {result['message']}")
    # Handle error appropriately
```

## Resources

- `motor_ai.json` in your project root contains the full capability registry
- `START_HERE_AI.md` provides project-specific guidance
- Run `python -m tools.engine_cli --help` for all available commands