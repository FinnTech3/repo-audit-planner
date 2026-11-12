import json
from pathlib import Path

import pytest
import repo_facts as rf
from helpers import AWS_KEY, FIXME, SECRET_VALUE, TODO, commit_all, git, needs_git, write


def make_repo(root):
    write(root, "src/app.py", f"import os\n# {TODO}: tidy\nx = 1\n")
    write(root, "src/util.js", "export const a = 1;\n")
    write(root, "tests/test_app.py", "def test_x():\n    assert True\n")
    write(root, "README.md", f"# Demo\n{TODO} in docs is not code debt\n")
    write(root, "package.json", "{}\n")
    write(root, "package-lock.json", "{}\n")
    write(root, ".github/workflows/ci.yml", "name: ci\n")
    write(root, "logo.png", b"\x89PNG\x00\x00binary")
    write(root, "node_modules/dep/index.js", "module.exports = 1;\n")
    return root


def test_counts_match_the_files(tmp_path):
    facts = rf.scan(make_repo(tmp_path))
    langs = {x["language"]: (x["files"], x["lines"]) for x in facts["languages"]}
    assert langs["Python"] == (2, 5) and langs["JavaScript"] == (1, 1) and "Markdown" in langs
    assert facts["tests"] == {"test_files": 1, "source_files": 2, "test_lines": 2, "source_lines": 4, "ratio": 0.5}
    assert facts["markers"]["counts"] == {TODO: 1}
    assert facts["markers"]["locations"] == [{"file": "src/app.py", "line": 2, "marker": TODO}]
    assert facts["manifests"] == ["package.json"] and facts["lockfiles"] == ["package-lock.json"]
    assert facts["ci"] == [".github/workflows/"] and facts["skipped"]["binary"] == 1
    assert not any("node_modules" in x["file"] for x in facts["largest"])


def test_secret_values_never_appear_in_any_output(tmp_path, capsys):
    write(
        tmp_path,
        "conf.py",
        f"# {FIXME} rotate {AWS_KEY}\npassword = '{SECRET_VALUE}'\nname = 'ok'\nPAYMENT_API_KEY = \"{SECRET_VALUE}\"\n",
    )
    facts = rf.scan(tmp_path)
    found = {(s["line"], s["kind"]) for s in facts["secrets"]["findings"]}
    assert found == {(1, "aws access key"), (2, "hardcoded credential"), (4, "hardcoded credential")}
    assert rf.main([str(tmp_path)]) == 0 and rf.main([str(tmp_path), "--json"]) == 0
    printed = capsys.readouterr().out
    assert AWS_KEY not in printed and SECRET_VALUE not in printed and "conf.py:2" in printed


def test_empty_repo_and_bad_path(tmp_path, capsys):
    facts = rf.scan(tmp_path)
    assert facts["languages"] == [] and facts["tests"]["ratio"] is None
    assert rf.main([str(tmp_path)]) == 0 and "none" in capsys.readouterr().out
    assert rf.main([str(tmp_path / "missing")]) == 2


def test_oversized_files_and_caps_are_reported(tmp_path, monkeypatch):
    write(tmp_path, "big.py", "x = 1\n" * 10)
    write(tmp_path, "a.py", "y = 2\n")
    monkeypatch.setattr(rf, "MAX_BYTES", 20)
    assert rf.scan(tmp_path)["skipped"]["oversized"] == 1
    monkeypatch.setattr(rf, "MAX_FILES", 1)
    assert rf.scan(tmp_path)["truncated"] is True


def test_symlinks_are_not_followed(tmp_path):
    outside = tmp_path / "outside"
    write(outside, "secret.py", f"password = '{SECRET_VALUE}'\n")
    repo = tmp_path / "repo"
    write(repo, "a.py", "x = 1\n")
    (repo / "link.py").symlink_to(outside / "secret.py")
    assert rf.scan(repo)["secrets"]["count"] == 0


@needs_git
def test_git_repo_honours_gitignore_and_reports_churn(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, ".gitignore", "node_modules/\n*.log\n")
    write(repo, "debug.log", "noise\n")
    git(repo, "init", "-q")
    commit_all(repo, "one")
    write(repo, "src/app.py", "x = 2\n")
    commit_all(repo, "two")
    facts = rf.scan(repo)
    assert facts["churn"][0] == {"file": "src/app.py", "commits": 2}
    assert facts["files_listed"] == 9  # the eight files plus .gitignore; the log and node_modules are ignored
    json.dumps(facts)


@needs_git
def test_churn_is_limited_to_the_scanned_folder(tmp_path):
    write(tmp_path, "top.py", "x = 1\n")
    write(tmp_path, "pkg/inner.py", "y = 1\n")
    git(tmp_path, "init", "-q")
    commit_all(tmp_path, "one")
    assert rf.scan(tmp_path / "pkg")["churn"] == [{"file": "inner.py", "commits": 1}]


@needs_git
def test_committed_vendor_and_build_folders_are_skipped_in_a_git_repo_too(tmp_path):
    write(tmp_path, "src/a.py", "x = 1\n")
    write(tmp_path, "vendor/lib/big.py", "y = 1\n" * 50)
    write(tmp_path, "web/node_modules/x/index.js", "z = 1\n")
    git(tmp_path, "init", "-q")
    commit_all(tmp_path)
    facts = rf.scan(tmp_path)
    assert facts["files_listed"] == 1 and [x["file"] for x in facts["largest"]] == ["src/a.py"]


