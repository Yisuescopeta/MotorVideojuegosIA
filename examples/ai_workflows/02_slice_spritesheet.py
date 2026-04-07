#!/usr/bin/env python3
"""
Example 02: Slice a Sprite Sheet (Official Motor CLI Interface)

Demonstrates grid-based slicing for animation frames using the official
`motor` CLI interface. This example assumes you have a sprite sheet 
image in assets/.
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


def run_motor(*args, project="."):
    """Run a motor CLI command and return parsed JSON."""
    cmd = ["motor"] + list(args) + ["--json", "--project", str(project)]
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
    print("Example 02: Slice a Sprite Sheet")
    print("=" * 60)
    
    project_path = Path(".")
    
    # Step 1: Check project health
    print("\n🔍 Checking project health...")
    result = run_motor("doctor", project=str(project_path))
    
    if not result.get("data", {}).get("healthy"):
        print(f"⚠️  Project issues: {result.get('data', {}).get('issues', [])}")
        recommendations = result.get("data", {}).get("recommendations", [])
        if recommendations:
            print("   Recommendations:")
            for rec in recommendations:
                print(f"     - {rec}")
    
    # Step 2: List available assets
    print("\n📁 Listing assets...")
    result = run_motor("asset", "list", project=str(project_path))
    
    if not result["success"]:
        print(f"❌ Failed to list assets: {result.get('message')}")
        return 1
    
    assets = result["data"]["assets"]
    images = [a for a in assets if a["path"].lower().endswith((".png", ".jpg"))]
    
    if not images:
        print("\n⚠️  No image assets found.")
        print("   Please add a sprite sheet to the assets/ folder first.")
        return 1
    
    print(f"\n✓ Found {len(images)} image(s):")
    for img in images[:5]:
        print(f"    - {img['path']}")
    
    # Use the first image as example
    target_asset = images[0]["path"]
    print(f"\n🎯 Using asset: {target_asset}")
    
    # Step 3: Check if already sliced
    print("\n📐 Checking existing slices...")
    result = run_motor("asset", "slice", "list", target_asset, project=str(project_path))
    
    if result["success"] and result["data"]["count"] > 0:
        print(f"✓ Asset already has {result['data']['count']} slices")
        print("\n   Existing slices:")
        for s in result["data"]["slices"][:5]:
            print(f"     - {s['name']}: {s['width']}x{s['height']} at ({s['x']},{s['y']})")
    else:
        print("   No slices found. Creating grid slices...")
        
        # Step 4: Create grid slices (assuming 32x32 cells)
        print("\n✂️  Creating grid slices (32x32 cells)...")
        result = run_motor(
            "asset", "slice", "grid", target_asset,
            "--cell-width", "32",
            "--cell-height", "32",
            "--margin", "0",
            "--spacing", "0",
            project=str(project_path)
        )
        
        if result["success"]:
            print(f"✓ Created {result['data']['slices_count']} slices")
            print("\n   Created slices:")
            for s in result["data"]["slices"][:5]:
                print(f"     - {s['name']}: {s['width']}x{s['height']} at ({s['x']},{s['y']})")
            if result["data"]["slices_count"] > 5:
                print(f"     ... and {result['data']['slices_count'] - 5} more")
        else:
            print(f"❌ Failed to create slices: {result.get('message')}")
            return 1
    
    # Step 5: Show next steps
    print("\n" + "=" * 60)
    print("✅ Slicing complete!")
    print("\nNext steps:")
    print("  1. Use these slices to create animation states:")
    print(f"     motor animator state create Player idle --slices slice_0,slice_1,slice_2,slice_3 --project .")
    print("  2. Try: python examples/ai_workflows/03_create_animated_entity.py")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
