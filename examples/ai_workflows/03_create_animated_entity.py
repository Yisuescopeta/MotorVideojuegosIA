#!/usr/bin/env python3
"""
Example 03: Create Animated Entity (Official Motor CLI Workflow)

Full workflow demonstrating the official AI-facing animator API:
1. Validate project with doctor
2. Create a scene
3. Create an entity
4. Ensure Animator component exists (auto-creates if missing)
5. Set sprite sheet
6. Configure animation states (loop and no-loop)

Uses the official `motor` CLI interface.

Official Animator Workflow (Grammar: motor <noun> [<subnoun>] <verb>):
  motor animator ensure <entity> [--sheet <asset>]
  motor animator set-sheet <entity> <asset>
  motor animator state create <entity> <state> --slices <names> [--loop|--no-loop]
  motor animator state remove <entity> <state>
  motor animator info <entity>

Loop/No-Loop Semantics:
  --loop      : Animation repeats indefinitely (default)
  --no-loop   : Animation plays once and stops
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Ensure motor CLI is available in the environment
ROOT = Path(__file__).resolve().parents[2]
ENV = os.environ.copy()
PYTHONPATH = ENV.get("PYTHONPATH", "")
ENV["PYTHONPATH"] = str(ROOT) if not PYTHONPATH else str(ROOT) + os.pathsep + PYTHONPATH


def run_command(*args, project="."):
    """Run a motor CLI command and return parsed JSON.

    Uses 'python -m motor' for robustness in clean checkouts without
    global motor binary installation.
    """
    cmd = [sys.executable, "-m", "motor"] + list(args) + ["--project", project, "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=ENV)
    # Parse JSON output (skip any leading non-JSON lines)
    output = result.stdout
    if "{" in output:
        output = output[output.index("{"):]
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"success": False, "message": f"Invalid JSON: {output[:200]}", "data": {}}


def main():
    print("=" * 60)
    print("Example 03: Create Animated Entity (Official Motor CLI)")
    print("=" * 60)
    
    project_path = Path(".")
    
    # Step 1: Validate project
    print("\n🔍 Validating project...")
    result = run_command("doctor", project=str(project_path))
    
    if not result["data"]["healthy"] and result["data"]["issues"]:
        print(f"❌ Project has critical issues: {result['data']['issues']}")
        return 1
    
    print("✓ Project validation passed")
    
    # Step 2: Create a new scene
    scene_name = "AnimatedLevel"
    print(f"\n🎬 Creating scene: {scene_name}...")
    result = run_command("scene", "create", scene_name, project=str(project_path))
    
    if not result["success"]:
        print(f"❌ Failed to create scene: {result.get('message')}")
        return 1
    
    scene_path = result["data"]["path"]
    print(f"✓ Scene created: {scene_path}")
    
    # Step 3: Create the player entity
    entity_name = "Player"
    print(f"\n👤 Creating entity: {entity_name}...")
    result = run_command("entity", "create", entity_name, project=str(project_path))
    
    if not result["success"]:
        print(f"❌ Failed to create entity: {result.get('message')}")
        return 1
    
    print(f"✓ Entity '{entity_name}' created")
    
    # Step 4: Add Transform component (canonical name)
    print("\n📦 Adding Transform component...")
    transform_data = json.dumps({"x": 100, "y": 200, "scale_x": 1, "scale_y": 1})
    result = run_command(
        "component", "add", entity_name, "Transform",
        "--data", transform_data,
        project=str(project_path)
    )
    
    if not result["success"]:
        print(f"⚠️  Could not add Transform: {result.get('message')}")
    else:
        print(f"✓ Transform added at position (100, 200)")
    
    # Step 5: Add Sprite component (canonical name, not SpriteRenderer)
    print("\n🎨 Adding Sprite component...")
    sprite_data = json.dumps({"enabled": True, "tint": "#FFFFFF"})
    result = run_command(
        "component", "add", entity_name, "Sprite",
        "--data", sprite_data,
        project=str(project_path)
    )
    
    if not result["success"]:
        print(f"⚠️  Could not add Sprite: {result.get('message')}")
    else:
        print(f"✓ Sprite added")
    
    # Step 6: Ensure Animator component exists with sprite sheet (idempotent)
    # The 'ensure --sheet' command guarantees Animator exists AND has the specified sheet.
    # If Animator doesn't exist: creates it with the sheet.
    # If Animator already exists: updates the sheet to the specified one.
    print("\n🔍 Looking for sprite assets...")
    result = run_command("asset", "list", project=str(project_path))
    images = [a for a in result["data"]["assets"] if a["path"].lower().endswith(".png")]

    if images:
        sprite_asset = images[0]["path"]
        print(f"✓ Found sprite asset: {sprite_asset}")

        # Ensure Animator exists AND set the sprite sheet in one command
        print(f"\n🎭 Ensuring Animator exists with sprite sheet...")
        result = run_command(
            "animator", "ensure", entity_name,
            "--sheet", sprite_asset,
            project=str(project_path)
        )

        if result["success"]:
            created = result["data"].get("created", False)
            updated = result["data"].get("updated", False)
            if created:
                print(f"✓ Animator created and configured with sprite sheet")
            elif updated:
                print(f"✓ Animator updated with new sprite sheet")
            else:
                print(f"✓ Animator already exists with correct sprite sheet")
        else:
            print(f"⚠️  Could not ensure Animator: {result.get('message')}")
        
        # Step 7: Check for slices
        result = run_command("asset", "slice", "list", sprite_asset, project=str(project_path))
        slices = result["data"]["slices"]
        
        if len(slices) >= 4:
            # Create looping idle animation state
            slice_names = ",".join([s["name"] for s in slices[:4]])
            print(f"\n🎬 Creating 'idle' animation state (looping)...")
            result = run_command(
                "animator", "state", "create", entity_name, "idle",
                "--slices", slice_names,
                "--fps", "8",
                "--loop",
                "--set-default",
                project=str(project_path)
            )

            if result["success"]:
                print(f"✓ Animation state 'idle' created with {len(slices[:4])} frames (looping)")
            else:
                print(f"⚠️  Could not create idle state: {result.get('message')}")

            # Create non-looping attack animation state if enough slices
            if len(slices) >= 6:
                attack_slices = ",".join([s["name"] for s in slices[4:6]])
                print(f"\n⚔️  Creating 'attack' animation state (non-looping)...")
                result = run_command(
                    "animator", "state", "create", entity_name, "attack",
                    "--slices", attack_slices,
                    "--fps", "12",
                    "--no-loop",
                    project=str(project_path)
                )

                if result["success"]:
                    print(f"✓ Animation state 'attack' created with {len(slices[4:6])} frames (non-looping)")
                else:
                    print(f"⚠️  Could not create attack state: {result.get('message')}")
        else:
            print(f"⚠️  Not enough slices for animation (need 4, have {len(slices)})")
            print("   Run: python examples/ai_workflows/02_slice_spritesheet.py")
    else:
        print("⚠️  No sprite assets found")
        print("   Add a PNG to assets/ folder first")
    
    # Step 8: Verify animator setup
    print(f"\n🔍 Verifying animator setup...")
    result = run_command("animator", "info", entity_name, project=str(project_path))
    
    if result["success"] and result["data"].get("exists"):
        info = result["data"]
        print(f"✓ Animator configured:")
        print(f"   - Sprite sheet: {info.get('sprite_sheet', 'none')}")
        print(f"   - States: {len(info.get('states', []))}")
        print(f"   - Default state: {info.get('default_state', 'none')}")
        for state in info.get("states", []):
            loop_status = "loop" if state.get('loop', True) else "one-shot"
            print(f"     - {state['name']}: {state['frame_count']} frames @ {state['fps']} FPS ({loop_status})")
    else:
        print(f"⚠️  Animator not fully configured")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ Workflow complete!")
    print(f"\nCreated:")
    print(f"  - Scene: {scene_name}")
    print(f"  - Entity: {entity_name}")
    print(f"  - Components: Transform, Sprite, Animator")
    print(f"\nOfficial Animator Commands Used:")
    print(f"  motor animator ensure <entity> [--sheet <asset>]  # Ensure exists, set sheet if provided")
    print(f"  motor animator set-sheet <entity> <asset>         # Set/update sprite sheet")
    print(f"  motor animator state create <entity> <state> --slices <names> [--loop|--no-loop]")
    print(f"  motor animator state remove <entity> <state>      # Remove animation state")
    print(f"  motor animator info <entity>                      # Get animator info")
    print(f"\nGrammar: motor <noun> [<subnoun>] <verb> [<args>] [options]")
    print(f"\nEnsure Semantics:")
    print(f"  --sheet <asset> : Guarantees Animator exists AND has this sheet")
    print(f"                    (creates if missing, updates sheet if different)")
    print(f"\nLoop/No-Loop Semantics:")
    print(f"  --loop    : Animation repeats indefinitely (default)")
    print(f"  --no-loop : Animation plays once and stops")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