@needs_git
def test_a_repos_own_fsmonitor_command_is_never_run(tmp_path):
    repo = tmp_path / "repo"
    write(repo, "a.py", "x = 1\n")
    git(repo, "init", "-q")
    commit_all(repo)
    marker = tmp_path / "ran"
    git(repo, "config", "core.fsmonitor", f"touch {marker}; echo")
    write(repo, "a.py", "x = 2\n")
    rf.scan(repo)
    assert not marker.exists()


def test_counts_stay_true_past_the_location_cap(tmp_path, capsys):
    write(
        tmp_path, "keys.py", "".join(f"password{n} = '{SECRET_VALUE}'\n# {TODO}\n" for n in range(rf.MAX_LOCATIONS + 5))
    )
    facts = rf.scan(tmp_path)
    assert facts["secrets"]["count"] == rf.MAX_LOCATIONS + 5 and len(facts["secrets"]["findings"]) == rf.MAX_LOCATIONS
    assert facts["markers"]["counts"] == {TODO: rf.MAX_LOCATIONS + 5}
    rf.main([str(tmp_path)])
    assert capsys.readouterr().out.count("(first 40 shown") == 2


def test_empty_repo_says_n_a_not_none_and_odd_names_do_not_crash(tmp_path, capsys, monkeypatch):
    assert rf.main([str(tmp_path)]) == 0 and "(ratio n/a)" in capsys.readouterr().out
    write(tmp_path, "café.py", "x = 1\n")
    import io

    ascii_out = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    monkeypatch.setattr("sys.stdout", ascii_out)
    assert rf.main([str(tmp_path)]) == 0
    ascii_out.flush()
    assert b"caf?.py" in ascii_out.buffer.getvalue()


@pytest.mark.parametrize(
    "rel,expected",
    [
        ("pkg/foo_test.go", True),
        ("web/app.spec.ts", True),
        ("web/app.test.js", True),
        ("src/FooTest.java", True),
        ("src/FooTests.cs", True),
        ("test_cli.py", True),
        ("spec/models/user.rb", True),
        ("src/latest.py", False),
        ("src/contest.py", False),
        ("src/attest.ts", False),
        ("src/app.py", False),
    ],
)
def test_test_file_detection(rel, expected):
    assert rf.is_test(rel) is expected


def test_secret_shapes_and_their_lengths(tmp_path):
    pk = "-----BEGIN RSA PRIVATE " + "KEY-----"
    pk2 = "-----BEGIN PRIVATE " + "KEY-----"
    lines = [
        pk,
        pk2,
        "t1 = 'ghp_" + "a" * 30 + "'",
        "t2 = 'ghp_" + "a" * 29 + "'",
        "t3 = 'xoxp-" + "1" * 10 + "'",
        "secret = 'abcdefgh'",
        "secret = 'abcdefg'",
        "token = '${TOKEN_VALUE}'",
    ]
    write(tmp_path, "keys.txt", "\n".join(lines) + "\n")
    hits = {s["line"] for s in rf.scan(tmp_path)["secrets"]["findings"]}
    assert hits == {1, 2, 3, 5, 6}


def test_line_counts_and_the_top_ten_lists(tmp_path):
    write(tmp_path, "no_newline.py", "a = 1\n" * 12 + "b = 2")
    for n in range(12):
        write(tmp_path, f"m{n:02}.py", "x = 1\n" * (n + 1))
    facts = rf.scan(tmp_path)
    assert {x["file"]: x["lines"] for x in facts["largest"]}["no_newline.py"] == 13
    assert len(facts["largest"]) == 10 and facts["largest"][1] == {"file": "m11.py", "lines": 12}


def test_a_file_of_exactly_the_size_cap_is_read(tmp_path, monkeypatch):
    write(tmp_path, "edge.py", "x = 1\n")
    monkeypatch.setattr(rf, "MAX_BYTES", 6)
    assert rf.scan(tmp_path)["skipped"]["oversized"] == 0
    monkeypatch.setattr(rf, "MAX_BYTES", 5)
    assert rf.scan(tmp_path)["skipped"]["oversized"] == 1


@needs_git
def test_churn_counts_six_months_only_and_lists_ten(tmp_path, monkeypatch):
    for n in range(12):
        write(tmp_path, f"f{n:02}.py", "x = 1\n")
    git(tmp_path, "init", "-q")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2020-01-01T00:00:00")
    monkeypatch.setenv("GIT_AUTHOR_DATE", "2020-01-01T00:00:00")
    commit_all(tmp_path, "ancient")
    assert rf.scan(tmp_path)["churn"] == []
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    monkeypatch.delenv("GIT_AUTHOR_DATE")
    for n in range(12):
        write(tmp_path, f"f{n:02}.py", "x = 2\n")
    commit_all(tmp_path, "recent")
    assert len(rf.scan(tmp_path)["churn"]) == 10


def test_the_shipped_sample_output_matches_a_real_run():
    """The sample in the skill's examples folder and the README must not drift from the script."""
    facts = rf.scan(Path("examples/demo-shop").resolve())
    facts["root"] = "examples/demo-shop"
    sample = Path("agensi/repo-audit-planner/examples/sample-repo-facts.txt").read_text(encoding="utf-8")
    head = lambda text: text.split("Most-changed files")[0]  # noqa: E731  (history depends on the checkout)
    assert head(rf.render(facts)) == head(sample)
    assert "18 test lines to 36 source lines" in Path("README.md").read_text(encoding="utf-8")
