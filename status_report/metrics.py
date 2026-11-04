"""Turn validated tasks into the numbers and status flags a report needs.

All rules live here as named constants, so "what does Amber mean?" has one
documented answer (see the README) instead of living in someone's head.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .loader import Project, Task

# Milestone statuses
COMPLETE, ON_TRACK, AT_RISK, LATE = "Complete", "On track", "At risk", "Late"
# Overall RAG statuses
GREEN, AMBER, RED = "Green", "Amber", "Red"
# Workload statuses
OK, NEAR_CAPACITY, OVERLOADED = "OK", "Near capacity", "Overloaded"

AT_RISK_WINDOW_DAYS = 7  # a milestone due within this many days...
AT_RISK_PROGRESS_PCT = 80.0  # ...and below this progress is "At risk"
FORECAST_RED_PCT = 10.0  # forecast this far over budget turns the project Red
HORIZON_DAYS = 7  # "coming up" and workload look this many days ahead
NEAR_CAPACITY_PCT = 85.0

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class MilestoneProgress:
    name: str
    due: date
    status: str
    progress_pct: float
    tasks_total: int
    tasks_done: int
    overdue: int
    blocked: int


@dataclass(frozen=True)
class WorkloadRow:
    name: str
    role: str
    open_hours: float
    capacity_h: float
    utilization_pct: float
    status: str


@dataclass(frozen=True)
class Summary:
    as_of: date
    week_start: date
    horizon: date
    rag: str
    rag_reasons: tuple[str, ...]
    progress_pct: float
    tasks_total: int
    tasks_done: int
    hours_spent: float
    hours_budget: float
    hours_forecast: float
    forecast_variance_pct: float
    days_to_end: int
    milestones: tuple[MilestoneProgress, ...]
    completed_this_week: tuple[Task, ...]
    coming_up: tuple[Task, ...]
    overdue: tuple[Task, ...]
    blocked: tuple[Task, ...]
    workload: tuple[WorkloadRow, ...]


def _pct(part: float, whole: float) -> float:
    return 0.0 if whole <= 0 else round(100.0 * part / whole, 1)


def remaining_hours(task: Task) -> float:
    """Hours still to spend. Overruns never count as negative remaining work."""
    return 0.0 if task.status == "done" else max(task.estimate_h - task.spent_h, 0.0)


def is_overdue(task: Task, as_of: date) -> bool:
    return task.status != "done" and task.due < as_of


def _milestone_progress(name: str, due: date, tasks: list[Task], as_of: date) -> MilestoneProgress:
    total = len(tasks)
    done = sum(t.status == "done" for t in tasks)
    progress = _pct(sum(t.estimate_h for t in tasks if t.status == "done"), sum(t.estimate_h for t in tasks))
    overdue = sum(is_overdue(t, as_of) for t in tasks)
    blocked = sum(t.status == "blocked" for t in tasks)
    days_left = (due - as_of).days

    if total == 0:
        status = ON_TRACK  # nothing planned, so nothing can be late
    elif done == total:
        status = COMPLETE
    elif due < as_of:
        status = LATE
    elif overdue or blocked or (days_left <= AT_RISK_WINDOW_DAYS and progress < AT_RISK_PROGRESS_PCT):
        status = AT_RISK
    else:
        status = ON_TRACK
    return MilestoneProgress(name, due, status, progress, total, done, overdue, blocked)


def _rag(
    milestones: tuple[MilestoneProgress, ...],
    variance_pct: float,
    overdue: list[Task],
    blocked: list[Task],
) -> tuple[str, tuple[str, ...]]:
    red: list[str] = []
    amber: list[str] = []
    for m in milestones:
        if m.status == LATE:
            red.append(f"Milestone '{m.name}' is past its due date")
        elif m.status == AT_RISK:
            amber.append(f"Milestone '{m.name}' is at risk")
    if variance_pct > FORECAST_RED_PCT:
        red.append(f"Forecast hours exceed the budget by {variance_pct:.1f}%")
    elif variance_pct > 0:
        amber.append(f"Forecast hours exceed the budget by {variance_pct:.1f}%")
    if overdue:
        amber.append(f"{len(overdue)} overdue {'task' if len(overdue) == 1 else 'tasks'}")
    if blocked:
        amber.append(f"{len(blocked)} blocked {'task' if len(blocked) == 1 else 'tasks'}")

    if red:
        return RED, tuple(red + amber)
    if amber:
        return AMBER, tuple(amber)
    return GREEN, ("All milestones are on track and the forecast is within budget",)


def _workload(project: Project, tasks: list[Task], horizon: date) -> tuple[WorkloadRow, ...]:
    rows = []
    for member in project.team:
        hours = sum(
            remaining_hours(t)
            for t in tasks
            if t.assignee == member.name and t.status != "done" and t.due <= horizon
        )
        utilization = _pct(hours, member.weekly_capacity_h)
        if utilization > 100:
            status = OVERLOADED
        elif utilization >= NEAR_CAPACITY_PCT:
            status = NEAR_CAPACITY
        else:
            status = OK
        rows.append(WorkloadRow(member.name, member.role, hours, member.weekly_capacity_h, utilization, status))
    return tuple(rows)


def build_summary(project: Project, tasks: list[Task], as_of: date) -> Summary:
    week_start = as_of - timedelta(days=as_of.weekday())  # Monday of the report week
    horizon = as_of + timedelta(days=HORIZON_DAYS)

    milestones = tuple(
        _milestone_progress(m.name, m.due, [t for t in tasks if t.milestone == m.name], as_of)
        for m in project.milestones
    )

    open_tasks = [t for t in tasks if t.status != "done"]
    overdue = sorted((t for t in open_tasks if is_overdue(t, as_of)), key=lambda t: (t.due, t.id))
    blocked = sorted(
        (t for t in tasks if t.status == "blocked"),
        key=lambda t: (PRIORITY_ORDER[t.priority], t.due, t.id),
    )
    completed = sorted(
        (t for t in tasks if t.status == "done" and t.completed and week_start <= t.completed <= as_of),
        key=lambda t: (t.completed, t.id),
    )
    coming_up = sorted(
        (t for t in open_tasks if as_of <= t.due <= horizon),
        key=lambda t: (t.due, PRIORITY_ORDER[t.priority], t.id),
    )

    hours_spent = sum(t.spent_h for t in tasks)
    hours_forecast = hours_spent + sum(remaining_hours(t) for t in tasks)
    variance = round(100.0 * (hours_forecast - project.budget_hours) / project.budget_hours, 1)
    rag, reasons = _rag(milestones, variance, overdue, blocked)

    return Summary(
        as_of=as_of,
        week_start=week_start,
        horizon=horizon,
        rag=rag,
        rag_reasons=reasons,
        progress_pct=_pct(
            sum(t.estimate_h for t in tasks if t.status == "done"), sum(t.estimate_h for t in tasks)
        ),
        tasks_total=len(tasks),
        tasks_done=sum(t.status == "done" for t in tasks),
        hours_spent=hours_spent,
        hours_budget=project.budget_hours,
        hours_forecast=hours_forecast,
        forecast_variance_pct=variance,
        days_to_end=(project.end - as_of).days,
        milestones=milestones,
        completed_this_week=tuple(completed),
        coming_up=tuple(coming_up),
        overdue=tuple(overdue),
        blocked=tuple(blocked),
        workload=_workload(project, tasks, horizon),
    )
