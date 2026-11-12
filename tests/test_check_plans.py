import json
from pathlib import Path

import check_plans as cp
import pytest
from helpers import APP_PY, GOOD_PLAN, NAME, commit_all, git, needs_git, with_replacement, without_section, write


def run(capsys, tmp_path, text=GOOD_PLAN, repo=None, name=NAME, extra=None):
    write(tmp_path / "plans", name, text)
    for other, body in (extra or {}).items():
        write(tmp_path / "plans", other, body)
    argv = [str(tmp_path / "plans"), "--json"] + (["--repo", str(repo)] if repo else [])
    code = cp.main(argv)
    return code, json.loads(capsys.readouterr().out)


def codes(report, index=0):
    return [f["code"] for f in report["plans"][index]["findings"]]


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    write(root, "src/app.py", APP_PY)
    return root


def test_good_plan_passes_with_and_without_a_repo(capsys, tmp_path, repo):
    assert run(capsys, tmp_path)[0] == 0
    code, report = run(capsys, tmp_path, repo=repo)
    assert code == 0 and report["errors"] == 0


def test_the_shipped_example_plan_passes_against_this_repo(capsys):
    assert cp.main(["examples", "--repo", "."]) == 0
    assert "0 error(s), 0 warning(s)" in capsys.readouterr().out


@pytest.mark.parametrize(
    "old,new,code",
    [
        ("id: 001", "id: 002", "front-matter"),
        ("severity: high", "severity: urgent", "front-matter"),
        ("effort: S", "effort: tiny", "front-matter"),
        ("status: todo", "status: wip", "front-matter"),
        ("depends_on: []", "depends_on: [007]", "depends-on"),
        ("`load_config` parses the file once", "{{say what changes}}", "placeholder"),
        ("parses the file once per process", "parses the file properly", "vague"),
        ("parses the file once per process", "parses it as  needed", "vague"),
        ("   Verify: `pytest -q` prints `2 passed`.\n", "", "step-no-verify"),
        ("1. Edit `src/app.py`", "Edit `src/app.py`", "steps"),
        ("- [ ] `pytest -q` exits 0.", "- pytest passes", "acceptance"),
        ("```sh\npytest -q\n```\n", "Run pytest.\n", "tests"),
        ("### Out of scope\n", "### Later\n", "subsection-missing"),
        ("### Rollback\n", "### Undo\n", "subsection-missing"),
        ("- `src/app.py:6` `data = json.load(open(PATH))` -", "- the loader is slow -", "evidence-missing"),
    ],
)
def test_each_defect_is_an_error(capsys, tmp_path, old, new, code):
    exit_code, report = run(capsys, tmp_path, with_replacement(GOOD_PLAN, old, new))
    assert exit_code == 1 and code in codes(report)


@pytest.mark.parametrize(
    "section", ["Goal", "Evidence", "Context", "Scope", "Steps", "Acceptance criteria", "Test commands"]
)
def test_missing_or_empty_required_section_fails(capsys, tmp_path, section):
    exit_code, report = run(capsys, tmp_path, without_section(GOOD_PLAN, section))
    assert exit_code == 1 and "section-missing" in codes(report)
    emptied = without_section(GOOD_PLAN, section).rstrip("\n") + f"\n\n## {section}\n\n<!-- nothing yet -->\n"
    exit_code, report = run(capsys, tmp_path, emptied)
    assert exit_code == 1 and "section-empty" in codes(report)


def test_missing_halt_conditions_only_warns(capsys, tmp_path):
    exit_code, report = run(capsys, tmp_path, without_section(GOOD_PLAN, "Halt conditions"))
    assert exit_code == 0 and report["warnings"] == 1


def test_template_syntax_in_code_is_not_a_placeholder(capsys, tmp_path):
    text = GOOD_PLAN + "\nCI uses `${{ github.ref }}` and:\n\n```yaml\nname: {{ item }}\n```\n"
    assert run(capsys, tmp_path, text)[0] == 0


