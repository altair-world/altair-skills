"""Exercise broken package layouts in disposable copies, never user config."""

import json
import pathlib
import shutil
import tempfile
import unittest

from validate_package import PackageError, validate


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        source = pathlib.Path(__file__).resolve().parents[1]
        for folder in (".claude-plugin", ".codex-plugin", "skills"):
            shutil.copytree(source / folder, self.root / folder)
        shutil.copyfile(source / ".mcp.json", self.root / ".mcp.json")

    def edit_json(self, file, edit):
        path = self.root / file
        data = json.loads(path.read_text())
        edit(data)
        path.write_text(json.dumps(data))

    def test_both_clients_discover_both_skills(self):
        self.assertEqual(validate(self.root), ["altair-market", "altair-research"])

    def test_codex_version_drift(self):
        self.edit_json(".codex-plugin/plugin.json", lambda data: data.update(version="9.0.0"))
        with self.assertRaisesRegex(PackageError, "versions must match"):
            validate(self.root)

    def test_codex_path_traversal(self):
        self.edit_json(".codex-plugin/plugin.json", lambda data: data.update(skills="./../skills"))
        with self.assertRaisesRegex(PackageError, "must not contain"):
            validate(self.root)

    def test_missing_market_skill(self):
        shutil.rmtree(self.root / "skills/altair-market")
        with self.assertRaisesRegex(PackageError, "both advertised skills"):
            validate(self.root)

    def test_missing_script(self):
        (self.root / "skills/altair-market/scripts/altair_market.py").unlink()
        with self.assertRaisesRegex(PackageError, "missing package resource"):
            validate(self.root)

    def test_script_path_cannot_be_a_directory(self):
        script = self.root / "skills/altair-market/scripts/altair_market.py"
        script.unlink()
        script.mkdir()
        with self.assertRaisesRegex(PackageError, "runnable script must be a file"):
            validate(self.root)

    def test_claude_inline_mcp_override_cannot_bypass_free_endpoint_check(self):
        self.edit_json(".claude-plugin/plugin.json", lambda data: data.update(
            mcpServers={"altair": {"type": "http", "url": "https://altairworld.com/mcp"}}))
        with self.assertRaisesRegex(PackageError, "Claude manifest mcpServers overrides"):
            validate(self.root)

    def test_claude_extra_skills_must_be_checked(self):
        self.edit_json(".claude-plugin/plugin.json", lambda data: data.update(skills="./missing-skills/"))
        with self.assertRaisesRegex(PackageError, "missing package resource"):
            validate(self.root)

    def test_marketplace_cannot_select_only_one_advertised_skill(self):
        self.edit_json(".claude-plugin/marketplace.json", lambda data: data["plugins"][0].update(
            skills=["./skills/altair-research/"]))
        with self.assertRaisesRegex(PackageError, "marketplace entry skills must reference the shared"):
            validate(self.root)

    def test_explicit_shared_claude_components_remain_valid(self):
        self.edit_json(".claude-plugin/plugin.json", lambda data: data.update(
            skills=["./skills/"], mcpServers="./.mcp.json"))
        self.edit_json(".claude-plugin/marketplace.json", lambda data: data["plugins"][0].update(
            skills="./skills/"))
        self.assertEqual(validate(self.root), ["altair-market", "altair-research"])

    def test_paid_endpoint_accident(self):
        def change(data):
            data["mcpServers"]["altair"]["url"] = "https://altairworld.com/mcp"
        self.edit_json(".mcp.json", change)
        with self.assertRaisesRegex(PackageError, "credential-free public HTTP endpoint"):
            validate(self.root)

    def test_symlink_escape(self):
        icon = self.root / ".claude-plugin/icon.png"
        icon.unlink()
        icon.symlink_to(pathlib.Path(__file__).resolve())
        with self.assertRaisesRegex(PackageError, "inside the plugin root"):
            validate(self.root)

    def test_marketplace_root_drift(self):
        def change(data):
            data["plugins"][0]["source"] = "./skills"
        self.edit_json(".claude-plugin/marketplace.json", change)
        with self.assertRaisesRegex(PackageError, "select this plugin root"):
            validate(self.root)


if __name__ == "__main__":
    unittest.main()
