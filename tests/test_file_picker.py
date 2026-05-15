import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from engine.editor.ui_core.controls.file_picker import FileEntry, FilePickerModel


class TestFilePickerModel(unittest.TestCase):
    def test_navigate_to_valid_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            sub = Path(tmp) / "subdir"
            sub.mkdir()
            (sub / "test.txt").write_text("hello")
            model = FilePickerModel(root_path=tmp, current_path=tmp)
            self.assertTrue(model.navigate_to(str(sub)))
            self.assertEqual(Path(model.current_path).resolve(), sub.resolve())
            self.assertIn("test.txt", [e.name for e in model.entries])

    def test_navigate_to_file_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            f = Path(tmp) / "file.txt"
            f.write_text("data")
            model = FilePickerModel(root_path=tmp, current_path=tmp)
            self.assertFalse(model.navigate_to(str(f)))

    def test_go_up(self) -> None:
        with TemporaryDirectory() as tmp:
            sub = Path(tmp) / "sub"
            sub.mkdir()
            model = FilePickerModel(root_path=tmp, current_path=str(sub))
            self.assertTrue(model.go_up())
            self.assertEqual(Path(model.current_path).resolve(), Path(tmp).resolve())

    def test_go_up_at_root_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            model = FilePickerModel(root_path=tmp, current_path=tmp)
            self.assertFalse(model.go_up())

    def test_set_filter(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "a.json").write_text("{}")
            (Path(tmp) / "b.txt").write_text("text")
            model = FilePickerModel(root_path=tmp, current_path=tmp)
            model.set_filter("*.json")
            names = [e.name for e in model.filtered_entries()]
            self.assertIn("a.json", names)
            self.assertNotIn("b.txt", names)

    def test_select(self) -> None:
        model = FilePickerModel(entries=[])
        model.select("/some/path/file.txt")
        self.assertEqual(model.selected_path, "/some/path/file.txt")

    def test_show_hidden(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "visible.txt").write_text("ok")
            (Path(tmp) / ".hidden.txt").write_text("secret")
            model = FilePickerModel(root_path=tmp, current_path=tmp)
            names = [e.name for e in model.filtered_entries()]
            self.assertIn("visible.txt", names)
            self.assertNotIn(".hidden.txt", names)
            model.show_hidden = True
            names = [e.name for e in model.filtered_entries()]
            self.assertIn(".hidden.txt", names)

    def test_directory_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            sub = Path(tmp) / "subdir"
            sub.mkdir()
            (Path(tmp) / "file.txt").write_text("data")
            model = FilePickerModel(root_path=tmp, current_path=tmp, mode="directory")
            names = [e.name for e in model.filtered_entries()]
            self.assertIn("subdir", names)
            self.assertNotIn("file.txt", names)

    def test_to_dict_from_dict_roundtrip(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "test.json").write_text("{}")
            model = FilePickerModel(root_path=tmp, current_path=tmp)
            model.select(str(Path(tmp) / "test.json"))
            payload = model.to_dict()
            restored = FilePickerModel.from_dict(payload)
            self.assertEqual(restored.schema_version, 1)
            self.assertEqual(restored.selected_path, model.selected_path)

    def test_file_entry_fields(self) -> None:
        entry = FileEntry(name="test.png", path="/tmp/test.png", is_dir=False, extension=".png", size=1024)
        self.assertEqual(entry.name, "test.png")
        self.assertEqual(entry.extension, ".png")
        self.assertEqual(entry.size, 1024)
        self.assertFalse(entry.is_dir)


if __name__ == "__main__":
    unittest.main()
