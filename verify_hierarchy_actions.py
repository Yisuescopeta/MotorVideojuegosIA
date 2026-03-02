import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from engine.ecs.world import World
from engine.editor.hierarchy_panel import HierarchyPanel
from engine.levels.component_registry import create_default_registry

def verify_hierarchy_actions():
    print("=== START HIERARCHY ACTIONS VERIFICATION ===")
    
    world = World()
    panel = HierarchyPanel()
    
    # 1. Test Create Entity
    print("[TEST] Create Entity Action...")
    initial_count = world.entity_count()
    panel._execute_context_action(world, "Create Entity")
    
    if world.entity_count() != initial_count + 1:
        print(f"[FAIL] Entity count mismatch: {world.entity_count()} != {initial_count + 1}")
        return False
        
    created_ent = world.get_all_entities()[0]
    print(f"[PASS] Entity '{created_ent.name}' created")
    
    # 2. Test Delete Entity
    print("[TEST] Delete Entity Action...")
    # Mock selection
    panel.context_target_id = created_ent.id
    panel._execute_context_action(world, "Delete Entity")
    
    if world.entity_count() != initial_count:
        print(f"[FAIL] Entity count mismatch after delete: {world.entity_count()} != {initial_count}")
        return False
        
    print("[PASS] Entity deleted")
    
    # 3. Test Delete Non-Existent (Safety)
    print("[TEST] Delete Invalid Entity...")
    panel.context_target_id = 99999
    try:
        panel._execute_context_action(world, "Delete Entity")
        print("[PASS] Handled invalid delete gracefully")
    except Exception as e:
        print(f"[FAIL] Crashed on invalid delete: {e}")
        return False
        
    print("=== HIERARCHY ACTIONS VERIFICATION SUCCESSFUL ===")
    return True

if __name__ == "__main__":
    if verify_hierarchy_actions():
        sys.exit(0)
    else:
        sys.exit(1)
