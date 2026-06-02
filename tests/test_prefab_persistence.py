"""Tests enfocados para bugs 3.4 y 3.5 del sistema de prefabs."""

import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from engine.assets.prefab import PrefabManager
from engine.core.runtime_logging import GLOBAL_LOGS
from engine.ecs.entity import Entity
from engine.ecs.world import World


class TestPrefabSaveLogging(unittest.TestCase):
    """Bug 3.4: save_prefab usa log_err, no print, y distingue tipos de error."""

    def setUp(self) -> None:
        self._log_count_before = len(GLOBAL_LOGS)

    def _recent_logs(self) -> list[tuple[str, str]]:
        return GLOBAL_LOGS[self._log_count_before:]

    def test_save_prefab_normal_success(self) -> None:
        """save_prefab guarda correctamente y retorna True (sin prints)."""
        entity = Entity("TestEntity")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.prefab")
            result = PrefabManager.save_prefab(entity, path)
            self.assertTrue(result)
            self.assertTrue(os.path.isfile(path))
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
            self.assertEqual(payload.get("root_name"), "TestEntity")
        # No debe loguear errores en caso de exito
        err_logs = [entry for entry in self._recent_logs() if entry[0] == "ERR"]
        self.assertEqual(len(err_logs), 0, f"Unexpected error logs on success: {err_logs}")

    def test_save_prefab_permission_error_returns_false_and_logs(self) -> None:
        """save_prefab retorna False y loguea error en PermissionError."""
        entity = Entity("TestEntity")
        with patch("builtins.open", side_effect=PermissionError("Acceso denegado")):
            result = PrefabManager.save_prefab(entity, "/fake/readonly/test.prefab")
        self.assertFalse(result)
        err_logs = [entry for entry in self._recent_logs() if entry[0] == "ERR"]
        self.assertTrue(len(err_logs) >= 1, f"No error log found; logs: {err_logs}")
        permission_log = next((msg for _, msg in err_logs if "Permission denied" in msg), None)
        self.assertIsNotNone(permission_log, f"No 'Permission denied' log; got: {err_logs}")

    def test_save_prefab_oserror_returns_false_and_logs(self) -> None:
        """save_prefab retorna False y loguea error en OSError genérico."""
        entity = Entity("TestEntity")
        with patch("builtins.open", side_effect=OSError("Disco lleno")):
            result = PrefabManager.save_prefab(entity, "/fake/disk/full.prefab")
        self.assertFalse(result)
        err_logs = [entry for entry in self._recent_logs() if entry[0] == "ERR"]
        self.assertTrue(len(err_logs) >= 1)
        io_log = next((msg for _, msg in err_logs if "I/O error" in msg), None)
        self.assertIsNotNone(io_log, f"No 'I/O error' log; got: {err_logs}")

    def test_save_prefab_build_error_returns_false_and_logs(self) -> None:
        """save_prefab retorna False si _build_prefab_payload lanza excepción."""
        entity = Entity("Broken")
        with patch.object(
            PrefabManager, "_build_prefab_payload", side_effect=ValueError("Entidad corrupta")
        ):
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "broken.prefab")
                result = PrefabManager.save_prefab(entity, path)
        self.assertFalse(result)
        err_logs = [entry for entry in self._recent_logs() if entry[0] == "ERR"]
        self.assertTrue(len(err_logs) >= 1)
        build_log = next((msg for _, msg in err_logs if "building prefab payload" in msg), None)
        self.assertIsNotNone(build_log, f"No 'building prefab payload' log; got: {err_logs}")


