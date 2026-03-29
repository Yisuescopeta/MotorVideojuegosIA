import unittest
from pathlib import Path


class ToolingPortabilityRegressionTests(unittest.TestCase):
    def test_selected_subprocess_tests_do_not_use_os_system_or_py_launcher(self) -> None:
        targets = [
            Path("tests/test_engine_cli.py"),
            Path("tests/test_gym_env.py"),
            Path("tests/test_pettingzoo_env.py"),
            Path("tests/test_profiler_api.py"),
            Path("tests/test_scenario_dataset.py"),
        ]

        for path in targets:
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("os.system(", source, msg=f"{path.as_posix()} still uses os.system")
            self.assertNotIn("py -3 ", source, msg=f"{path.as_posix()} still uses the Windows py launcher")

    def test_tools_modules_do_not_mutate_sys_path(self) -> None:
        for path in sorted(Path("tools").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("sys.path.append(os.getcwd())", source, msg=f"{path.as_posix()} still mutates sys.path")


if __name__ == "__main__":
    unittest.main()
