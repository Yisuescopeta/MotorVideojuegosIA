import unittest
from pathlib import Path

from engine.levels.component_registry import create_default_registry


class TechnicalDocComponentRegistrySyncTests(unittest.TestCase):
    def test_technical_doc_mentions_all_registered_components(self):
        technical = Path("docs/TECHNICAL.md").read_text(encoding="utf-8")
        registered = create_default_registry().list_registered()

        missing = [name for name in registered if f"`{name}`" not in technical]

        self.assertFalse(
            missing,
            "docs/TECHNICAL.md is missing registered components: "
            + ", ".join(sorted(missing)),
        )