def test_no_front_matter_and_binary_files_fail_cleanly(capsys, tmp_path):
    exit_code, report = run(capsys, tmp_path, GOOD_PLAN.split("---\n", 2)[2])
    assert exit_code == 1 and "front-matter" in codes(report)
    write(tmp_path / "plans", "002-binary.md", b"\xff\xfe\x00bad")
    cp.main([str(tmp_path / "plans")])
    assert "not readable" in capsys.readouterr().out


def test_empty_folder_misnamed_files_and_duplicates_fail(capsys, tmp_path):
    (tmp_path / "empty").mkdir()
    assert cp.main([str(tmp_path / "empty")]) == 1
    assert "no plan files" in capsys.readouterr().out
    exit_code, report = run(
        capsys, tmp_path, extra={"plan-1.md": "x", "001-other-thing.md": GOOD_PLAN, "README.md": "notes"}
    )
    found = {p["file"]: [f["code"] for f in p["findings"]] for p in report["plans"]}
    assert exit_code == 1 and found["plan-1.md"] == ["misnamed"] and "README.md" not in found
    assert "duplicate-number" in found[NAME] and "duplicate-number" in found["001-other-thing.md"]


def test_usage_errors_exit_two(tmp_path):
    assert cp.main([str(tmp_path / "missing")]) == 2
    (tmp_path / "plans").mkdir()
    assert cp.main([str(tmp_path / "plans"), "--repo", str(tmp_path / "nope")]) == 2


@pytest.mark.parametrize(
    "new,code",
    [
        ("`src/app.py:6` `data = yaml.load(open(PATH))`", "evidence-quote"),
        ("`src/app.py:6`", "evidence-no-quote"),
        ("`src/app.py:99` `data = json.load(open(PATH))`", "evidence-unresolved"),
        ("`src/gone.py:6` `data = json.load(open(PATH))`", "evidence-unresolved"),
        ("`../outside.py:1` `secret = 1`", "evidence-unresolved"),
    ],
)
def test_invented_or_stale_evidence_fails_against_the_repo(capsys, tmp_path, repo, new, code):
    write(tmp_path, "outside.py", "secret = 1\n")
    text = with_replacement(GOOD_PLAN, "`src/app.py:6` `data = json.load(open(PATH))`", new)
    exit_code, report = run(capsys, tmp_path, text, repo=repo)
    assert exit_code == 1 and code in codes(report)


def test_quote_may_span_a_range_and_ignores_spacing(capsys, tmp_path, repo):
    text = with_replacement(
        GOOD_PLAN,
        "`src/app.py:6` `data = json.load(open(PATH))`",
        "`src/app.py:5-7` `data  =  json.load(open(PATH)) return data`",
    )
    assert run(capsys, tmp_path, text, repo=repo)[0] == 0


def test_redacted_quote_matches_around_the_secret(capsys, tmp_path, repo):
    write(repo, "src/conf.py", 'API_KEY = "abc123secret"\n')
    old = "`src/app.py:6` `data = json.load(open(PATH))`"
    good = with_replacement(GOOD_PLAN, old, '`src/conf.py:1` `API_KEY = "[REDACTED]"`')
    assert run(capsys, tmp_path, good, repo=repo)[0] == 0
    bad = with_replacement(GOOD_PLAN, old, '`src/conf.py:1` `TOKEN = "[REDACTED]"`')
    assert "evidence-quote" in codes(run(capsys, tmp_path, bad, repo=repo)[1])


def test_done_plan_skips_repo_checks(capsys, tmp_path, repo):
    text = with_replacement(GOOD_PLAN, "data = json.load(open(PATH))", "data = changed_later()")
    assert run(capsys, tmp_path, with_replacement(text, "status: todo", "status: done"), repo=repo)[0] == 0


