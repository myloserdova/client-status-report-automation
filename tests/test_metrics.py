from datetime import date

import pytest

from status_report.metrics import build_summary, remaining_hours


def test_all_done_is_green_and_complete(project, make_task):
    tasks = [
        make_task(milestone="Design", status="done", spent_h=10, completed=date(2026, 2, 5)),
        make_task(milestone="Build", status="done", spent_h=10, completed=date(2026, 3, 5)),
    ]
    s = build_summary(project, tasks, date(2026, 3, 10))
    assert s.rag == "Green"
    assert [m.status for m in s.milestones] == ["Complete", "Complete"]
    assert s.progress_pct == 100.0


def test_unfinished_milestone_past_due_is_late_and_red(project, make_task):
    tasks = [make_task(milestone="Design", due=date(2026, 2, 6))]
    s = build_summary(project, tasks, date(2026, 2, 10))
    assert s.milestones[0].status == "Late"
    assert s.rag == "Red"


def test_blocked_task_puts_milestone_at_risk_and_project_amber(project, make_task):
    tasks = [
        make_task(status="blocked", blocked_on="client", blocked_reason="Waiting", due=date(2026, 3, 6)),
    ]
    s = build_summary(project, tasks, date(2026, 2, 16))
    build = next(m for m in s.milestones if m.name == "Build")
    assert build.status == "At risk"
    assert s.rag == "Amber"


def test_low_progress_close_to_due_date_is_at_risk(project, make_task):
    tasks = [
        make_task(status="done", completed=date(2026, 3, 2), estimate_h=2, spent_h=2),
        make_task(status="in_progress", estimate_h=18, spent_h=1, due=date(2026, 3, 6)),
    ]
    s = build_summary(project, tasks, date(2026, 3, 3))
    assert next(m for m in s.milestones if m.name == "Build").status == "At risk"


def test_comfortable_schedule_is_on_track(project, make_task):
    tasks = [make_task(status="in_progress", estimate_h=10, spent_h=2, due=date(2026, 3, 6))]
    s = build_summary(project, tasks, date(2026, 2, 16))
    assert next(m for m in s.milestones if m.name == "Build").status == "On track"
    assert s.rag == "Green"


def test_forecast_far_over_budget_is_red(project, make_task):
    tasks = [make_task(estimate_h=120, due=date(2026, 3, 20))]
    s = build_summary(project, tasks, date(2026, 2, 16))
    assert s.forecast_variance_pct == 20.0
    assert s.rag == "Red"


def test_forecast_slightly_over_budget_is_amber(project, make_task):
    tasks = [make_task(estimate_h=105, due=date(2026, 3, 20))]
    s = build_summary(project, tasks, date(2026, 2, 16))
    assert s.forecast_variance_pct == 5.0
    assert s.rag == "Amber"


def test_progress_is_weighted_by_estimated_hours(project, make_task):
    tasks = [
        make_task(status="done", estimate_h=30, completed=date(2026, 2, 2)),
        make_task(estimate_h=10),
    ]
    assert build_summary(project, tasks, date(2026, 2, 3)).progress_pct == 75.0


def test_remaining_hours_never_negative(make_task):
    assert remaining_hours(make_task(estimate_h=5, spent_h=8)) == 0.0
    assert remaining_hours(make_task(status="done", estimate_h=5, spent_h=2)) == 0.0
    assert remaining_hours(make_task(estimate_h=5, spent_h=2)) == 3.0


def test_overrun_on_open_task_counts_in_forecast(project, make_task):
    tasks = [make_task(estimate_h=5, spent_h=8, due=date(2026, 3, 20))]
    s = build_summary(project, tasks, date(2026, 2, 16))
    assert s.hours_forecast == 8.0


def test_completed_this_week_uses_monday_to_report_date(project, make_task):
    # 2026-02-13 is a Friday, so the report week starts Monday 2026-02-09.
    tasks = [
        make_task(status="done", completed=date(2026, 2, 9)),
        make_task(status="done", completed=date(2026, 2, 13)),
        make_task(status="done", completed=date(2026, 2, 6)),
    ]
    s = build_summary(project, tasks, date(2026, 2, 13))
    assert s.week_start == date(2026, 2, 9)
    assert [t.completed for t in s.completed_this_week] == [date(2026, 2, 9), date(2026, 2, 13)]


def test_coming_up_window_is_today_through_seven_days(project, make_task):
    as_of = date(2026, 2, 13)
    tasks = [
        make_task(id="past", due=date(2026, 2, 12)),
        make_task(id="today", due=as_of),
        make_task(id="edge", due=date(2026, 2, 20)),
        make_task(id="later", due=date(2026, 2, 21)),
        make_task(id="done", due=date(2026, 2, 16), status="done", completed=date(2026, 2, 12)),
    ]
    s = build_summary(project, tasks, as_of)
    assert [t.id for t in s.coming_up] == ["today", "edge"]
    assert [t.id for t in s.overdue] == ["past"]


def test_workload_flags_overloaded_people(project, make_task):
    as_of = date(2026, 2, 13)
    tasks = [
        make_task(assignee="Bob", estimate_h=40, due=date(2026, 2, 18)),
        make_task(assignee="Bob", estimate_h=50, due=date(2026, 3, 30)),  # beyond the horizon, ignored
        make_task(assignee="Ann", estimate_h=10, due=date(2026, 2, 18)),
    ]
    rows = {w.name: w for w in build_summary(project, tasks, as_of).workload}
    assert rows["Bob"].open_hours == 40
    assert rows["Bob"].status == "Overloaded"
    assert rows["Ann"].status == "OK"


def test_workload_near_capacity(project, make_task):
    tasks = [make_task(assignee="Ann", estimate_h=18, due=date(2026, 2, 18))]  # 90% of 20h
    rows = {w.name: w for w in build_summary(project, tasks, date(2026, 2, 13)).workload}
    assert rows["Ann"].status == "Near capacity"


def test_workload_ignores_done_tasks(project, make_task):
    tasks = [make_task(assignee="Bob", estimate_h=40, due=date(2026, 2, 18), status="done", completed=date(2026, 2, 12))]
    rows = {w.name: w for w in build_summary(project, tasks, date(2026, 2, 13)).workload}
    assert rows["Bob"].open_hours == 0


def test_empty_milestone_does_not_crash(project, make_task):
    s = build_summary(project, [make_task(milestone="Build")], date(2026, 2, 13))
    design = next(m for m in s.milestones if m.name == "Design")
    assert design.tasks_total == 0
    assert design.progress_pct == 0.0
    assert design.status == "On track"


@pytest.mark.parametrize("variance_hours, expected", [(100, "Green"), (110, "Amber"), (111, "Red")])
def test_budget_thresholds(project, make_task, variance_hours, expected):
    tasks = [make_task(estimate_h=variance_hours, due=date(2026, 3, 20))]
    assert build_summary(project, tasks, date(2026, 2, 16)).rag == expected
