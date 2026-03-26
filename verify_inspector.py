from engine.inspector.inspector_system import InspectorSystem
from engine.ecs.world import World
from engine.components.transform import Transform

print("Testing Inspector Commit...")

# Setup
world = World()
entity = world.create_entity("TestEntity")
entity.add_component(Transform(0, 0))
inspector = InspectorSystem()

# Simulate Input
# Prop ID: {entity_id}:Transform:x
prop_id = f"{entity.id}:Transform:x"
inspector.editing_text_field = prop_id

# Set Buffer manually (as if user typed)
test_val_str = "99.0"
encoded = test_val_str.encode("utf-8")
inspector.text_buffer[:] = b'\x00' * len(inspector.text_buffer)
inspector.text_buffer[0:len(encoded)] = encoded

# Commit
inspector._commit_text_edit(world)

# Verify
comp = entity.get_component(Transform)
print(f"Transform.x = {comp.x} (Expected 99.0)")

if comp.x == 99.0:
    print("SUCCESS: Value updated correctly.")
else:
    print("FAILURE: Value did not update.")
    exit(1)
