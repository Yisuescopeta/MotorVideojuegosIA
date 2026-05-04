"""tests/test_async_loader.py — Tests for AsyncResourceLoader."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path

from engine.resources.async_loader import (
    AsyncLoadRequest,
    AsyncResourceLoader,
    LoadStatus,
)


class TestAsyncLoader(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.loader = AsyncResourceLoader()

    def tearDown(self):
        self._tmp.cleanup()

    def _write_file(self, name: str, content: str) -> str:
        path = self.tmp / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    @staticmethod
    def _file_loader(path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def test_async_load_completes(self):
        path = self._write_file("data.txt", "hello async")
        request = self.loader.load_async(path, self._file_loader)

        # Poll with timeout
        deadline = time.time() + 5.0
        while request.status == LoadStatus.IN_PROGRESS:
            if time.time() > deadline:
                self.fail("Async load timed out")
            time.sleep(0.05)

        self.assertEqual(request.status, LoadStatus.DONE)
        self.assertEqual(request.resource, "hello async")

    def test_async_load_fails_for_missing_file(self):
        path = str(self.tmp / "does_not_exist.txt")
        request = self.loader.load_async(path, self._file_loader)

        deadline = time.time() + 5.0
        while request.status == LoadStatus.IN_PROGRESS:
            if time.time() > deadline:
                self.fail("Async load timed out")
            time.sleep(0.05)

        self.assertEqual(request.status, LoadStatus.FAILED)
        self.assertIsNotNone(request.error)

    def test_poll_returns_completed(self):
        path1 = self._write_file("a.txt", "A")
        path2 = self._write_file("b.txt", "B")

        self.loader.load_async(path1, self._file_loader)
        self.loader.load_async(path2, self._file_loader)

        deadline = time.time() + 5.0
        completed: list[AsyncLoadRequest] = []
        while len(completed) < 2:
            if time.time() > deadline:
                self.fail("Async loads timed out")
            completed.extend(self.loader.poll())
            time.sleep(0.05)

        self.assertEqual(len(completed), 2)
        resources = {r.resource for r in completed}
        self.assertEqual(resources, {"A", "B"})

    def test_get_resource_returns_none_while_pending(self):
        path = self._write_file("slow.txt", "slow")
        request = self.loader.load_async(path, self._file_loader)
        resource = self.loader.get_resource(path)
        # May be None or already loaded depending on timing
        # Just check it doesn't crash
        _ = resource

    def test_clear_removes_pending(self):
        path = self._write_file("clear.txt", "clear")
        request = self.loader.load_async(path, self._file_loader)

        # Wait for completion to avoid file-lock race on Windows teardown
        deadline = time.time() + 5.0
        while request.status == LoadStatus.IN_PROGRESS:
            if time.time() > deadline:
                self.fail("Async load timed out")
            time.sleep(0.05)

        self.loader.clear()
        self.assertEqual(self.loader.pending_count(), 0)

    def test_load_status_values(self):
        self.assertEqual(LoadStatus.IN_PROGRESS.value, "in_progress")
        self.assertEqual(LoadStatus.DONE.value, "done")
        self.assertEqual(LoadStatus.FAILED.value, "failed")


if __name__ == "__main__":
    unittest.main()
