from __future__ import annotations

import ast
import json
import math
import unittest
from pathlib import Path

from engine.vision.detection_result import DetectionResult, DetectionResultValidationError
from engine.vision.supervision_adapter import (
    OptionalSupervisionDependencyError,
    UnknownDetectionLabelError,
    detections_to_gamespec2d,
    normalize_detections,
)


class DetectionResultTests(unittest.TestCase):
    def test_detection_result_roundtrips_dict_and_bbox_mapping(self) -> None:
        result = DetectionResult.from_dict(
            {"label": "coin", "bbox": {"x": 1, "y": 2, "w": 3, "h": 4}, "confidence": 0.75, "metadata": {"id": "a"}}
        )

        self.assertEqual(result.bbox, (1.0, 2.0, 3.0, 4.0))
        self.assertEqual(DetectionResult.from_dict(json.loads(json.dumps(result.to_dict()))), result)

    def test_detection_result_rejects_non_finite_bool_and_invalid_confidence(self) -> None:
        cases = (
            {"label": "coin", "bbox": (True, 0, 1, 1)},
            {"label": "coin", "bbox": (0, 0, math.inf, 1)},
            {"label": "coin", "bbox": (0, 0, 0, 1)},
            {"label": "coin", "bbox": (0, 0, 1, 1), "confidence": 1.01},
            {"label": "", "bbox": (0, 0, 1, 1)},
        )
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(DetectionResultValidationError):
                    DetectionResult.from_dict(payload)


class SupervisionAdapterTests(unittest.TestCase):
    def test_accepts_detection_results_and_normalized_dicts_without_supervision(self) -> None:
        normalized = normalize_detections([
            DetectionResult(label="coin", bbox=(0, 0, 10, 10), confidence=1.0),
            {"label": "enemy", "bbox": [20, 5, 10, 10], "confidence": 0.5},
        ])

        self.assertEqual([item.label for item in normalized], ["coin", "enemy"])

    def test_converts_allowed_and_alias_labels_to_valid_gamespec_entities(self) -> None:
        spec = detections_to_gamespec2d(
            [
                {"label": "spawn", "bbox": [0, 0, 16, 16]},
                {"label": "coin", "bbox": [16, 0, 8, 8], "confidence": 0.9},
                {"label": "spikes", "bbox": [32, 0, 8, 8]},
                {"label": "finish", "bbox": [48, 0, 8, 8]},
            ],
            tile_size=8.0,
        )

        spec.validate()
        self.assertEqual([entity.type for entity in spec.entities], ["player_spawn", "coin", "hazard", "goal"])
        self.assertEqual(spec.entities[1].x, 20.0)
        self.assertEqual(spec.entities[1].metadata["bbox"]["w"], 8.0)

    def test_unknown_label_defaults_to_decorative_prop_with_warning(self) -> None:
        spec = detections_to_gamespec2d([{"label": "tree", "bbox": [1, 2, 3, 4], "confidence": 0.25}])

        spec.validate()
        self.assertEqual(spec.entities[0].type, "decorative_prop")
        self.assertEqual(spec.entities[0].label, "tree")
        self.assertEqual(spec.warnings[0].code, "unknown_detection_label")

    def test_unknown_label_reject_policy_raises(self) -> None:
        with self.assertRaises(UnknownDetectionLabelError):
            detections_to_gamespec2d([{"label": "tree", "bbox": [1, 2, 3, 4]}], unknown_label_policy="reject")

    def test_empty_detections_return_valid_spec_with_no_detections_warning(self) -> None:
        spec = detections_to_gamespec2d([], source_width=320, source_height=180)

        spec.validate()
        self.assertEqual(spec.entities, [])
        self.assertEqual(spec.warnings[0].code, "no_detections")
        self.assertEqual(spec.source.width, 320)

    def test_supervision_native_object_without_dependency_has_actionable_error(self) -> None:
        SupervisionDetections = type("Detections", (), {"__module__": "supervision.detection.core"})

        with self.assertRaises(OptionalSupervisionDependencyError) as caught:
            normalize_detections(SupervisionDetections())

        self.assertIn("optional dependency 'supervision' is not installed", str(caught.exception))
        self.assertIn("DetectionResult/dict", str(caught.exception))

    def test_adapter_sources_do_not_import_optional_vision_or_network_packages(self) -> None:
        forbidden = {"cv2", "PIL", "Pillow", "numpy", "supervision", "roboflow"}
        for path in (Path("engine/vision/detection_result.py"), Path("engine/vision/supervision_adapter.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported_roots: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported_roots.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported_roots.add(node.module.split(".")[0])
            self.assertTrue(forbidden.isdisjoint(imported_roots), path)


if __name__ == "__main__":
    unittest.main()
