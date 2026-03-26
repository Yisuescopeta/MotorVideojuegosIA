"""
tests/test_api_usage.py - Demostración de uso de la API Formal

PROPÓSITO:
    Verificar que una "IA" (agente externo) puede controlar el motor
    usando exclusivamente la clase EngineAPI, sin tocar internals.
"""

import sys
import os

# Añadir root al path para importar engine
sys.path.append(os.getcwd())

from engine.api import EngineAPI, InvalidOperationError

def main():
    print("=== INICIANDO PRUEBA DE API FORMAL ===")
    
    # 1. Inicialización
    try:
        api = EngineAPI()
        print("[OK] EngineAPI inicializada")
    except Exception as e:
        print(f"[FAIL] Error inicializando API: {e}")
        return

    # 2. Carga de Nivel
    level_path = "levels/demo_level.json"
    try:
        api.load_level(level_path)
        print(f"[OK] Nivel cargado: {level_path}")
    except Exception as e:
        print(f"[FAIL] Error cargando nivel: {e}")
        return

    # 3. Inspección (Lectura)
    try:
        status = api.get_status()
        print(f"[INFO] Estado inicial: {status}")
        
        entity = api.get_entity("Ground")
        ground_x = entity["components"]["Transform"]["x"]
        print(f"[OK] Ground encontrado en X={ground_x}")
    except Exception as e:
        print(f"[FAIL] Error en inspección: {e}")
        return

    # 4. Edición (Escritura) - Modo EDIT
    try:
        print("[INFO] Intentando editar Ground.Transform.x a 600.0...")
        result = api.edit_component("Ground", "Transform", "x", 600.0)
        
        if result["success"]:
            # Verificar cambio
            entity = api.get_entity("Ground")
            new_x = entity["components"]["Transform"]["x"]
            if new_x == 600.0:
                print(f"[OK] Edición exitosa y verificada. Nuevo X={new_x}")
            else:
                print(f"[FAIL] La edición reportó éxito pero el valor es {new_x}")
        else:
            print(f"[FAIL] La edición falló: {result['message']}")
            
    except Exception as e:
        print(f"[FAIL] Excepción editando: {e}")

    # 4b. Authoring compartido de metadatos y Camera2D
    try:
        print("[INFO] Creando Camera2D serializable...")
        camera_result = api.create_camera2d(
            "MainCamera",
            transform={"x": 320.0, "y": 180.0},
            camera={"offset_x": 320.0, "offset_y": 180.0, "zoom": 1.5, "follow_entity": "Player", "framing_mode": "platformer"},
        )
        if not camera_result["success"]:
            print(f"[FAIL] No se pudo crear Camera2D: {camera_result['message']}")
        else:
            api.set_camera_framing("MainCamera", {"clamp_left": 0.0, "clamp_right": 1024.0, "recenter_on_play": True})
            api.set_entity_tag("MainCamera", "MainCamera")
            api.set_entity_layer("MainCamera", "Gameplay")
            filtered = api.list_entities(tag="MainCamera", layer="Gameplay", active=True)
            primary_camera = api.get_primary_camera()
            print(f"[OK] Filtro tag/layer encontró {len(filtered)} entidad(es)")
            print(f"[OK] Cámara primaria: {primary_camera['name'] if primary_camera else 'ninguna'}")
    except Exception as e:
        print(f"[FAIL] Error creando o consultando Camera2D: {e}")

    try:
        print("[INFO] Creando InputMap y AudioSource serializables...")
        api.create_input_map("PlayerInput", {"move_left": "J", "move_right": "L", "action_1": "SPACE"})
        api.create_audio_source("MusicPlayer", audio={"asset_path": "assets/theme.wav", "play_on_awake": False})
        api.update_audio_source("MusicPlayer", {"loop": True, "volume": 0.25})
        audio_state = api.get_audio_state("MusicPlayer")
        input_state = api.get_input_state("PlayerInput")
        print(f"[OK] AudioSource editable: loop={audio_state.get('loop')} volume={audio_state.get('volume')}")
        print(f"[OK] InputMap expone estado serializable: {input_state}")
    except Exception as e:
        print(f"[FAIL] Error con InputMap o AudioSource: {e}")

    try:
        print("[INFO] Añadiendo ScriptBehaviour serializable...")
        api.create_entity("AgentDrivenActor")
        api.add_script_behaviour("AgentDrivenActor", "platformer_character", {"health": 3, "coins": 0})
        script_data = api.get_script_public_data("AgentDrivenActor")
        print(f"[OK] ScriptBehaviour visible por API: {script_data}")
    except Exception as e:
        print(f"[FAIL] Error creando ScriptBehaviour: {e}")

    # 5. Control de Ejecución (Play/Step)
    try:
        print("[INFO] Iniciando simulación (PLAY)...")
        api.play()
        
        # Intentar editar en PLAY (debería fallar)
        try:
            api.edit_component("Ground", "Transform", "x", 700.0)
            print("[FAIL] Se permitió editar en modo PLAY (debería estar bloqueado)")
        except InvalidOperationError:
            print("[OK] Bloqueo de edición en PLAY verificado correctamente")
            
        # Avanzar 10 frames
        print("[INFO] Avanzando 10 frames...")
        api.step(10)
        
        status = api.get_status()
        print(f"[OK] Simulación avanzada. Tiempo: {status['time']:.4f}s")
        
    except Exception as e:
        print(f"[FAIL] Error en ejecución: {e}")

    print("=== PRUEBA FINALIZADA ===")
    api.shutdown()

if __name__ == "__main__":
    main()
