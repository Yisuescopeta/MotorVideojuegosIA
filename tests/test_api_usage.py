"""
tests/test_api_usage.py - Demo de uso de la API formal.

PROPOSITO:
    Verificar que un agente externo puede controlar el motor usando
    exclusivamente la clase EngineAPI, sin tocar internals.
"""

import tempfile
from pathlib import Path

from engine.api import EngineAPI, InvalidOperationError


def main():
    print("=== INICIANDO PRUEBA DE API FORMAL ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Ejecutar la demo sobre una copia temporal evita mutar el workspace real.
        project_root = Path(temp_dir) / "project"
        project_root.mkdir(parents=True, exist_ok=True)
        source_level = Path(__file__).resolve().parents[1] / "levels" / "demo_level.json"
        target_level = project_root / "levels" / "demo_level.json"
        target_level.parent.mkdir(parents=True, exist_ok=True)
        target_level.write_text(source_level.read_text(encoding="utf-8"), encoding="utf-8")

        try:
            api = EngineAPI(project_root=project_root.as_posix())
            print("[OK] EngineAPI inicializada")
        except Exception as e:
            print(f"[FAIL] Error inicializando API: {e}")
            return

        try:
            level_path = "levels/demo_level.json"
            api.load_level(level_path)
            print(f"[OK] Nivel cargado: {level_path}")

            status = api.get_status()
            print(f"[INFO] Estado inicial: {status}")

            entity = api.get_entity("Ground")
            ground_x = entity["components"]["Transform"]["x"]
            print(f"[OK] Ground encontrado en X={ground_x}")

            print("[INFO] Intentando editar Ground.Transform.x a 600.0...")
            result = api.edit_component("Ground", "Transform", "x", 600.0)
            if result["success"]:
                entity = api.get_entity("Ground")
                new_x = entity["components"]["Transform"]["x"]
                if new_x == 600.0:
                    print(f"[OK] Edicion exitosa y verificada. Nuevo X={new_x}")
                else:
                    print(f"[FAIL] La edicion reporto exito pero el valor es {new_x}")
            else:
                print(f"[FAIL] La edicion fallo: {result['message']}")

            print("[INFO] Creando Camera2D serializable...")
            camera_result = api.create_camera2d(
                "MainCamera",
                transform={"x": 320.0, "y": 180.0},
                camera={
                    "offset_x": 320.0,
                    "offset_y": 180.0,
                    "zoom": 1.5,
                    "follow_entity": "Player",
                    "framing_mode": "platformer",
                },
            )
            if not camera_result["success"]:
                print(f"[FAIL] No se pudo crear Camera2D: {camera_result['message']}")
            else:
                api.set_camera_framing(
                    "MainCamera",
                    {"clamp_left": 0.0, "clamp_right": 1024.0, "recenter_on_play": True},
                )
                api.set_entity_tag("MainCamera", "MainCamera")
                api.set_entity_layer("MainCamera", "Gameplay")
                filtered = api.list_entities(tag="MainCamera", layer="Gameplay", active=True)
                primary_camera = api.get_primary_camera()
                print(f"[OK] Filtro tag/layer encontro {len(filtered)} entidad(es)")
                print(f"[OK] Camara primaria: {primary_camera['name'] if primary_camera else 'ninguna'}")

            print("[INFO] Creando InputMap y AudioSource serializables...")
            api.create_input_map("PlayerInput", {"move_left": "J", "move_right": "L", "action_1": "SPACE"})
            api.create_audio_source("MusicPlayer", audio={"asset_path": "assets/theme.wav", "play_on_awake": False})
            api.update_audio_source("MusicPlayer", {"loop": True, "volume": 0.25})
            audio_state = api.get_audio_state("MusicPlayer")
            input_state = api.get_input_state("PlayerInput")
            print(f"[OK] AudioSource editable: loop={audio_state.get('loop')} volume={audio_state.get('volume')}")
            print(f"[OK] InputMap expone estado serializable: {input_state}")

            print("[INFO] Anadiendo ScriptBehaviour serializable...")
            api.create_entity("AgentDrivenActor")
            api.add_script_behaviour("AgentDrivenActor", "platformer_character", {"health": 3, "coins": 0})
            script_data = api.get_script_public_data("AgentDrivenActor")
            print(f"[OK] ScriptBehaviour visible por API: {script_data}")

            print("[INFO] Iniciando simulacion (PLAY)...")
            api.play()
            try:
                api.edit_component("Ground", "Transform", "x", 700.0)
                print("[FAIL] Se permitio editar en modo PLAY (deberia estar bloqueado)")
            except InvalidOperationError:
                print("[OK] Bloqueo de edicion en PLAY verificado correctamente")

            print("[INFO] Avanzando 10 frames...")
            api.step(10)
            status = api.get_status()
            print(f"[OK] Simulacion avanzada. Tiempo: {status['time']:.4f}s")
        except Exception as e:
            print(f"[FAIL] Error durante la demo: {e}")
        finally:
            api.shutdown()

        print("=== PRUEBA FINALIZADA ===")


if __name__ == "__main__":
    main()
