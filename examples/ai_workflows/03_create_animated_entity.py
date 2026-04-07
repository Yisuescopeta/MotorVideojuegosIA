#!/usr/bin/env python3
"""
Example 03: Create Animated Entity

Full workflow demonstrating:
1. Create a scene
2. Create an entity
3. Add components
4. Configure animator with states
"""

import json
import subprocess
import sys
from pathlib import Path


def run_command(*args, project="."):
    """Run a motor CLI command and return parsed JSON."""
    cmd = [sys.executable, "-m", "tools.engine_cli"] + list(args) + ["--project", project, "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)


def main():
    print("=" * 60)
    print("Example 03: Create Animated Entity")
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
    
    # Step 4: Add Transform component
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
    
    # Step 5: Add SpriteRenderer component
    print("\n🎨 Adding SpriteRenderer component...")
    renderer_data = json.dumps({"enabled": True, "tint": "#FFFFFF"})
    result = run_command(
        "component", "add", entity_name, "SpriteRenderer",
        "--data", renderer_data,
        project=str(project_path)
    )
    
    if not result["success"]:
        print(f"⚠️  Could not add SpriteRenderer: {result.get('message')}")
    else:
        print(f"✓ SpriteRenderer added")
    
    # Step 6: Add Animator component
    print("\n🎭 Adding Animator component...")
    animator_data = json.dumps({"enabled": True, "speed": 1.0})
    result = run_command(
        "component", "add", entity_name, "Animator",
        "--data", animator_data,
        project=str(project_path)
    )
    
    if not result["success"]:
        print(f"⚠️  Could not add Animator: {result.get('message')}")
    else:
        print(f"✓ Animator added")
    
    # Step 7: Check for available sprites
    print("\n🔍 Looking for sprite assets...")
    result = run_command("assets", "list", project=str(project_path))
    images = [a for a in result["data"]["assets"] if a["path"].lower().endswith(".png")]
    
    if images:
        sprite_asset = images[0]["path"]
        print(f"✓ Found sprite asset: {sprite_asset}")
        
        # Set sprite sheet
        print(f"\n📄 Setting sprite sheet...")
        result = run_command(
            "animator", "set-sheet", entity_name, sprite_asset,
            project=str(project_path)
        )
        
        if result["success"]:
            print(f"✓ Sprite sheet configured")
            
            # Check for slices
            result = run_command("assets", "slices", "list", sprite_asset, project=str(project_path))
            slices = result["data"]["slices"]
            
            if len(slices) >= 4:
                # Create animation state
                slice_names = ",".join([s["name"] for s in slices[:4]])
                print(f"\n🎬 Creating 'idle' animation state...")
                result = run_command(
                    "animator", "upsert-state", entity_name, "idle",
                    "--slices", slice_names,
                    "--fps", "8",
                    "--loop",
                    "--set-default",
                    project=str(project_path)
                )
                
                if result["success"]:
                    print(f"✓ Animation state 'idle' created with {len(slices[:4])} frames")
                else:
                    print(f"⚠️  Could not create state: {result.get('message')}")
            else:
                print(f"⚠️  Not enough slices for animation (need 4, have {len(slices)})")
                print("   Run: python examples/ai_workflows/02_slice_spritesheet.py")
        else:
            print(f"⚠️  Could not set sprite sheet: {result.get('message')}")
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
            print(f"     - {state['name']}: {state['frame_count']} frames @ {state['fps']} FPS")
    else:
        print(f"⚠️  Animator not fully configured")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ Workflow complete!")
    print(f"\nCreated:")
    print(f"  - Scene: {scene_name}")
    print(f"  - Entity: {entity_name}")
    print(f"  - Components: Transform, SpriteRenderer, Animator")
    print(f"\nNext steps:")
    print(f"  1. Open scene: motor scene load {scene_path}")
    print(f"  2. Add more animation states")
    print(f"  3. Save the scene")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())