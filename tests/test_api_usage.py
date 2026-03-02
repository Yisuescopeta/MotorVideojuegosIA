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
