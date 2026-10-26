#!/usr/bin/env python3
"""Check this repository's Claude/Codex package wiring without installing it.

Uses only Python 3.8's standard library. This is a repository contract check,
not a replacement for either client's own manifest validator or runtime tests.
"""

import argparse
import json
import pathlib
import re
import sys


class PackageError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PackageError(message)


def package_path(root, value):
    require(isinstance(value, str) and value.startswith("./"),
            "package paths must start with ./")
    relative = pathlib.PurePosixPath(value)
    require(".." not in relative.parts, "package paths must not contain ..")
    resolved = (root / relative).resolve()
    require(resolved == root or root in resolved.parents,
            "package paths must stay inside the plugin root")
    require(resolved.exists(), "missing package resource: {}".format(value))
    return resolved


def shared_component(root, manifest, field, expected, label):
    """Keep this package's two clients on the same audited component files.

    Claude also supports extra skills and inline/merged MCP definitions. This
    repository deliberately uses the shared defaults; accepting an uninspected
    override would make the free-endpoint/resource checks below meaningless.
    """
    if field not in manifest:
        return
    values = manifest[field] if isinstance(manifest[field], list) else [manifest[field]]
    require(bool(values), "{} {} must reference the shared component".format(label, field))
    for value in values:
        require(isinstance(value, str),
                "{} {} overrides must reference the shared {}".format(label, field, expected))
        require(package_path(root, value) == root / expected,
                "{} {} must reference the shared {}".format(label, field, expected))


def validate(root):
    root = pathlib.Path(root).resolve()

    def read_json(path):
        return json.loads((root / path).read_text(encoding="utf-8"))

    claude = read_json(".claude-plugin/plugin.json")
    codex = read_json(".codex-plugin/plugin.json")
    marketplace = read_json(".claude-plugin/marketplace.json")
    require(claude["name"] == codex["name"], "Claude/Codex plugin names must match")
    require(claude["version"] == codex["version"], "Claude/Codex versions must match")
    require(re.fullmatch(r"\d+\.\d+\.\d+", claude["version"]) is not None,
            "plugin version must be semver")
    entries = marketplace["plugins"]
    require(len(entries) == 1 and entries[0]["name"] == claude["name"],
            "marketplace entry must match the plugin name")
    require(entries[0]["description"] == claude["description"],
            "marketplace description must match the Claude plugin")
    require(package_path(root, entries[0]["source"]) == root,
            "marketplace source must select this plugin root")
    for label, manifest in (("Claude manifest", claude), ("marketplace entry", entries[0])):
        shared_component(root, manifest, "skills", "skills", label)
        shared_component(root, manifest, "mcpServers", ".mcp.json", label)

    skills_root = package_path(root, codex["skills"])
    require(skills_root == root / "skills", "both clients must discover the same skills/ root")
    require(skills_root.is_dir(), "skills root must be a directory")
    names = []
    for entry in sorted(skills_root.iterdir()):
        require(entry.is_dir(), "skills/ must contain skill directories")
        skill = package_path(root, "./skills/{}/SKILL.md".format(entry.name))
        text = skill.read_text(encoding="utf-8")
        # The two packaged skills use plain, single-line YAML name/description.
        head = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
        require(head is not None, "{}: missing YAML frontmatter".format(entry.name))
        name = re.search(r"^name: ([^\r\n]+)$", head[1], re.M)
        description = re.search(r"^description: ([^\r\n]+)$", head[1], re.M)
        require(name is not None and name[1].strip() == entry.name,
                "{}: frontmatter name must match its folder".format(entry.name))
        require(description is not None and 0 < len(description[1].strip()) <= 1024,
                "{}: description must be 1-1024 characters".format(entry.name))
        scripts = re.findall(r"\bpython3 (scripts/[a-z_]+\.py)\b", text)
        require(bool(scripts), "{}: missing runnable script example".format(entry.name))
        for script in set(scripts):
            path = package_path(root, "./skills/{}/{}".format(entry.name, script))
            require(path.is_file(), "runnable script must be a file: {}".format(script))
        names.append(entry.name)
    require(set(names) == {"altair-research", "altair-market"},
            "the package must include both advertised skills")

    mcp_path = package_path(root, codex["mcpServers"])
    require(mcp_path == root / ".mcp.json", "clients must share the root .mcp.json")
    mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
    require(mcp == {"mcpServers": {"altair": {
        "type": "http", "url": "https://altairworld.com/mcp/free"}}},
        "the bundled MCP connection must be the credential-free public HTTP endpoint")
    for field in ("composerIcon", "logo"):
        path = package_path(root, codex["interface"][field])
        require(path.is_file(), "{} must reference a file".format(field))
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        names = validate(args.root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Invalid package: {}".format(error), file=sys.stderr)
        return 1
    print("Valid Claude/Codex package: {}".format(", ".join(names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
