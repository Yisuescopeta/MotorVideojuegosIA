from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.scenes.scene_persistence import ScenePersistenceService


class ScenePersistenceBackupTests(unittest.TestCase):
    def test_save_creates_recoverable_backup_before_overwrite(self) -> None:
        service = ScenePersistenceService()
        payload = {"schema_version": 3, "name": "Backup", "entities": [], "rules": [], "feature_metadata": {}}
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "backup.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "name": "Old",
                        "entities": [],
                        "rules": [],
                        "feature_metadata": {},
                    }
                ),
                encoding="utf-8",
            )

            saved = service.save(path, payload)

            self.assertIsNotNone(saved.backup_path)
            assert saved.backup_path is not None
            backup = Path(saved.backup_path)
            self.assertEqual(json.loads(backup.read_text(encoding="utf-8"))["schema_version"], 2)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["schema_version"], 3)


if __name__ == "__main__":
    unittest.main()
