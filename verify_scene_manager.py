import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from engine.scenes.scene_manager import SceneManager
from engine.levels.component_registry import create_default_registry
from engine.components.transform import Transform

def verify_scene_manager():
    print("=== START SCENE MANAGER VERIFICATION ===")
    
    registry = create_default_registry()
    manager = SceneManager(registry)
    
    # 1. Create New Scene
    print("[TEST] create_new_scene...")
    world = manager.create_new_scene("TestSceneManager")
    if not world:
        print("[FAIL] World not created")
        return False
    if manager.scene_name != "TestSceneManager":
        print(f"[FAIL] Scene name mismatch: {manager.scene_name}")
        return False
    print("[PASS] New Scene created")
    
    # 2. Add Entity
    entity = world.create_entity("PersistentEntity")
    entity.add_component(Transform(50, 50))
    print("[TEST] Entity added")
    
    # 3. Save Scene
    path = "verify_scene_manager.json"
    print(f"[TEST] save_scene_to_file({path})...")
    if not manager.save_scene_to_file(path):
        print("[FAIL] Save returned False")
        return False
        
    if not os.path.exists(path):
        print("[FAIL] File not created")
        return False
    print("[PASS] Scene saved")
    
    # 4. Load Scene
    print(f"[TEST] load_scene_from_file({path})...")
    loaded_world = manager.load_scene_from_file(path)
    if not loaded_world:
        print("[FAIL] Load returned None")
        return False
        
    loaded_entity = loaded_world.get_entity_by_name("PersistentEntity")
    if not loaded_entity:
        print("[FAIL] Entity not found in loaded world")
        return False
        
    # Verify Transform
    t = loaded_entity.get_component(Transform)
    if not t or t.x != 50:
        print(f"[FAIL] Transform mismatch: {t.x if t else 'None'}")
        return False
        
    print("[PASS] Scene loaded and verified")
    
    # Cleanup
    try:
        os.remove(path)
        print("[INFO] Cleanup successful")
    except:
        pass
        
    print("=== SCENE MANAGER VERIFICATION SUCCESSFUL ===")
    return True

if __name__ == "__main__":
    if verify_scene_manager():
        sys.exit(0)
    else:
        sys.exit(1)
