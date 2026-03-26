import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from engine.ecs.world import World
from engine.scenes.scene import Scene
from engine.levels.component_registry import create_default_registry
from engine.components.transform import Transform
from engine.components.sprite import Sprite
from engine.components.collider import Collider
from engine.components.animator import Animator, AnimationData

def verify_serialization():
    print("=== START SERIALIZATION VERIFICATION ===")
    
    # 1. Setup Registry
    registry = create_default_registry()
    print("[OK] Registry created")

    # 2. Create Initial World
    world = World()
    entity = world.create_entity("TestPlayer")
    
    # Add Components with specific values
    t = Transform(x=100.5, y=200.0, rotation=45.0, scale_x=2.0)
    entity.add_component(t)
    
    s = Sprite(texture_path="assets/player.png", width=64, height=64, flip_x=True)
    entity.add_component(s)
    
    c = Collider(width=50, height=100, is_trigger=True)
    entity.add_component(c)
    
    anim_data = AnimationData(frames=[0, 1, 2], fps=10, loop=True)
    a = Animator(sprite_sheet="assets/sheet.png", animations={"run": anim_data}, default_state="run")
    entity.add_component(a)
    
    print(f"[OK] Entity created with {len(entity.get_all_components())} components")

    # 3. Serialize World -> Dict
    data = world.serialize()
    # Mock Scene wrapping (Scene adds "entities" key)
    scene_data = {
        "name": "TestScene",
        "entities": data["entities"],
        "rules": data["rules"]
    }
    
    print("[OK] World serialized")
    
    # 4. Create Scene from Dict
    scene = Scene.from_dict(scene_data)
    print(f"[OK] Scene created: {scene}")

    # 5. Create New World from Scene
    new_world = scene.create_world(registry)
    print("[OK] New World created from Scene")
    
    # 6. Verify Data Integrity
    new_entity = new_world.get_entity_by_name("TestPlayer")
    if not new_entity:
        print("[FAIL] Entity 'TestPlayer' not found in new world")
        return False
        
    # Verify Transform
    nt = new_entity.get_component(Transform)
    if not nt:
        print("[FAIL] Transform missing")
        return False
    
    if abs(nt.x - 100.5) > 0.001 or abs(nt.scale_x - 2.0) > 0.001:
        print(f"[FAIL] Transform mismatch: x={nt.x}, scale_x={nt.scale_x}")
        return False
    print("[PASS] Transform verified")

    # Verify Sprite
    ns = new_entity.get_component(Sprite)
    if not ns:
        print("[FAIL] Sprite missing")
        return False
        
    if ns.texture_path != "assets/player.png" or not ns.flip_x:
        print(f"[FAIL] Sprite mismatch: path={ns.texture_path}, flip_x={ns.flip_x}")
        return False
    print("[PASS] Sprite verified")
    
    # Verify Animator
    na = new_entity.get_component(Animator)
    if not na:
        print("[FAIL] Animator missing")
        return False
    
    if "run" not in na.animations:
        print("[FAIL] Animation 'run' missing")
        return False
        
    if na.animations["run"].fps != 10:
        print(f"[FAIL] Animation FPS mismatch: {na.animations['run'].fps}")
        return False
    print("[PASS] Animator verified")

    print("=== SERIALIZATION VERIFICATION SUCCESSFUL ===")
    return True

if __name__ == "__main__":
    if verify_serialization():
        sys.exit(0)
    else:
        sys.exit(1)
