from __future__ import annotations

import ast
import json
import math
from pathlib import Path
import unittest

from engine.vision import STATUS
from engine.vision.gamespec2d import (
    ALLOWED_ENTITY_TYPES,
    CURRENT_SCHEMA_VERSION,
    CameraSpec,
    EntitySpec,
    GameSpec2D,
    GameSpecValidationError,
    GridSpec,
    SourceImageMetadata,
    TileCell,
    TileMapSpec,
    WarningSpec,
)


def minimal_spec() -> GameSpec2D:
    return GameSpec2D(grid=GridSpec(width=4, height=3, tile_size=16.0))


class GameSpec2DTests(unittest.TestCase):
    def assert_validation_fails(self, spec: GameSpec2D, field: str) -> GameSpecValidationError:
        with self.assertRaises(GameSpecValidationError) as caught:
            spec.validate()
        self.assertIn(field, caught.exception.field)
        self.assertIn(field, str(caught.exception))
        return caught.exception

    def test_valid_minimal_spec_validates(self) -> None:
        minimal_spec().validate()

    def test_to_dict_from_dict_roundtrip_and_json_compatibility(self) -> None:
        spec = minimal_spec()
        spec.entities.append(EntitySpec(type="coin", x=1.5, y=2.5, confidence=1.0))
        as_dict = spec.to_dict()

        json.dumps(as_dict)
        roundtripped = GameSpec2D.from_dict(json.loads(json.dumps(as_dict)))

        self.assertEqual(roundtripped.to_dict(), as_dict)
        roundtripped.validate()

    def test_unsupported_schema_version_fails(self) -> None:
        spec = minimal_spec()
        spec.schema_version = "gamespec2d.v999"
        self.assert_validation_fails(spec, "schema_version")

    def test_unsupported_game_type_fails(self) -> None:
        spec = minimal_spec()
        spec.game_type = "topdown"
        self.assert_validation_fails(spec, "game_type")

    def test_invalid_grid_and_tile_size_fail(self) -> None:
        for field, grid in (
            ("grid.width", GridSpec(width=0, height=1, tile_size=1.0)),
            ("grid.height", GridSpec(width=1, height=-1, tile_size=1.0)),
            ("grid.tile_size", GridSpec(width=1, height=1, tile_size=0.0)),
            ("grid.tile_size", GridSpec(width=1, height=1, tile_size=math.inf)),
        ):
            with self.subTest(field=field):
                self.assert_validation_fails(GameSpec2D(grid=grid), field)

    def test_out_of_bounds_solid_and_decorative_cells_fail(self) -> None:
        cases = (
            ("tilemap.solid_cells[0].x", TileMapSpec(solid_cells=[TileCell(x=4, y=0)])),
            ("tilemap.solid_cells[0].y", TileMapSpec(solid_cells=[TileCell(x=0, y=3)])),
            ("tilemap.decorative_cells[0].x", TileMapSpec(decorative_cells=[TileCell(x=-1, y=0)])),
            ("tilemap.decorative_cells[0].y", TileMapSpec(decorative_cells=[TileCell(x=0, y=-1)])),
        )
        for field, tilemap in cases:
            with self.subTest(field=field):
                spec = minimal_spec()
                spec.tilemap = tilemap
                self.assert_validation_fails(spec, field)

    def test_source_camera_grid_tilemap_entities_warnings_confidence_metadata_preserved(self) -> None:
        spec = GameSpec2D(
            source=SourceImageMetadata(width=320, height=180, path="input.png", metadata={"confidence": 0.5}),
            camera=CameraSpec(x=1.0, y=2.0, width=160.0, height=90.0, confidence=0.75, metadata={"mode": "crop"}),
            grid=GridSpec(width=5, height=4, tile_size=8.0, origin_x=3.0, origin_y=4.0, confidence=0.8, metadata={"unit": "px"}),
            tilemap=TileMapSpec(
                solid_cells=[TileCell(x=1, y=1, label="solid_ground", confidence=0.9, metadata={"edge": True})],
                decorative_cells=[TileCell(x=2, y=2, label="decorative_prop", confidence=0.1, metadata={"color": "red"})],
                confidence=0.6,
                metadata={"layer": "vision"},
            ),
            entities=[EntitySpec(type="player_spawn", x=1.0, y=2.0, semantics="player_spawn", label="player_spawn", confidence=1.0, metadata={"id": "p1"})],
            warnings=[WarningSpec(code="low_contrast", message="low contrast", confidence=0.0, metadata={"source": "detector"})],
            confidence=0.7,
            metadata={"detector": {"confidence": 0.4}},
        )

        spec.validate()
        restored = GameSpec2D.from_dict(spec.to_dict())

        self.assertEqual(restored.to_dict(), spec.to_dict())

    def test_all_allowed_entity_types_accepted(self) -> None:
        spec = minimal_spec()
        spec.entities = [EntitySpec(type=entity_type, x=0.0, y=0.0, semantics=entity_type, label=entity_type) for entity_type in sorted(ALLOWED_ENTITY_TYPES)]
        spec.validate()

    def test_unknown_entity_type_fails(self) -> None:
        spec = minimal_spec()
        spec.entities = [EntitySpec(type="boss", x=0.0, y=0.0)]
        self.assert_validation_fails(spec, "entities[0].type")

    def test_unknown_semantics_or_label_fails_unless_decorative_prop(self) -> None:
        for kwargs, field in (
            ({"semantics": "mystery"}, "entities[0].semantics"),
            ({"label": "mystery"}, "entities[0].label"),
        ):
            with self.subTest(field=field):
                spec = minimal_spec()
                spec.entities = [EntitySpec(type="coin", x=0.0, y=0.0, **kwargs)]
                self.assert_validation_fails(spec, field)

        spec = minimal_spec()
        spec.entities = [EntitySpec(type="decorative_prop", x=0.0, y=0.0, semantics="tree", label="unknown_tree")]
        spec.validate()

    def test_non_finite_coordinates_fail(self) -> None:
        for field, entity in (
            ("entities[0].x", EntitySpec(type="coin", x=math.nan, y=0.0)),
            ("entities[0].y", EntitySpec(type="coin", x=0.0, y=math.inf)),
        ):
            with self.subTest(field=field):
                spec = minimal_spec()
                spec.entities = [entity]
                self.assert_validation_fails(spec, field)

    def test_confidence_bounds_fail_and_edges_are_accepted(self) -> None:
        for confidence in (-0.01, 1.01):
            with self.subTest(confidence=confidence):
                spec = minimal_spec()
                spec.confidence = confidence
                self.assert_validation_fails(spec, "confidence")

        for confidence in (0.0, 1.0):
            with self.subTest(confidence=confidence):
                spec = minimal_spec()
                spec.confidence = confidence
                spec.camera.confidence = confidence
                spec.grid.confidence = confidence
                spec.tilemap.confidence = confidence
                spec.entities = [EntitySpec(type="coin", x=0.0, y=0.0, confidence=confidence)]
                spec.warnings = [WarningSpec(code="ok", message="ok", confidence=confidence)]
                spec.validate()

    def test_no_mandatory_imports_of_optional_cv_packages(self) -> None:
        source = Path("engine/vision/gamespec2d.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])

        self.assertTrue({"cv2", "PIL", "numpy", "supervision"}.isdisjoint(imported_roots))

    def test_engine_vision_exposes_curated_all_and_status(self) -> None:
        import engine.vision as vision

        self.assertEqual(STATUS, "internal-experimental")
        self.assertEqual(vision.STATUS, "internal-experimental")
        self.assertIn("GameSpec2D", vision.__all__)
        self.assertIn("STATUS", vision.__all__)
        self.assertNotIn("math", vision.__all__)
        self.assertEqual(GameSpec2D().schema_version, CURRENT_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
