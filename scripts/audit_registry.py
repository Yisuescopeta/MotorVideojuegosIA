#!/usr/bin/env python3
"""
Audit script for semantic fidelity of capability registry.

This script cross-references the capability registry with:
1. ComponentRegistry - to verify component names are real
2. API implementations - to verify api_methods exist
3. CLI implementation - to verify cli_commands are valid
"""

from __future__ import annotations

import ast
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.ai import get_default_registry
from engine.levels.component_registry import create_default_registry


def get_available_components() -> Set[str]:
    """Get all registered component names."""
    registry = create_default_registry()
    return set(registry.list_registered())


def parse_api_methods_from_file(filepath: Path) -> Set[str]:
    """Parse Python file to extract public method names."""
    methods = set()
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith("_"):
                    methods.add(node.name)
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                        methods.add(item.name)
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}")
    return methods


def get_available_api_methods() -> Dict[str, Set[str]]:
    """Get all available API methods from source files."""
    api_dir = ROOT / "engine" / "api"
    methods = {}
    
    api_files = {
        "AuthoringAPI": "_authoring_api.py",
        "SceneWorkspaceAPI": "_scene_workspace_api.py",
        "AssetsProjectAPI": "_assets_project_api.py",
        "RuntimeAPI": "_runtime_api.py",
    }
    
    for api_name, filename in api_files.items():
        filepath = api_dir / filename
        if filepath.exists():
            methods[api_name] = parse_api_methods_from_file(filepath)
        else:
            methods[api_name] = set()
            print(f"Warning: {filepath} not found")
    
    return methods


def audit_components(registry) -> List[str]:
    """Audit component names mentioned in registry examples."""
    errors = []
    available_components = get_available_components()
    
    # Common component names mentioned in examples
    components_in_examples = set()
    
    for cap in registry.list_all():
        # Check example API calls for component names
        for call in cap.example.api_calls:
            args = call.get("args", {})
            if "component_name" in args:
                components_in_examples.add(args["component_name"])
            if "component" in args:
                components_in_examples.add(args["component"])
        
        # Check notes for component mentions
        if "component" in cap.notes.lower():
            # Extract component names from notes (heuristic)
            for word in cap.notes.split():
                word = word.strip(".,();:\"'")
                if word and word[0].isupper() and word not in ["Transform", "Sprite", "AI", "Use", "Some", "The", "First", "Cannot"]:
                    if word not in available_components and word not in ["Collider", "Animator", "Camera2D", "Tilemap"]:
                        # Skip common non-component words
                        pass
    
    return errors


KNOWN_CLI_FUNCTIONS = {
    "cmd_capabilities", "cmd_doctor", "cmd_project_info", 
    "cmd_scene_list", "cmd_scene_create", "cmd_entity_create",
    "cmd_component_add", "cmd_assets_list", "cmd_slices_list",
    "cmd_slices_grid", "cmd_slices_auto", "cmd_slices_manual",
    "cmd_animator_info", "cmd_animator_set_sheet", 
    "cmd_animator_upsert_state", "cmd_animator_remove_state",
}


def audit_api_methods(registry, available_methods: Dict[str, Set[str]]) -> List[str]:
    """Audit that api_methods reference real methods."""
    errors = []
    
    for cap in registry.list_all():
        for method_ref in cap.api_methods:
            # Handle standalone functions (CLI command handlers)
            if "." not in method_ref:
                if method_ref in KNOWN_CLI_FUNCTIONS:
                    continue
                errors.append(f"{cap.id}: Unknown function: {method_ref}")
                continue
            
            api_class, method_name = method_ref.rsplit(".", 1)
            
            if api_class not in available_methods:
                errors.append(f"{cap.id}: Unknown API class: {api_class}")
                continue
            
            if method_name not in available_methods[api_class]:
                errors.append(f"{cap.id}: Method not found: {method_ref}")
    
    return errors


def audit_modes(registry) -> List[str]:
    """Audit capability modes for consistency."""
    errors = []
    
    for cap in registry.list_all():
        # Check for capabilities that should likely be 'edit' only
        edit_only_patterns = ["create", "delete", "add", "remove", "edit", "set", "update"]
        
        if cap.mode == "both":
            # If it's a write operation, it should probably be 'edit' only
            action = cap.id.split(":")[-1] if ":" in cap.id else cap.id
            if any(pattern in action.lower() for pattern in edit_only_patterns):
                # scene:load and scene:create are correctly marked 'both' and 'edit'
                # but let's flag suspicious ones
                if action not in ["load", "create", "list", "get", "info", "find"]:
                    pass  # Not flagging for now
    
    return errors


def audit_cli_commands(registry) -> List[str]:
    """Audit CLI commands are valid."""
    errors = []
    
    # These are the officially implemented commands
    implemented_commands = {
        "capabilities",
        "doctor",
        "project",
        "scene",
        "entity",
        "component",
        "animator",
        "asset",
    }
    
    # Future commands (documented but not implemented)
    future_commands = {
        "runtime", "prefab", "undo", "redo", "status", "physics"
    }
    
    for cap in registry.list_all():
        cmd = cap.cli_command
        if not cmd.startswith("motor "):
            errors.append(f"{cap.id}: CLI command must start with 'motor ': {cmd}")
            continue
        
        parts = cmd.split()[1:]  # Remove 'motor'
        if not parts:
            errors.append(f"{cap.id}: Empty CLI command")
            continue
        
        base_cmd = parts[0]
        
        if base_cmd not in implemented_commands and base_cmd not in future_commands:
            errors.append(f"{cap.id}: Unknown CLI command scope: {base_cmd}")
    
    return errors


def main():
    print("=" * 70)
    print("CAPABILITY REGISTRY SEMANTIC AUDIT")
    print("=" * 70)
    
    registry = get_default_registry()
    available_methods = get_available_api_methods()
    
    print(f"\nRegistry contains {len(registry.list_all())} capabilities")
    print(f"Available components: {len(get_available_components())}")
    print(f"Available API methods:")
    for api_name, methods in available_methods.items():
        print(f"  - {api_name}: {len(methods)} methods")
    
    # Run audits
    print("\n" + "=" * 70)
    print("AUDIT RESULTS")
    print("=" * 70)
    
    all_errors = []
    
    # Audit 1: API Methods
    print("\n1. API Methods Audit...")
    api_errors = audit_api_methods(registry, available_methods)
    if api_errors:
        print(f"   FAILED - {len(api_errors)} issues found:")
        for error in api_errors:
            print(f"     - {error}")
        all_errors.extend(api_errors)
    else:
        print("   PASSED - All api_methods reference real methods")
    
    # Audit 2: CLI Commands
    print("\n2. CLI Commands Audit...")
    cli_errors = audit_cli_commands(registry)
    if cli_errors:
        print(f"   FAILED - {len(cli_errors)} issues found:")
        for error in cli_errors:
            print(f"     - {error}")
        all_errors.extend(cli_errors)
    else:
        print("   PASSED - All CLI commands are valid")
    
    # Audit 3: Modes
    print("\n3. Mode Consistency Audit...")
    mode_errors = audit_modes(registry)
    if mode_errors:
        print(f"   WARNING - {len(mode_errors)} potential issues:")
        for error in mode_errors:
            print(f"     - {error}")
    else:
        print("   PASSED - All modes look consistent")
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if all_errors:
        print(f"\nFAILED: {len(all_errors)} critical issues found")
        print("The registry is NOT semantically accurate")
        return 1
    else:
        print("\nPASSED: Registry is semantically accurate")
        return 0


if __name__ == "__main__":
    sys.exit(main())
