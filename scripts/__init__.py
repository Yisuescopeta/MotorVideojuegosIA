"""
scripts/__init__.py - Directorio de scripts recargables en caliente

PROPÓSITO:
    Los scripts en este directorio pueden ser modificados mientras
    el motor está ejecutándose. El sistema de hot-reload (F8) los
    recargará automáticamente.

REGLAS PARA SCRIPTS:
    - Cada script debe ser un módulo Python independiente
    - Definir una función on_reload() opcional que se ejecuta al recargar
    - No importar módulos circulares del motor
    - Usar engine.config para constantes
"""
