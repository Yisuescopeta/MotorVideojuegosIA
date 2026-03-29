"""
tools/create_mechanic.py - Herramienta IA para crear mecÃ¡nicas de juego

PROPÃ“SITO:
    Permite a la IA crear automÃ¡ticamente nuevos Systems en el motor.
    La IA ejecuta esta herramienta cuando el usuario dice cosas como
    "AÃ±ade una mecÃ¡nica de doble salto" o "Crea un sistema de inventario".

FUNCIONALIDAD:
    - Genera un archivo de System con boilerplate ECS correcto
    - Lo registra en engine/systems/__init__.py
    - Genera cÃ³digo listo para ser conectado en main.py

EJEMPLO DE USO:
    from tools.create_mechanic import create_game_mechanic

    create_game_mechanic(
        name="double_jump",
        description="Permite al jugador saltar dos veces antes de tocar el suelo",
        required_components=["Transform", "RigidBody"]
    )
"""

import os
from typing import List, Optional


def create_game_mechanic(
    name: str,
    description: str = "Nuevo sistema de juego",
    required_components: Optional[List[str]] = None
) -> str:
    """
    Crea un nuevo System en el motor y genera el boilerplate necesario.

    Args:
        name: Nombre de la mecÃ¡nica (snake_case, ej: "double_jump")
        description: DescripciÃ³n de lo que hace el sistema
        required_components: Lista de componentes que necesita (ej: ["Transform", "RigidBody"])

    Returns:
        Ruta del archivo creado
    """
    if required_components is None:
        required_components = ["Transform"]

    # Nombre del archivo
    filename = f"{name.lower()}_sys.py"
    filepath = os.path.join("engine", "systems", filename)

    # Generar imports de componentes
    component_imports = []
    for comp in required_components:
        comp_lower = comp.lower()
        # Mapeo conocido de componentes a archivos
        comp_file_map = {
            "transform": "transform",
            "sprite": "sprite",
            "collider": "collider",
            "rigidbody": "rigidbody",
            "animator": "animator",
        }
        file_name = comp_file_map.get(comp_lower, comp_lower)
        component_imports.append(
            f"from engine.components.{file_name} import {comp}"
        )

    imports_str = "\n".join(component_imports)
    components_tuple = ", ".join(required_components)

    # Generar cÃ³digo del sistema
    class_name = "".join(word.capitalize() for word in name.split("_")) + "System"

    code = f'''"""
engine/systems/{filename} - Sistema de {name.replace('_', ' ')}

PROPÃ“SITO:
    {description}

DEPENDENCIAS:
    Componentes requeridos: {', '.join(required_components)}

EJEMPLO DE USO:
    {name}_system = {class_name}()
    {name}_system.update(world, delta_time)
"""

from engine.ecs.world import World
{imports_str}


class {class_name}:
    """
    {description}

    Procesa entidades que tengan: {', '.join(required_components)}
    """

    def __init__(self) -> None:
        """Inicializa el sistema."""
        pass

    def update(self, world: World, delta_time: float) -> None:
        """
        Actualiza la lÃ³gica del sistema.

        Args:
            world: Mundo con las entidades
            delta_time: Tiempo desde el Ãºltimo frame (segundos)
        """
        entities = world.get_entities_with({components_tuple})

        for entity in entities:
            # Obtener componentes
'''

    # AÃ±adir obtenciÃ³n de cada componente
    for comp in required_components:
        var_name = comp.lower()
        code += f"            {var_name} = entity.get_component({comp})\n"

    # Null check
    null_checks = " or ".join(f"{comp.lower()} is None" for comp in required_components)
    code += f"""
            if {null_checks}:
                continue

            # TODO: Implementar lÃ³gica de {name.replace('_', ' ')} aquÃ­
            pass
"""

    # Escribir archivo
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"[CREATE_MECHANIC] Sistema '{class_name}' creado en {filepath}")
    print("[CREATE_MECHANIC] Para usarlo, aÃ±ade en main.py:")
    print(f"    from engine.systems.{name.lower()}_sys import {class_name}")
    print(f"    {name}_system = {class_name}()")
    print(f"    game.set_{name}_system({name}_system)")

    return filepath


def list_existing_systems() -> List[str]:
    """
    Lista todos los sistemas existentes en engine/systems/.

    Returns:
        Lista de nombres de archivos de sistemas
    """
    systems_dir = os.path.join("engine", "systems")
    if not os.path.isdir(systems_dir):
        return []

    return [
        f for f in os.listdir(systems_dir)
        if f.endswith(".py") and not f.startswith("_")
    ]


if __name__ == "__main__":
    # Demo: crear un sistema de ejemplo
    import sys

    if len(sys.argv) > 1:
        name = sys.argv[1]
        desc = sys.argv[2] if len(sys.argv) > 2 else "Sistema generado por IA"
        comps = sys.argv[3].split(",") if len(sys.argv) > 3 else ["Transform"]
        create_game_mechanic(name, desc, comps)
    else:
        print("Uso: python tools/create_mechanic.py <nombre> [descripciÃ³n] [comp1,comp2,...]")
        print("Ejemplo: python tools/create_mechanic.py double_jump 'Doble salto' Transform,RigidBody")
        print()
        print("Sistemas existentes:")
        for s in list_existing_systems():
            print(f"  - {s}")
