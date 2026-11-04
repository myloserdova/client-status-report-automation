import csv
from pathlib import Path

import pytest

from status_report.loader import TASK_COLUMNS, DataError, load_project, load_tasks

DATA = Path(__file__).resolve().parents[1] / "data"


def _row(**overrides):
    row = dict(
        id="T-1",
        title="Something",
        milestone="Build",
        assignee="Bob",
        status="todo",
        priority="medium",
        estimate_h="4",
        spent_h="0",
        due="2026-03-01",
        completed="",
        blocked_on="",
        blocked_reason="",
    )
    row.update(overrides)
    return row


def _write(tmp_path, rows):
    path = tmp_path / "tasks.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TASK_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_demo_data_loads():
    project = load_project(DATA / "project.json")
    tasks = load_tasks(DATA / "tasks.csv", project)
    assert len(tasks) == 31
    assert len(project.milestones) == 5


def test_valid_row_is_accepted(tmp_path, project):
    tasks = load_tasks(_write(tmp_path, [_row()]), project)
    assert tasks[0].estimate_h == 4.0


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"assignee": "Nobody"}, "unknown assignee"),
        ({"milestone": "Nope"}, "unknown milestone"),
        ({"status": "finished"}, "status"),
        ({"due": "03/01/2026"}, "not a valid date"),
        ({"estimate_h": "abc"}, "not a number"),
        ({"spent_h": "-1"}, "cannot be negative"),
        ({"status": "done"}, "no completion date"),
        ({"completed": "2026-02-01"}, "not done"),
        ({"status": "blocked"}, "blocked_on"),
        ({"status": "blocked", "blocked_on": "client"}, "blocked_reason"),
    ],
)
def test_bad_rows_are_rejected_with_a_clear_message(tmp_path, project, overrides, message):
    path = _write(tmp_path, [_row(**overrides)])
    with pytest.raises(DataError, match=message) as exc:
        load_tasks(path, project)
    assert "line 2" in str(exc.value)


def test_duplicate_ids_are_rejected(tmp_path, project):
    path = _write(tmp_path, [_row(), _row()])
    with pytest.raises(DataError, match="duplicate task id"):
        load_tasks(path, project)


def test_missing_column_is_reported(tmp_path, project):
    path = tmp_path / "tasks.csv"
    path.write_text("id,title\nT-1,x\n", encoding="utf-8")
    with pytest.raises(DataError, match="missing column"):
        load_tasks(path, project)


def test_missing_file_is_reported(tmp_path, project):
    with pytest.raises(DataError, match="File not found"):
        load_tasks(tmp_path / "nope.csv", project)


def test_project_missing_field_is_reported(tmp_path):
    path = tmp_path / "project.json"
    path.write_text('{"name": "X"}', encoding="utf-8")
    with pytest.raises(DataError, match="missing field"):
        load_project(path)


def test_project_end_must_follow_start(tmp_path):
    text = (DATA / "project.json").read_text(encoding="utf-8").replace('"end": "2026-12-11"', '"end": "2026-01-01"')
    path = tmp_path / "project.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(DataError, match="after 'start'"):
        load_project(path)
