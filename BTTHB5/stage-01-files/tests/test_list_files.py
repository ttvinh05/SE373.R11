import json

import pytest

import paths
from tools import files


def listing(path):
    return json.loads(files.list_files.invoke({"path": path}))


def test_lists_direct_children_sorted(lab_dirs):
    root = paths.WORKSPACE_DIR / "data" / "listing"
    root.mkdir()
    (root / "z.md").write_text("z")
    (root / "a-dir").mkdir()
    (root / "a-dir" / "hidden.md").write_text("nested")
    assert listing("data/listing") == {"ok": True, "path": "data/listing", "entries": [
        {"name": "a-dir", "path": "data/listing/a-dir", "type": "directory"},
        {"name": "z.md", "path": "data/listing/z.md", "type": "file"},
    ]}
    assert listing("data/listing/a-dir")["ok"]


@pytest.mark.parametrize("path,code", [
    ("data/weekly_notes.md", "NOT_A_DIRECTORY"),
    ("data/missing", "DIRECTORY_NOT_FOUND"),
    ("../outside", "PATH_OUTSIDE_WORKSPACE"),
    ("/tmp", "PATH_OUTSIDE_WORKSPACE"),
    ("", "INVALID_PATH"),
])
def test_invalid_targets(lab_dirs, path, code):
    assert listing(path)["error"]["code"] == code


def test_symlink_directory_cannot_escape(lab_dirs):
    outside = lab_dirs / "outside"
    outside.mkdir()
    (paths.WORKSPACE_DIR / "escape").symlink_to(outside, target_is_directory=True)
    assert listing("escape")["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"


def test_child_symlink_cannot_escape(lab_dirs):
    outside = lab_dirs / "outside.txt"
    outside.write_text("fake lab data")
    (paths.WORKSPACE_DIR / "data" / "escape").symlink_to(outside)
    assert listing("data")["error"]["code"] == "PATH_OUTSIDE_WORKSPACE"


def test_empty_directory_and_internal_symlink(lab_dirs):
    (paths.WORKSPACE_DIR / "empty").mkdir()
    assert listing("empty")["entries"] == []
    (paths.WORKSPACE_DIR / "alias").symlink_to(paths.WORKSPACE_DIR / "empty", target_is_directory=True)
    assert listing("alias")["ok"]


def test_discovers_renamed_policy_without_old_path(lab_dirs):
    directory = paths.WORKSPACE_DIR / "data/policies"
    before = directory / "policy-before-oct.md"
    content = before.read_text(encoding="utf-8")
    before.rename(directory / "alpha.md")
    result = listing("data/policies")
    assert [e["name"] for e in result["entries"]] == ["alpha.md", "policy-from-oct.md"]
    found = result["entries"][0]["path"]
    assert json.loads(files.read_file.invoke({"path": found}))["content"] == content


def test_stage01_has_no_skill_catalog_or_preloaded_policy(lab_dirs):
    from agent import system_prompt, capabilities
    prompt = system_prompt()
    assert capabilities()['skills'] == []
    assert '2026-10-01' not in prompt
    assert 'policy-before-oct.md' not in prompt
