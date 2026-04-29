import sys
import os
import math

# Add project root to path
sys.path.append(os.getcwd())

import pyray as rl
from engine.ecs.world import World
from engine.components.transform import Transform
from engine.editor.gizmo_system import GizmoSystem, GizmoMode

def verify_gizmo_logic():
    print("=== START GIZMO LOGIC VERIFICATION ===")
    
    world = World()
    entity = world.create_entity("TestEntity")
    transform = Transform(100, 100)
    entity.add_component(transform)
    world.selected_entity_name = entity.name
    
    gizmo = GizmoSystem()
    
    # 1. Test Rotate Hover
    print("[TEST] Rotate Hover...")
    # Mouse at 140, 100 (Radius 40 from 100, 100)
    mouse_pos = rl.Vector2(140, 100)
    gizmo.update(world, mouse_pos, "Rotate")
    
    if gizmo.hover_mode == GizmoMode.ROTATE_Z:
        print("[PASS] Hover detected ROTATE_Z")
    else:
        print(f"[FAIL] Hover mode is {gizmo.hover_mode}, expected ROTATE_Z")
        return False
        
    # 2. Test Rotate Drag
    print("[TEST] Rotate Drag...")
    # Start drag at 0 degrees (140, 100)
    # Simulate Mouse Pressed
    # GizmoSystem checks is_mouse_button_pressed internally. 
    # We can hack it by calling _start_drag manually or mocking raylib.
    # Since we can't easy mock raylib C functions, we call private methods logic.
    
    gizmo._start_drag(transform, 140, 100, GizmoMode.ROTATE_Z)
    
    # Move to 90 degrees (100, 140) (Y grows down? In Raylib +Y is down. So 100, 140 is below. 
    # Angle of 0, 1 is 90 deg? atan2(y, x). atan2(1, 0) = PI/2 = 90 deg.
    # So (100, 140) relative to (100, 100) is (0, 40). atan2(40, 0) = 90.
    
    gizmo._handle_drag(transform, 100, 140)
    
    # Expected Rotation: 0 + 90 = 90
    print(f"Rotation: {transform.rotation}")
    if abs(transform.rotation - 90.0) < 1.0:
        print("[PASS] Rotation updated correctly")
    else:
        print(f"[FAIL] Rotation {transform.rotation} != 90")
        return False
        
    gizmo._end_drag()
    
    # 3. Test Scale Hover (X Axis)
    print("[TEST] Scale Hover X...")
    # Axis Length is 50. Handle is at 50..58?
    # Logic: if (ox + self.AXIS_LENGTH <= mx <= ox + self.AXIS_LENGTH + 8) ...
    # 100 + 50 = 150. Handle at 150..158.
    mouse_pos = rl.Vector2(154, 100) # Center of handle
    gizmo.update(world, mouse_pos, "Scale")
    
    if gizmo.hover_mode == GizmoMode.SCALE_X:
        print("[PASS] Hover detected SCALE_X")
    else:
        print(f"[FAIL] Hover mode is {gizmo.hover_mode}, expected SCALE_X")
        return False
        
    # 4. Test Scale Drag
    print("[TEST] Scale Drag X...")
    gizmo._start_drag(transform, 154, 100, GizmoMode.SCALE_X)
    
    # Drag +50 pixels right
    # Logic: scale_delta = dx * 0.02. 
    # dx = 50. delta = 1.0. 
    # Initial scale 1.0. New scale 2.0.
    
    gizmo._handle_drag(transform, 204, 100)
    
    print(f"Scale X: {transform.scale_x}")
    if abs(transform.scale_x - 2.0) < 0.1:
        print("[PASS] Scale X updated correctly")
    else:
        print(f"[FAIL] Scale X {transform.scale_x} != 2.0")
        return False
        
    print("=== GIZMO LOGIC VERIFICATION SUCCESSFUL ===")
    return True

if __name__ == "__main__":
    if verify_gizmo_logic():
        sys.exit(0)
    else:
        sys.exit(1)