@needs_git
def test_drift_since_base_commit_is_a_warning(capsys, tmp_path, repo):
    git(repo, "init", "-q")
    base = commit_all(repo, "base")
    write(repo, "src/app.py", APP_PY + "\n# later\n")
    commit_all(repo, "later")
    exit_code, report = run(
        capsys, tmp_path, with_replacement(GOOD_PLAN, "base_commit: abc1234", f"base_commit: {base}"), repo=repo
    )
    assert exit_code == 0 and codes(report) == ["drift"]


def test_text_output_names_the_failing_plan(capsys, tmp_path):
    write(tmp_path / "plans", NAME, without_section(GOOD_PLAN, "Goal"))
    assert cp.main([str(tmp_path / "plans")]) == 1
    out = capsys.readouterr().out
    assert f"FAIL  {NAME}" in out and "[section-missing]" in out


OLD_EVIDENCE = "`src/app.py:6` `data = json.load(open(PATH))`"


def test_a_quote_that_is_only_the_redaction_marker_proves_nothing(capsys, tmp_path, repo):
    for cited in ("src/app.py:6", "src/app.py:8"):  # APP_PY has 7 lines; 8 is the empty piece after the last newline
        text = with_replacement(GOOD_PLAN, OLD_EVIDENCE, f"`{cited}` `[REDACTED]`")
        exit_code, report = run(capsys, tmp_path, text, repo=repo)
        assert exit_code == 1 and codes(report)[0] in ("evidence-quote", "evidence-unresolved")


def test_line_numbers_count_real_lines_only(capsys, tmp_path, repo):
    text = with_replacement(GOOD_PLAN, OLD_EVIDENCE, "`src/app.py:8` `data`")
    _, report = run(capsys, tmp_path, text, repo=repo)
    assert "the file has 7 lines" in report["plans"][0]["findings"][0]["message"]


def test_a_cited_folder_or_oversized_file_is_an_error_not_a_hang(capsys, tmp_path, repo, monkeypatch):
    folder = with_replacement(GOOD_PLAN, OLD_EVIDENCE, "`src:1` `data`")
    assert "evidence-unresolved" in codes(run(capsys, tmp_path, folder, repo=repo)[1])
    monkeypatch.setattr(cp, "MAX_CITED_BYTES", 10)
    assert "over 5 MB" in run(capsys, tmp_path, repo=repo)[1]["plans"][0]["findings"][0]["message"]


def test_byte_order_mark_and_front_matter_comments_are_accepted(capsys, tmp_path):
    text = with_replacement(GOOD_PLAN, "severity: high", "severity: high   # critical | high | medium | low")
    text = with_replacement(text, "title: Cache the parsed config", "title: Fix issue #12")
    write(tmp_path / "plans", NAME, "﻿" + text)
    assert cp.main([str(tmp_path / "plans")]) == 0
    assert "0 error(s)" in capsys.readouterr().out


def test_depends_on_entries_must_be_plan_numbers_without_cycles(capsys, tmp_path):
    other = with_replacement(GOOD_PLAN, "id: 001", "id: 002")
    sibling = {"002-other.md": with_replacement(other, "depends_on: []", "depends_on: [001]")}
    ok = with_replacement(GOOD_PLAN, "depends_on: []", "depends_on: [002]")
    exit_code, report = run(capsys, tmp_path, ok, extra={"002-other.md": other})
    assert exit_code == 0 and report["errors"] == 0
    exit_code, report = run(capsys, tmp_path, ok, extra=sibling)
    messages = [f["message"] for p in report["plans"] for f in p["findings"]]
    assert exit_code == 1 and sum("a cycle" in m for m in messages) == 2
    bad = with_replacement(GOOD_PLAN, "depends_on: []", "depends_on: [1]")
    assert any("not a plan number" in f["message"] for f in run(capsys, tmp_path, bad)[1]["plans"][0]["findings"])


