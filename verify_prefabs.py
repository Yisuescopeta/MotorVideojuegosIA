import sys
import os
import shutil

# Add project root to path
sys.path.append(os.getcwd())

from engine.ecs.world import World
from engine.ecs.entity import Entity
from engine.components.transform import Transform
from engine.assets.prefab import PrefabManager

def verify_prefabs():
    print("=== START PREFAB VERIFICATION ===")
    
    # 1. Setup Source World
    world_src = World()
    entity = world_src.create_entity("Hero")
    t = Transform(10, 20)
    t.rotation = 45
    entity.add_component(t)
    
    prefab_path = os.path.abspath("test_assets/hero.prefab")
    
    # 2. Save Prefab
    print(f"[TEST] Saving prefab to {prefab_path}...")
    if not PrefabManager.save_prefab(entity, prefab_path):
        print("[FAIL] Failed to save prefab")
        return False
        
    if not os.path.exists(prefab_path):
        print("[FAIL] File not created")
        return False
        
    # 3. Instantiate in Target World (with override)
    print("[TEST] Instantiating Prefab...")
    world_dst = World()
    new_ent = PrefabManager.instantiate_prefab(prefab_path, world_dst, (100, 200))
    
    if not new_ent:
        print("[FAIL] Instantiate returned None")
        return False
        
    print(f"[INFO] Created Entity: {new_ent.name}")
    
    # 4. Verify Components
    t_new = new_ent.get_component(Transform)
    if not t_new:
        print("[FAIL] Transform missing")
        return False
        
    print(f"[INFO] Transform: x={t_new.x}, y={t_new.y}, rot={t_new.rotation}")
    
    # Check Position Override
    if abs(t_new.x - 100) > 0.1 or abs(t_new.y - 200) > 0.1:
        print(f"[FAIL] Position override failed. Expected (100, 200), got ({t_new.x}, {t_new.y})")
        return False
        
    # Check Rotation Persistence (Should be 45)
    if abs(t_new.rotation - 45) > 0.1:
        print(f"[FAIL] Rotation lost. Expected 45, got {t_new.rotation}")
        return False
        
    # 5. Verify Name Mapping
    # First one should be "Hero"
    if new_ent.name != "Hero":
         print(f"[FAIL] Name mismatch. Expected 'Hero', got '{new_ent.name}'")
         return False
         
    # Create Duplicate
    print("[TEST] Instantiating Duplicate...")
    dup_ent = PrefabManager.instantiate_prefab(prefab_path, world_dst, (0,0))
    print(f"[INFO] Duplicate Name: {dup_ent.name}")
    
    if dup_ent.name == "Hero":
        print("[FAIL] Duplicate name collision not handled. Got 'Hero' again.") 
        # Wait, PrefabManager handles this? 
        # Yes, using world.get_entity_by_name loop.
        return False
        
    if not dup_ent.name.startswith("Hero_"):
        print(f"[FAIL] Duplicate name format unexpected: {dup_ent.name}")
        return False

    # Cleanup
    try:
        shutil.rmtree("test_assets")
    except:
        pass
        
    print("=== PREFAB VERIFICATION SUCCESSFUL ===")
    return True

if __name__ == "__main__":
    if verify_prefabs():
        sys.exit(0)
    else:
        sys.exit(1)
