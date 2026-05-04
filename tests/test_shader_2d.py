"""Tests for Shader2DResource and ShaderRuntime."""

from __future__ import annotations

import unittest

from engine.rendering.shader_runtime import ShaderRuntime
from engine.resources.shader2d_resource import Shader2DResource


class TestShader2D(unittest.TestCase):
    """Test Shader2DResource serialization and ShaderRuntime operations."""

    def test_create_shader_resource(self):
        """Crear Shader2DResource vacío con defaults."""
        shader = Shader2DResource()
        self.assertEqual(shader.resource_id, "")
        self.assertEqual(shader.resource_name, "New Shader")
        self.assertEqual(shader.shader_type, "canvas_item")
        self.assertEqual(shader.vertex_source, "")
        self.assertEqual(shader.fragment_source, "")
        self.assertEqual(shader.uniforms, {})
        self.assertEqual(shader.blend_mode, "alpha")

    def test_shader_serialization(self):
        """to_dict/from_dict roundtrip."""
        shader = Shader2DResource(
            resource_id="shader_001",
            resource_name="Tint Shader",
            shader_type="canvas_item",
            vertex_source="void vertex() {}",
            fragment_source="void fragment() {}",
            uniforms={"tint": [255, 128, 64], "alpha": 0.5},
            blend_mode="add",
        )
        data = shader.to_dict()
        loaded = Shader2DResource.from_dict(data)
        self.assertEqual(loaded.resource_id, "shader_001")
        self.assertEqual(loaded.resource_name, "Tint Shader")
        self.assertEqual(loaded.shader_type, "canvas_item")
        self.assertEqual(loaded.vertex_source, "void vertex() {}")
        self.assertEqual(loaded.fragment_source, "void fragment() {}")
        self.assertEqual(loaded.uniforms, {"tint": [255, 128, 64], "alpha": 0.5})
        self.assertEqual(loaded.blend_mode, "add")

    def test_shader_modulate(self):
        """Aplicar modulate uniform al color."""
        shader = Shader2DResource(
            resource_id="modulate_test",
            uniforms={"modulate": [0.5, 0.5, 0.5]},
        )
        result = ShaderRuntime.apply(shader, (200, 100, 50, 255))
        self.assertEqual(result, (100, 50, 25, 255))

    def test_shader_tint(self):
        """Aplicar tint uniform."""
        shader = Shader2DResource(
            resource_id="tint_test",
            uniforms={"tint": [128, 64, 32]},
        )
        result = ShaderRuntime.apply(shader, (200, 100, 50, 255))
        self.assertEqual(result, (128, 64, 32, 255))

    def test_shader_alpha(self):
        """Aplicar alpha uniform."""
        shader = Shader2DResource(
            resource_id="alpha_test",
            uniforms={"alpha": 0.5},
        )
        result = ShaderRuntime.apply(shader, (200, 100, 50, 200))
        # alpha: 200 * 0.5 * 1.0 = 100
        self.assertEqual(result, (200, 100, 50, 100))

    def test_shader_blend_mode(self):
        """Leer blend_mode del shader."""
        shader = Shader2DResource(resource_id="blend_test", blend_mode="multiply")
        mode = ShaderRuntime.get_blend_mode(shader)
        self.assertEqual(mode, "multiply")

    def test_shader_no_uniforms(self):
        """Shader sin uniforms no modifica color."""
        shader = Shader2DResource(resource_id="empty")
        result = ShaderRuntime.apply(shader, (200, 100, 50, 255))
        self.assertEqual(result, (200, 100, 50, 255))

    def test_modulate_and_alpha_combined(self):
        """Combinar modulate y alpha uniform."""
        shader = Shader2DResource(
            resource_id="combined",
            uniforms={"modulate": [0.5, 0.5, 0.5], "alpha": 0.5},
        )
        result = ShaderRuntime.apply(shader, (200, 100, 50, 255))
        # modulate: 100, 50, 25. alpha: 255 * 0.5 * 1.0 = 127
        self.assertEqual(result, (100, 50, 25, 127))

    def test_tint_overrides_modulate(self):
        """Tint reemplaza modulate si ambos están presentes."""
        shader = Shader2DResource(
            resource_id="tint_override",
            uniforms={
                "modulate": [0.5, 0.5, 0.5],
                "tint": [255, 0, 0],
            },
        )
        result = ShaderRuntime.apply(shader, (200, 100, 50, 255))
        self.assertEqual(result, (255, 0, 0, 255))

    def test_from_dict_missing_fields(self):
        """from_dict con dict vacío produce defaults."""
        shader = Shader2DResource.from_dict({})
        self.assertEqual(shader.resource_id, "")
        self.assertEqual(shader.resource_name, "New Shader")

    def test_repr(self):
        """Representación textual del recurso."""
        shader = Shader2DResource(
            resource_name="Test",
            uniforms={"tint": [255, 0, 0]},
        )
        r = repr(shader)
        self.assertIn("Test", r)
        self.assertIn("tint", r)


if __name__ == "__main__":
    unittest.main()