def test_code_fences_close_only_on_a_matching_fence(capsys, tmp_path):
    nested = GOOD_PLAN.replace("```sh\npytest -q\n```", "````md\n```sh\npytest -q\n```\n````")
    assert run(capsys, tmp_path, nested)[0] == 0
    unclosed = GOOD_PLAN.replace("```sh\npytest -q\n```", "```sh\npytest -q\n~~~")
    exit_code, report = run(capsys, tmp_path, unclosed)
    assert exit_code == 1 and "fence" in codes(report)


@needs_git
def test_drift_is_found_when_repo_is_a_subfolder_or_the_change_is_uncommitted(capsys, tmp_path):
    root = tmp_path / "mono"
    write(root, "svc/src/app.py", APP_PY)
    git(root, "init", "-q")
    base = commit_all(root, "base")
    text = with_replacement(GOOD_PLAN, "base_commit: abc1234", f"base_commit: {base}")
    assert codes(run(capsys, tmp_path, text, repo=root / "svc")[1]) == []
    write(root, "svc/src/app.py", APP_PY + "\n# uncommitted\n")
    assert codes(run(capsys, tmp_path, text, repo=root / "svc")[1]) == ["drift"]


@needs_git
def test_a_base_commit_that_git_cannot_find_warns(capsys, tmp_path, repo):
    git(repo, "init", "-q")
    commit_all(repo, "base")
    exit_code, report = run(capsys, tmp_path, repo=repo)  # GOOD_PLAN says abc1234, which is not in this history
    assert exit_code == 0 and codes(report) == ["drift"]
    assert "cannot be compared" in report["plans"][0]["findings"][0]["message"]


@needs_git
def test_a_repos_own_fsmonitor_command_is_never_run(capsys, tmp_path, repo):
    git(repo, "init", "-q")
    base = commit_all(repo, "base")
    marker = tmp_path / "ran"
    git(repo, "config", "core.fsmonitor", f"touch {marker}; echo")
    write(repo, "src/app.py", APP_PY + "\n# later\n")
    run(capsys, tmp_path, with_replacement(GOOD_PLAN, "base_commit: abc1234", f"base_commit: {base}"), repo=repo)
    assert not marker.exists()


@pytest.mark.parametrize("phrase", cp.VAGUE)
def test_every_vague_phrase_is_caught_in_a_step(capsys, tmp_path, phrase):
    text = with_replacement(GOOD_PLAN, "wrap `load_config`", f"{phrase} wrap `load_config`")
    exit_code, report = run(capsys, tmp_path, text)
    assert exit_code == 1 and "vague" in codes(report)


@pytest.mark.parametrize(
    "key,values",
    [
        ("severity: high", ["critical", "high", "medium", "low"]),
        ("effort: S", ["XS", "S", "M", "L", "XL"]),
        ("status: todo", ["todo", "in-progress", "blocked", "done", "dropped"]),
    ],
)
def test_every_allowed_front_matter_value_is_accepted(capsys, tmp_path, key, values):
    for value in values:
        text = with_replacement(GOOD_PLAN, key, f"{key.split(':')[0]}: {value}")
        assert run(capsys, tmp_path, text)[0] == 0, value


def test_small_defects_each_have_their_own_finding(capsys, tmp_path, repo):
    own = with_replacement(GOOD_PLAN, "depends_on: []", "depends_on: [001]")
    assert any(
        "this plan or does not exist" in f["message"] for f in run(capsys, tmp_path, own)[1]["plans"][0]["findings"]
    )
    assert "front-matter" in codes(
        run(capsys, tmp_path, with_replacement(GOOD_PLAN, "title: Cache the parsed config", "title:"))[1]
    )
    zero = with_replacement(GOOD_PLAN, OLD_EVIDENCE, "`src/app.py:0` `import json`")
    assert "evidence-unresolved" in codes(run(capsys, tmp_path, zero, repo=repo)[1])
    no_expected = with_replacement(GOOD_PLAN, "Expected: exit code 0 and `2 passed`.", "It should pass.")
    exit_code, report = run(capsys, tmp_path, no_expected)
    assert exit_code == 0 and report["warnings"] == 1
    dropped = with_replacement(GOOD_PLAN, "status: todo", "status: dropped").replace("data = json.load", "data = gone")
    assert run(capsys, tmp_path, dropped, repo=repo)[0] == 0


