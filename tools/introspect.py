"""
tools/introspect.py - Herramienta de reflexiÃ³n para inspeccionar el motor

PROPÃ“SITO:
    Permite a la IA inspeccionar el estado del motor en tiempo de ejecuciÃ³n.
    Equivalente a una "consola de reflexiÃ³n" donde la IA puede ejecutar
    dir(objeto), ver atributos, y entender la estructura del juego.

FUNCIONALIDAD:
    - inspect_entity: Ver todos los componentes y atributos de una entidad
    - inspect_world: Resumen completo del mundo
    - list_systems: Listar sistemas disponibles
    - inspect_component: Ver la estructura de un tipo de componente

EJEMPLO DE USO:
    from tools.introspect import inspect_world, inspect_entity

    # Ver todo el mundo
    print(inspect_world(world))

    # Ver una entidad especÃ­fica
    print(inspect_entity(world, "Player"))
"""

import os
from typing import Any, Dict, List

from engine.ecs.world import World


def inspect_entity(world: World, entity_name: str) -> Dict[str, Any]:
    """
    Inspecciona una entidad y retorna todos sus datos.

    Args:
        world: El mundo que contiene la entidad
        entity_name: Nombre de la entidad a inspeccionar

    Returns:
        Diccionario con toda la informaciÃ³n de la entidad:
        {
            "name": "Player",
            "id": 0,
            "components": {
                "Transform": {"x": 100, "y": 200, ...},
                "RigidBody": {"velocity_x": 0, ...}
            }
        }
    """
    entity = world.get_entity_by_name(entity_name)
    if entity is None:
        return {"error": f"Entidad '{entity_name}' no encontrada"}

    components_data: Dict[str, Dict[str, Any]] = {}
    for component in entity.get_all_components():
        comp_name = type(component).__name__

        # Intentar serializaciÃ³n completa
        if hasattr(component, 'to_dict'):
            try:
                components_data[comp_name] = component.to_dict()
            except Exception as e:
                components_data[comp_name] = {"_error": str(e)}
        else:
            # Fallback: introspecciÃ³n de atributos
            attrs = {}
            for attr in dir(component):
                if attr.startswith("_"):
                    continue
                if callable(getattr(component, attr)):
                    continue
                try:
                    val = getattr(component, attr)
                    if isinstance(val, (int, float, str, bool, list, dict, type(None))):
                        attrs[attr] = val
                    else:
                        attrs[attr] = str(val)
                except Exception:
                    pass
            components_data[comp_name] = attrs

    return {
        "name": entity.name,
        "id": entity.id,
        "component_count": len(components_data),
        "components": components_data
    }


def inspect_world(world: World) -> Dict[str, Any]:
    """
    Inspecciona todo el mundo y retorna un resumen.

    Args:
        world: El mundo a inspeccionar

    Returns:
        Diccionario con resumen del mundo:
        {
            "entity_count": 5,
            "entities": ["Player", "Enemy", ...],
            "component_types": ["Transform", "Sprite", ...],
            "details": { ... por entidad ... }
        }
    """
    entities = world.get_all_entities()

    entity_names: List[str] = []
    component_types: set = set()
    details: Dict[str, Dict[str, Any]] = {}

    for entity in entities:
        entity_names.append(entity.name)

        entity_comps: Dict[str, Dict[str, Any]] = {}
        for component in entity.get_all_components():
            comp_name = type(component).__name__
            component_types.add(comp_name)

            if hasattr(component, 'to_dict'):
                try:
                    entity_comps[comp_name] = component.to_dict()
                except Exception:
                    entity_comps[comp_name] = {"_error": "serialization failed"}
            else:
                entity_comps[comp_name] = {"_type": comp_name}

        details[entity.name] = {
            "id": entity.id,
            "components": entity_comps
        }

    return {
        "entity_count": len(entities),
        "entities": entity_names,
        "component_types": sorted(component_types),
        "details": details
    }


def list_systems() -> List[Dict[str, str]]:
    """
    Lista todos los sistemas disponibles en engine/systems/.

    Returns:
        Lista de diccionarios con nombre y ruta de cada sistema
    """
    systems_dir = os.path.join("engine", "systems")
    result: List[Dict[str, str]] = []

    if not os.path.isdir(systems_dir):
        return result

    for filename in sorted(os.listdir(systems_dir)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        filepath = os.path.join(systems_dir, filename)
        system_name = filename[:-3]  # Quitar .py

        # Leer primera lÃ­nea de docstring si existe
        description = ""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read(500)
                if '"""' in content:
                    start = content.index('"""') + 3
                    end = content.index('"""', start)
                    doc = content[start:end].strip()
                    # Primera lÃ­nea del docstring
                    description = doc.split("\n")[0].strip()
        except Exception:
            description = "No description available"

        result.append({
            "name": system_name,
            "file": filepath,
            "description": description
        })

    return result


def inspect_component_type(component_class: type) -> Dict[str, Any]:
    """
    Inspecciona la estructura de un tipo de componente.

    Args:
        component_class: La clase del componente a inspeccionar

    Returns:
        Diccionario con la estructura del componente
    """
    try:
        instance = component_class()
    except Exception:
        return {"error": f"No se puede instanciar {component_class.__name__}"}

    attrs: Dict[str, str] = {}
    for attr in dir(instance):
        if attr.startswith("_"):
            continue
        if callable(getattr(instance, attr)):
            continue
        try:
            val = getattr(instance, attr)
            attrs[attr] = type(val).__name__
        except Exception:
            pass

    return {
        "name": component_class.__name__,
        "attributes": attrs,
        "has_to_dict": hasattr(component_class, "to_dict"),
        "has_from_dict": hasattr(component_class, "from_dict"),
    }


if __name__ == "__main__":
    # Demo: inspeccionar un mundo de ejemplo
    from engine.components.rigidbody import RigidBody
    from engine.components.transform import Transform

    world = World()

    player = world.create_entity("Player")
    player.add_component(Transform(x=100, y=200))
    player.add_component(RigidBody())

    enemy = world.create_entity("Enemy")
    enemy.add_component(Transform(x=300, y=200))

    import json

    print("=== WORLD INSPECTION ===")
    print(json.dumps(inspect_world(world), indent=2))

    print("\n=== ENTITY INSPECTION ===")
    print(json.dumps(inspect_entity(world, "Player"), indent=2))

    print("\n=== AVAILABLE SYSTEMS ===")
    for sys_info in list_systems():
        print(f"  - {sys_info['name']}: {sys_info['description']}")

    print("\n=== COMPONENT STRUCTURE ===")
    print(json.dumps(inspect_component_type(Transform), indent=2))
