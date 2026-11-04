from datetime import date
from pathlib import Path

import pytest

from status_report.cli import main
from status_report.loader import load_project, load_tasks
from status_report.metrics import build_summary

DATA = Path(__file__).resolve().parents[1] / "data"
AS_OF = date(2026, 11, 6)


@pytest.fixture(scope="module")
def summary():
    project = load_project(DATA / "project.json")
    return build_summary(project, load_tasks(DATA / "tasks.csv", project), AS_OF)


def test_demo_story_is_stable(summary):
    """The demo data is built to tell one clear story; lock it in."""
    assert summary.rag == "Amber"
    assert {m.name: m.status for m in summary.milestones} == {
        "Discovery & Sitemap": "Complete",
        "UX/UI Design": "Complete",
        "Core Development": "At risk",
        "Content & SEO": "On track",
        "QA & Launch": "On track",
    }
    assert (summary.tasks_done, summary.tasks_total) == (14, 31)
    assert summary.progress_pct == pytest.approx(45.7, abs=0.1)
    assert summary.hours_spent == 236
    assert summary.hours_forecast == 403
    assert 3.0 < summary.forecast_variance_pct < 4.0
    assert [t.id for t in summary.completed_this_week] == ["T-019", "T-012", "T-014"]
    assert [t.id for t in summary.blocked] == ["T-016", "T-018"]
    assert [t.id for t in summary.overdue] == ["T-016"]


def test_demo_workload_highlights_one_overloaded_developer(summary):
    status = {w.name: w.status for w in summary.workload}
    assert status["Iryna Petrenko"] == "Overloaded"
    assert status["Marek Nowak"] == "OK"


def test_cli_writes_all_reports(tmp_path, capsys):
    code = main(["--data-dir", str(DATA), "--out-dir", str(tmp_path), "--as-of", "2026-11-06"])
    assert code == 0
    assert {p.name for p in tmp_path.iterdir()} == {
        "client_status_2026-11-06.md",
        "client_status_2026-11-06.html",
        "team_workload_2026-11-06.md",
    }
    assert "Overall status: Amber" in capsys.readouterr().out


def test_cli_validate_only_writes_nothing(tmp_path):
    code = main(["--data-dir", str(DATA), "--out-dir", str(tmp_path / "out"), "--validate-only"])
    assert code == 0
    assert not (tmp_path / "out").exists()


def test_cli_reports_data_errors_without_a_traceback(tmp_path, capsys):
    (tmp_path / "project.json").write_text("{not json", encoding="utf-8")
    assert main(["--data-dir", str(tmp_path), "--validate-only"]) == 2
    assert "invalid JSON" in capsys.readouterr().err


def test_cli_rejects_a_malformed_date():
    with pytest.raises(SystemExit) as exc:
        main(["--as-of", "06/11/2026"])
    assert exc.value.code == 2
