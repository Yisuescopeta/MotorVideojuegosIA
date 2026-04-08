#!/usr/bin/env python3
"""
Demo runner para el vertical slice de plataformas 2D.

Uso:
    python run_demo.py              # Cargar y ejecutar el demo
    python run_demo.py --validate   # Solo validar sin ejecutar
    python run_demo.py --headless   # Ejecutar sin renderizado
"""

import argparse
import sys
from pathlib import Path

# Añadir el proyecto al path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from engine.api import EngineAPI


def validate_scene():
    """Validar que la escena se puede cargar correctamente."""
    print("🔍 Validando escena...")
    
    try:
        api = EngineAPI(project_root=str(project_root))
        api.load_level("levels/platformer_vertical_slice.json")
        
        scene = api.get_active_scene()
        print(f"✅ Escena cargada: {scene.get('name', 'Unnamed')}")
        
        # Verificar entidades
        # Nota: La API no expone directamente las entidades del mundo,
        # pero podemos verificar que la escena está cargada
        
        print("✅ Validación completada")
        return True
        
    except Exception as e:
        print(f"❌ Error validando escena: {e}")
        return False


def run_demo(headless=False):
    """Ejecutar el demo."""
    print("🎮 Iniciando Platformer Vertical Slice...")
    print(f"   Modo: {'headless' if headless else 'normal'}")
    
    try:
        api = EngineAPI(project_root=str(project_root))
        api.load_level("levels/platformer_vertical_slice.json")
        
        print("✅ Escena cargada")
        print("\n📋 Resumen de la escena:")
        print("   - Player: Entidad controlable con física y animaciones")
        print("   - Coin: Coleccionable que da puntos")
        print("   - Spikes: Peligro que hace respawn")
        print("   - Goal: Meta para completar el nivel")
        print("\n🎯 Objetivo: Llega a la meta verde evitando los pinchos!")
        print("\n⌨️  Controles:")
        print("   A / ← : Mover izquierda")
        print("   D / → : Mover derecha")
        print("   SPACE : Saltar")
        
        if not headless:
            print("\n▶️  Iniciando gameplay...")
            api.play()
            
            # Simular algunos frames
            print("\n⏱️  Simulando 60 frames...")
            for i in range(60):
                api.step(1)
                if i % 20 == 0:
                    print(f"   Frame {i}/60")
            
            print("\n⏹️  Deteniendo...")
            api.stop()
        
        print("\n✅ Demo completado!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error ejecutando demo: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Platformer Vertical Slice Demo Runner"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Solo validar la escena sin ejecutar"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Ejecutar sin renderizado gráfico"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MotorVideojuegosIA - Platformer Vertical Slice")
    print("=" * 60)
    
    if args.validate:
        success = validate_scene()
    else:
        success = run_demo(headless=args.headless)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
