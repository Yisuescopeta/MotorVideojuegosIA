import unittest

from engine.scenes.compat.result_adapters import LegacyResultAdapter
from engine.scenes.refs import EntityRef, OpenDocumentId, OpenSceneRef
from engine.scenes.result import (
    CommandError,
    CommandErrorCode,
    Err,
    MutationMetadata,
    Ok,
)


class SceneResultTests(unittest.TestCase):
    def test_ok_carries_value_and_typed_mutation_metadata(self) -> None:
        scene = OpenSceneRef(OpenDocumentId.new())
        entity = EntityRef(scene, "player")
        result = Ok(
            value="updated",
            metadata=MutationMetadata(
                changed_entities=(entity,),
                history_entry_id="history-1",
                scene_revision=4,
            ),
        )

        self.assertEqual(result.value, "updated")
        self.assertEqual(result.metadata.changed_entities, (entity,))
        self.assertEqual(result.metadata.history_entry_id, "history-1")
        self.assertEqual(result.metadata.scene_revision, 4)

    def test_err_is_discriminated_by_typed_code(self) -> None:
        result = Err(
            CommandError(
                code=CommandErrorCode.PROJECTION_DIVERGED,
                user_message="La proyección requiere revisión.",
                technical_details="fingerprint mismatch",
            )
        )

        self.assertEqual(result.error.code, CommandErrorCode.PROJECTION_DIVERGED)
        self.assertEqual(result.error.technical_details, "fingerprint mismatch")

    def test_legacy_adapters_preserve_success_and_failure_semantics(self) -> None:
        ok = Ok(value=7)
        err = Err(CommandError(CommandErrorCode.NOT_FOUND, "No encontrado"))

        self.assertTrue(LegacyResultAdapter.to_bool(ok))
        self.assertFalse(LegacyResultAdapter.to_bool(err))
        self.assertEqual(LegacyResultAdapter.to_optional(ok), 7)
        self.assertIsNone(LegacyResultAdapter.to_optional(err))


if __name__ == "__main__":
    unittest.main()
