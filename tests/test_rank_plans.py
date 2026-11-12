import json

import rank_plans as rp
from helpers import write


def plan(root, number, severity, effort, status="todo", depends=""):
    fields = {"id": number, "title": f"Plan {number}", "severity": severity, "effort": effort, "status": status}
    front = "---\n" + "".join(f"{k}: {v}\n" for k, v in fields.items()) + f"depends_on: [{depends}]\n---\n"
    write(root, f"{number}-plan.md", front)


def order(root):
    return [p["id"] for p in rp.rank(root)]


def test_critical_first_then_priority_then_closed_last(tmp_path):
    plan(tmp_path, "001", "low", "XS")  # priority 1
    plan(tmp_path, "002", "high", "S")  # priority 4
    plan(tmp_path, "003", "critical", "XL")  # priority 1.25 but critical
    plan(tmp_path, "004", "high", "XS", status="done")  # closed
    plan(tmp_path, "005", "medium", "M")  # priority 0.75
    assert order(tmp_path) == ["003", "002", "001", "005", "004"]


def test_a_plan_never_precedes_an_open_dependency(tmp_path):
    plan(tmp_path, "001", "high", "XS", depends="002")
    plan(tmp_path, "002", "low", "L")
    assert order(tmp_path) == ["002", "001"]
    plan(tmp_path, "002", "low", "L", status="done")
    assert order(tmp_path) == ["001", "002"]


def test_cycles_and_bad_values_do_not_hang_or_crash(tmp_path):
    plan(tmp_path, "001", "high", "S", depends="002")
    plan(tmp_path, "002", "weird", "huge", depends="001")
    write(tmp_path, "notes.md", "not a plan")
    assert sorted(order(tmp_path)) == ["001", "002"]


def test_cli_output_and_exit_codes(tmp_path, capsys):
    assert rp.main([str(tmp_path)]) == 1
    plan(tmp_path, "001", "high", "S")
    capsys.readouterr()
    assert rp.main([str(tmp_path)]) == 0
    assert "| 1 | 001 | Plan 001 | high | S | 4 | todo |" in capsys.readouterr().out
    assert rp.main([str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["priority"] == 4
    assert rp.main([str(tmp_path / "missing")]) == 2


def test_a_folder_named_like_a_plan_is_skipped_and_bad_values_are_reported(tmp_path, capsys):
    (tmp_path / "009-folder.md").mkdir()
    plan(tmp_path, "001", "urgent", "S")
    assert rp.main([str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert "001-plan.md: severity or effort is not valid" in captured.err and "009" in captured.out


def test_comments_after_values_and_a_byte_order_mark_are_ignored(tmp_path):
    front = (
        "﻿---\nid: 001\ntitle: Fix issue #12\nseverity: high   # one of four\neffort: S # XS to XL\nstatus: todo\n---\n"
    )
    write(tmp_path, "001-plan.md", front)
    (ranked,) = rp.rank(tmp_path)
    assert (ranked["severity"], ranked["effort"], ranked["priority"], ranked["title"]) == (
        "high",
        "S",
        4,
        "Fix issue #12",
    )


def test_a_title_the_console_cannot_show_does_not_crash(tmp_path, monkeypatch, capsys):
    plan(tmp_path, "001", "high", "S")
    write(tmp_path, "002-plan.md", "---\nid: 002\ntitle: café\nseverity: low\neffort: XS\nstatus: todo\n---\n")
    import io

    ascii_out = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    monkeypatch.setattr("sys.stdout", ascii_out)
    assert rp.main([str(tmp_path)]) == 0
    ascii_out.flush()
    assert b"caf?" in ascii_out.buffer.getvalue()


def test_dropped_plans_are_closed_too(tmp_path):
    plan(tmp_path, "001", "critical", "XS", status="dropped")
    plan(tmp_path, "002", "low", "XL")
    plan(tmp_path, "003", "high", "S", depends="001")
    assert order(tmp_path) == ["003", "002", "001"]
