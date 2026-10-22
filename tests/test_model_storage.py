"""Regression tests for preservation, validation, disk conflict and recovery."""
import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
package = types.ModuleType("home_share_test")
package.__path__ = [str(ROOT / "custom_components/home_share")]
sys.modules["home_share_test"] = package
from home_share_test.model import difference, patched, revision, validate
from home_share_test.storage import history, managed_file, read, restore_data, save


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.config = {"light.desk": {"expose": True, "name": "Desk", "room": "Study", "aliases": ["Reading light"]},
                       "switch.legacy_disabled": {"expose": True, "name": "Legacy"}}

    def test_preserves_disabled_missing_and_metadata(self):
        result = patched(self.config, {"light.desk": {"expose": False}})
        self.assertEqual(result["switch.legacy_disabled"], self.config["switch.legacy_disabled"])
        self.assertEqual(result["light.desk"]["aliases"], ["Reading light"])
        self.assertTrue(self.config["light.desk"]["expose"])
        self.assertEqual(len(difference(self.config, result)), 1)

    def test_removes_only_requested_optional_field(self):
        result = patched(self.config, {"light.desk": {"name": None}})
        self.assertNotIn("name", result["light.desk"])
        self.assertEqual(result["light.desk"]["room"], "Study")

    def test_rejects_invalid_or_unbounded_changes(self):
        for changes in [{"../secrets": {"expose": True}}, {"light.desk": {"expose": "yes"}},
                        {"light.desk": {"service_account": "secret"}}, {"light.desk": {"aliases": "text"}},
                        {"light.desk": {"name": "a" * 256}}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                patched(self.config, changes)

    def test_hash_ignores_key_order(self):
        self.assertEqual(revision(self.config), revision(dict(reversed(list(self.config.items())))))


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = managed_file(self.tmp.name, "entities.yaml")
        self.path.write_text("light.example:\n  expose: true\n  name: Original\n")
        self.old = read(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_and_restore_preserve_exact_original(self):
        raw = self.path.read_bytes()
        new = patched(self.old, {"light.example": {"name": "Changed"}})
        before, identifier = save(self.path, new, self.old)
        self.assertEqual(before, raw)
        self.assertEqual(read(self.path), new)
        self.assertEqual(restore_data(self.path, identifier), self.old)
        self.assertEqual(history(self.path)[0]["id"], identifier)

    def test_external_edits_are_not_overwritten(self):
        self.path.write_text("{}")
        with self.assertRaisesRegex(ValueError, "changed elsewhere"):
            save(self.path, self.old, self.old)
        self.assertEqual(self.path.read_text(), "{}")

    def test_rejects_traversal_and_non_yaml(self):
        for filename in ["../secrets.yaml", "/config/configuration.yaml", "sub/file.yaml", "entities.json"]:
            with self.assertRaises(ValueError):
                managed_file(self.tmp.name, filename)
        with self.assertRaises(ValueError):
            restore_data(self.path, "../../secrets")

    def test_unsafe_yaml_rejected(self):
        self.path.write_text("!!python/object/apply:os.system ['echo unsafe']")
        with self.assertRaises(Exception):
            read(self.path)

    @unittest.skipIf(sys.platform == "win32", "Symlink creation requires elevated Windows privileges")
    def test_rejects_symlink(self):
        link = pathlib.Path(self.tmp.name) / "link.yaml"
        link.symlink_to(self.path)
        with self.assertRaises(ValueError):
            managed_file(self.tmp.name, "link.yaml")


if __name__ == "__main__":
    unittest.main()
