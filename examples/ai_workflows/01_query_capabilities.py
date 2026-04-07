#!/usr/bin/env python3
"""
Example 01: Query Capabilities

Demonstrates how an AI assistant can discover what the engine can do.
This is typically the first step when opening a project folder.
"""

import json
import subprocess
import sys
from pathlib import Path


def run_command(*args):
    """Run a motor CLI command and return parsed JSON."""
    cmd = [sys.executable, "-m", "tools.engine_cli"] + list(args) + ["--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)


def main():
    print("=" * 60)
    print("Example 01: Query Engine Capabilities")
    print("=" * 60)
    
    # Step 1: Check if this is a motor project
    project_path = Path(".")
    motor_ai_path = project_path / "motor_ai.json"
    
    if not motor_ai_path.exists():
        print("\n⚠️  No motor_ai.json found. This may not be a MotorVideojuegosIA project.")
        print("   Run: python -m tools.engine_cli doctor --project .")
        return 1
    
    print(f"\n✓ Found motor project at: {project_path.absolute()}")
    
    # Step 2: Get capabilities
    print("\n📋 Querying engine capabilities...")
    result = run_command("capabilities")
    
    if not result.get("success"):
        print(f"❌ Failed: {result.get('message')}")
        return 1
    
    data = result["data"]
    print(f"\n✓ Engine version: {data['engine_version']}")
    print(f"✓ Schema version: {data['capabilities_schema_version']}")
    print(f"✓ Total capabilities: {data['count']}")
    
    # Step 3: Group capabilities by category
    print("\n📊 Capabilities by Category:")
    categories = {}
    for cap in data["capabilities"]:
        scope = cap["id"].split(":")[0]
        categories.setdefault(scope, []).append(cap)
    
    for scope, caps in sorted(categories.items()):
        print(f"\n  {scope.upper()} ({len(caps)} capabilities):")
        for cap in caps[:3]:  # Show first 3
            print(f"    - {cap['id']}: {cap['summary']}")
        if len(caps) > 3:
            print(f"    ... and {len(caps) - 3} more")
    
    # Step 4: Show example CLI commands
    print("\n💡 Example CLI Commands:")
    examples = [
        ("doctor", "Check project health"),
        ("scene list", "List all scenes"),
        ("assets list", "List all assets"),
        ("entity create Player", "Create an entity"),
    ]
    for cmd, desc in examples:
        print(f"    motor {cmd:<25} # {desc}")
    
    print("\n" + "=" * 60)
    print("Next steps:")
    print("  1. Run: python -m tools.engine_cli doctor --project .")
    print("  2. Try: python examples/ai_workflows/02_slice_spritesheet.py")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())