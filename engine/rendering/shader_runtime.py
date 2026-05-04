"""engine/rendering/shader_runtime.py — Motor de shader 2D en Python (MVP, sin GPU).

Aplica operaciones predefinidas sobre colores de píxel/textura:
modulate, tint, alpha threshold, UV scroll, tint_replace.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.resources.shader2d_resource import Shader2DResource


class ShaderRuntime:
    """Motor de shader 2D en Python (MVP, no GPU).

    Soporta operaciones predefinidas:
    - modulate: multiplica el color de textura por un color uniform
    - alpha_threshold: descarta píxeles por debajo de umbral
    - uv_scroll: desplaza coordenadas UV
    - tint_replace: reemplaza color por completo
    """

    @staticmethod
    def apply(shader: "Shader2DResource", color: tuple, alpha: float = 1.0) -> tuple:
        """Aplica el shader a un color de textura/píxel.

        Retorna (r, g, b, a) modificado.
        """
        r, g, b, a = color
        uniforms = shader.uniforms

        # modulate: multiplicar por color uniform
        if "modulate" in uniforms:
            mod = uniforms["modulate"]
            if isinstance(mod, (list, tuple)) and len(mod) >= 3:
                r = int(r * mod[0])
                g = int(g * mod[1])
                b = int(b * mod[2])

        # tint: reemplazar color
        if "tint" in uniforms:
            tint = uniforms["tint"]
            if isinstance(tint, (list, tuple)) and len(tint) >= 3:
                r, g, b = int(tint[0]), int(tint[1]), int(tint[2])

        # alpha modulation
        alpha_mod = uniforms.get("alpha", 1.0)
        a = int(a * alpha_mod * alpha)

        return (min(r, 255), min(g, 255), min(b, 255), min(a, 255))

    @staticmethod
    def get_blend_mode(shader: "Shader2DResource") -> str:
        return shader.blend_mode
