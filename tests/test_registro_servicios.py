import unittest

from engine.services.registro_servicios import RegistroServicios


class RegistroServiciosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registro = RegistroServicios()

    def test_registrar_y_obtener_builtin(self) -> None:
        servicio = {"dato": 42}
        self.registro.registrar_builtin("ConfigGlobal", servicio)

        self.assertTrue(self.registro.tiene("ConfigGlobal"))
        self.assertIs(self.registro.obtener("ConfigGlobal"), servicio)

    def test_registrar_y_obtener_runtime(self) -> None:
        servicio = {"dato": 7}
        self.registro.registrar("TempService", servicio)

        self.assertTrue(self.registro.tiene("TempService"))
        self.assertIs(self.registro.obtener("TempService"), servicio)

    def test_runtime_oculta_builtin_mismo_nombre(self) -> None:
        builtin = {"capa": "builtin"}
        runtime = {"capa": "runtime"}
        self.registro.registrar_builtin("MiServicio", builtin)
        self.registro.registrar("MiServicio", runtime)

        self.assertIs(self.registro.obtener("MiServicio"), runtime)

    def test_desregistrar_solo_runtime(self) -> None:
        self.registro.registrar_builtin("Persistente", {})
        self.registro.registrar("Volatil", {})

        self.assertTrue(self.registro.desregistrar("Volatil"))
        self.assertFalse(self.registro.tiene("Volatil"))
        self.assertTrue(self.registro.tiene("Persistente"))
        self.assertFalse(self.registro.desregistrar("Volatil"))

    def test_desregistrar_builtin(self) -> None:
        self.registro.registrar_builtin("Builtin", {})

        self.assertTrue(self.registro.desregistrar_builtin("Builtin"))
        self.assertFalse(self.registro.tiene("Builtin"))

    def test_obtener_inexistente_retorna_none(self) -> None:
        self.assertIsNone(self.registro.obtener("NoExiste"))
        self.assertFalse(self.registro.tiene("NoExiste"))

    def test_listar_servicios_combina_ambas_capas(self) -> None:
        self.registro.registrar_builtin("A", 1)
        self.registro.registrar("B", 2)
        self.registro.registrar_builtin("C", 3)

        self.assertEqual(self.registro.listar_servicios(), ["A", "B", "C"])

    def test_limpiar_runtime_preserva_builtins(self) -> None:
        self.registro.registrar_builtin("Global", {})
        self.registro.registrar("Sesion", {})

        self.registro.limpiar_runtime()

        self.assertTrue(self.registro.tiene("Global"))
        self.assertFalse(self.registro.tiene("Sesion"))

    def test_limpiar_todo_elimina_todo(self) -> None:
        self.registro.registrar_builtin("Global", {})
        self.registro.registrar("Sesion", {})

        self.registro.limpiar_todo()

        self.assertEqual(self.registro.listar_servicios(), [])


if __name__ == "__main__":
    unittest.main()