def test_github_expression_syntax_in_plain_prose_is_not_a_placeholder(capsys, tmp_path):
    assert (
        run(
            capsys,
            tmp_path,
            with_replacement(GOOD_PLAN, "## Context\n\n", "## Context\n\nCI sets ${{ github.ref }} in prose. "),
        )[0]
        == 0
    )
    assert "placeholder" in codes(
        run(capsys, tmp_path, with_replacement(GOOD_PLAN, "## Context\n\n", "## Context\n\nFill {{this}} in. "))[1]
    )


def test_redacted_quote_parts_must_appear_in_order(capsys, tmp_path, repo):
    write(repo, "src/conf.py", 'KEY = "abc123secret" # prod\n')
    ok = with_replacement(GOOD_PLAN, OLD_EVIDENCE, '`src/conf.py:1` `KEY = "[REDACTED]" # prod`')
    assert run(capsys, tmp_path, ok, repo=repo)[0] == 0
    wrong_order = with_replacement(GOOD_PLAN, OLD_EVIDENCE, "`src/conf.py:1` `# prod [REDACTED] KEY`")
    assert "evidence-quote" in codes(run(capsys, tmp_path, wrong_order, repo=repo)[1])


def test_a_path_with_spaces_can_be_cited(capsys, tmp_path, repo):
    write(repo, "my docs/setup notes.md", "run `make all`\n")
    text = with_replacement(GOOD_PLAN, OLD_EVIDENCE, "`my docs/setup notes.md:1` `run`")
    assert run(capsys, tmp_path, text, repo=repo)[0] == 0


def test_the_template_heading_must_get_its_plan_number(capsys, tmp_path):
    text = with_replacement(GOOD_PLAN, "# 001: Cache the parsed config", "# NNN: Cache the parsed config")
    assert "placeholder" in codes(run(capsys, tmp_path, text)[1])


def test_the_shipped_template_fails_until_it_is_filled_in(capsys, tmp_path):
    template = Path("agensi/repo-audit-planner/references/plan-template.md").read_text(encoding="utf-8")
    exit_code, report = run(capsys, tmp_path, template)
    assert exit_code == 1 and codes(report).count("placeholder") >= 10


def test_usage_errors_say_which_folder_is_wrong(capsys, tmp_path):
    assert cp.main([str(tmp_path / "missing")]) == 2
    assert "PLANS_DIR is not an existing directory" in capsys.readouterr().err
    (tmp_path / "plans").mkdir()
    assert cp.main([str(tmp_path / "plans"), "--repo", str(tmp_path / "nope")]) == 2
    assert "--repo is not an existing directory" in capsys.readouterr().err


def test_a_wrong_repo_root_is_explained_once_per_plan(capsys, tmp_path, repo):
    text = with_replacement(GOOD_PLAN, "`src/app.py:6`", "`app.py:6`")
    text = with_replacement(text, "- `app.py:6` `data = json.load(open(PATH))` - the file is opened and parsed on every call.",
                            "- `app.py:6` `data = json.load(open(PATH))` - the file is opened and parsed on every call.\n"
                            "- `app.py:7` `return data` - second cite")
    exit_code, report = run(capsys, tmp_path, text, repo=repo)
    messages = [f["message"] for f in report["plans"][0]["findings"] if f["code"] == "evidence-unresolved"]
    assert exit_code == 1 and len(messages) == 2
    assert sum("--repo must be the folder" in m for m in messages) == 1