class TestPrefabInstantiateConcurrency(unittest.TestCase):
    """Bug 3.5: instantiate_prefab previene colisiones de nombres con lock."""

    def setUp(self) -> None:
        self.world = World()
        self._prefab_dir = tempfile.TemporaryDirectory()
        self._prefab_path = os.path.join(self._prefab_dir.name, "concurrent.prefab")

        # Crear un prefab valido simple (schema_version 2 = CURRENT)
        payload = {
            "root_name": "Enemy",
            "schema_version": 2,
            "entities": [{"name": "Enemy", "components": {"Transform": {"x": 0.0, "y": 0.0}}}],
        }
        with open(self._prefab_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    def tearDown(self) -> None:
        self._prefab_dir.cleanup()

    def test_single_instantiate_works(self) -> None:
        """La instanciación normal sigue funcionando."""
        entity = PrefabManager.instantiate_prefab(self._prefab_path, self.world)
        self.assertIsNotNone(entity)
        self.assertEqual(entity.name, "Enemy")  # type: ignore[union-attr]

    def test_repeated_instantiate_creates_unique_names(self) -> None:
        """Instancias repetidas generan nombres únicos sin colisiones."""
        e1 = PrefabManager.instantiate_prefab(self._prefab_path, self.world)
        e2 = PrefabManager.instantiate_prefab(self._prefab_path, self.world)
        e3 = PrefabManager.instantiate_prefab(self._prefab_path, self.world)

        self.assertIsNotNone(e1)
        self.assertIsNotNone(e2)
        self.assertIsNotNone(e3)
        names = {e1.name, e2.name, e3.name}  # type: ignore[union-attr]
        self.assertEqual(len(names), 3, f"Duplicate names: {names}")
        self.assertIn("Enemy", names)
        self.assertIn("Enemy_1", names)
        self.assertIn("Enemy_2", names)

    def test_concurrent_no_errors_all_non_none(self) -> None:
        """Instanciaciones concurrentes no lanzan errores y todas retornan Entity."""
        results: list[Entity | None] = []
        errors: list[Exception] = []

        def instantiate() -> None:
            try:
                result = PrefabManager.instantiate_prefab(self._prefab_path, self.world)
                results.append(result)
            except Exception as exc:
                errors.append(exc)

        thread_count = 8
        threads = [threading.Thread(target=instantiate) for _ in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Errors during concurrent instantiation: {errors}")
        self.assertEqual(len(results), thread_count)
        self.assertTrue(all(r is not None for r in results))

    def test_concurrent_unique_names_under_contention(self) -> None:
        """Regresion: bajo contencion real, todas las entidades tienen nombres unicos.

        Usa un threading.Event para forzar que todos los hilos compitan por
        create_entity al mismo tiempo. Con el viejo check-then-create (fuera
        del lock), esto producia nombres duplicados. Con la reserva atomica
        (create_entity dentro del lock), cada hilo obtiene un nombre unico.
        """
        gate = threading.Event()
        original_create = self.world.create_entity

        def gated_create(name: str) -> Entity:
            gate.wait()
            return original_create(name)

        results: list[Entity | None] = []
        errors: list[Exception] = []

        def instantiate() -> None:
            try:
                result = PrefabManager.instantiate_prefab(self._prefab_path, self.world)
                results.append(result)
            except Exception as exc:
                errors.append(exc)

        thread_count = 12
        with patch.object(self.world, "create_entity", side_effect=gated_create):
            threads = [threading.Thread(target=instantiate) for _ in range(thread_count)]
            for t in threads:
                t.start()

            # Permitir que todos los hilos generen nombres y lleguen a create_entity
            time.sleep(0.3)

            # Liberar todos simultaneamente
            gate.set()

            for t in threads:
                t.join()

        self.assertEqual(len(errors), 0, f"Errors: {errors}")
        self.assertEqual(len(results), thread_count)
        self.assertTrue(all(r is not None for r in results))

        names = [r.name for r in results]  # type: ignore[union-attr]
        unique_names = set(names)
        self.assertEqual(
            len(unique_names),
            thread_count,
            f"Duplicate names detected: {names}",
        )
        expected = {"Enemy"} | {f"Enemy_{i}" for i in range(1, thread_count)}
        self.assertEqual(unique_names, expected)
        self.assertFalse(PrefabManager._name_lock.locked())

    def test_lock_released_after_instantiate(self) -> None:
        """El lock se libera despues de cada llamada a instantiate_prefab."""
        PrefabManager.instantiate_prefab(self._prefab_path, self.world)
        self.assertFalse(
            PrefabManager._name_lock.locked(),
            "Lock should be released after instantiate_prefab",
        )

        # Segunda instancia (para forzar loop de colision de nombres)
        PrefabManager.instantiate_prefab(self._prefab_path, self.world)
        self.assertFalse(
            PrefabManager._name_lock.locked(),
            "Lock should be released even when name collision loop runs",
        )


class TestPrefabRoundtrip(unittest.TestCase):
    """Test de ida y vuelta básico: save + load + instantiate."""

    def setUp(self) -> None:
        self._log_count_before = len(GLOBAL_LOGS)

    def _recent_logs(self) -> list[tuple[str, str]]:
        return GLOBAL_LOGS[self._log_count_before:]

    def test_save_and_instantiate_roundtrip(self) -> None:
        """Guardar un prefab e instanciarlo desde archivo funciona."""
        world = World()
        entity = world.create_entity("Hero")
        world.create_entity("Hero/Weapon")

        with tempfile.TemporaryDirectory() as tmp:
            prefab_path = os.path.join(tmp, "hero.prefab")
            self.assertTrue(PrefabManager.save_prefab(entity, prefab_path, world))

            # Instanciar en un mundo nuevo
            new_world = World()
            instance = PrefabManager.instantiate_prefab(prefab_path, new_world)
            self.assertIsNotNone(instance)
            self.assertEqual(instance.name, "Hero")  # type: ignore[union-attr]

            # La segunda instancia debe tener nombre único
            instance2 = PrefabManager.instantiate_prefab(prefab_path, new_world)
            self.assertIsNotNone(instance2)
            self.assertEqual(instance2.name, "Hero_1")  # type: ignore[union-attr]

        err_logs = [entry for entry in self._recent_logs() if entry[0] == "ERR"]
        self.assertEqual(len(err_logs), 0, f"Unexpected errors during roundtrip: {err_logs}")


if __name__ == "__main__":
    unittest.main()
