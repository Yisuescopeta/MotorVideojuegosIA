import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_CWD_PATH_MUTATION = "sys.path.append(" + "os.getcwd())"
FORBIDDEN_OS_SYSTEM = "os." + "system("
FORBIDDEN_PY_LAUNCHER = "py -3" + " "


class ToolingPortabilityRegressionTests(unittest.TestCase):
    def test_all_tests_do_not_use_os_system_or_py_launcher(self) -> None:
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn(FORBIDDEN_OS_SYSTEM, source, msg=f"{path.as_posix()} still uses os.system")
            self.assertNotIn(FORBIDDEN_PY_LAUNCHER, source, msg=f"{path.as_posix()} still uses the Windows py launcher")

    def test_all_tests_do_not_mutate_sys_path_via_cwd(self) -> None:
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn(
                FORBIDDEN_CWD_PATH_MUTATION,
                source,
                msg=f"{path.as_posix()} still mutates sys.path",
            )

    def test_tools_modules_do_not_mutate_sys_path(self) -> None:
        for path in sorted((ROOT / "tools").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn(
                FORBIDDEN_CWD_PATH_MUTATION,
                source,
                msg=f"{path.as_posix()} still mutates sys.path",
            )

    def test_scripts_do_not_mutate_sys_path(self) -> None:
        for path in sorted((ROOT / "scripts").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn(
                FORBIDDEN_CWD_PATH_MUTATION,
                source,
                msg=f"{path.as_posix()} still mutates sys.path",
            )


if __name__ == "__main__":
    unittest.main()
