"""Load and validate project and task data.

Everything a report needs comes from two plain files (project.json and
tasks.csv), so the tool works with any tracker that can export CSV: Jira,
Asana, Trello, or a spreadsheet. Bad data is rejected early with a message
that names the file and line, so a broken export never becomes a wrong report.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

STATUSES = ("todo", "in_progress", "blocked", "done")
PRIORITIES = ("low", "medium", "high")
BLOCKERS = ("client", "team")
VISIBILITIES = ("client", "internal")
IMPACTS = ("low", "medium", "high")

TASK_COLUMNS = (
    "id",
    "title",
    "milestone",
    "assignee",
    "status",
    "priority",
    "estimate_h",
    "spent_h",
    "due",
    "completed",
    "blocked_on",
    "blocked_reason",
)


class DataError(ValueError):
    """Input data is missing, malformed or inconsistent."""


@dataclass(frozen=True)
class Milestone:
    name: str
    due: date


@dataclass(frozen=True)
class TeamMember:
    name: str
    role: str
    weekly_capacity_h: float


@dataclass(frozen=True)
class Risk:
    id: str
    description: str
    impact: str
    mitigation: str
    owner: str
    visibility: str  # "client" risks appear in the client report, "internal" ones do not


@dataclass(frozen=True)
class Project:
    name: str
    client: str
    pm: str
    start: date
    end: date
    budget_hours: float
    milestones: tuple[Milestone, ...]
    team: tuple[TeamMember, ...]
    risks: tuple[Risk, ...]


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    milestone: str
    assignee: str
    status: str
    priority: str
    estimate_h: float
    spent_h: float
    due: date
    completed: date | None
    blocked_on: str
    blocked_reason: str


def _parse_date(value: object, where: str) -> date:
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        raise DataError(f"{where}: '{value}' is not a valid date (expected YYYY-MM-DD)") from None


def _parse_hours(value: str, where: str, field: str) -> float:
    try:
        hours = float(value)
    except ValueError:
        raise DataError(f"{where}: {field} '{value}' is not a number") from None
    if hours < 0:
        raise DataError(f"{where}: {field} cannot be negative")
    return hours


def _choice(value: str, allowed: tuple[str, ...], where: str, field: str) -> str:
    if value not in allowed:
        raise DataError(f"{where}: {field} '{value}' must be one of: {', '.join(allowed)}")
    return value


def load_project(path: str | Path) -> Project:
    """Read project.json: dates, budget, milestones, team and risks."""
    path = Path(path)
    where = path.name
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DataError(f"File not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise DataError(f"{where}: invalid JSON ({exc})") from None

    try:
        milestones = tuple(
            Milestone(m["name"], _parse_date(m["due"], f"{where} milestone '{m['name']}'"))
            for m in raw["milestones"]
        )
        team = tuple(
            TeamMember(m["name"], m["role"], float(m["weekly_capacity_h"])) for m in raw["team"]
        )
        risks = tuple(
            Risk(
                id=r["id"],
                description=r["description"],
                impact=_choice(r["impact"], IMPACTS, f"{where} risk {r['id']}", "impact"),
                mitigation=r["mitigation"],
                owner=r["owner"],
                visibility=_choice(
                    r.get("visibility", "internal"), VISIBILITIES, f"{where} risk {r['id']}", "visibility"
                ),
            )
            for r in raw.get("risks", [])
        )
        project = Project(
            name=raw["name"],
            client=raw["client"],
            pm=raw["pm"],
            start=_parse_date(raw["start"], f"{where} start"),
            end=_parse_date(raw["end"], f"{where} end"),
            budget_hours=float(raw["budget_hours"]),
            milestones=milestones,
            team=team,
            risks=risks,
        )
    except DataError:
        raise
    except KeyError as exc:
        raise DataError(f"{where}: missing field {exc}") from None
    except (TypeError, ValueError) as exc:
        raise DataError(f"{where}: invalid value ({exc})") from None

    _validate_project(project, where)
    return project


def _validate_project(project: Project, where: str) -> None:
    if project.end <= project.start:
        raise DataError(f"{where}: 'end' must be after 'start'")
    if project.budget_hours <= 0:
        raise DataError(f"{where}: budget_hours must be greater than zero")
    if not project.milestones:
        raise DataError(f"{where}: at least one milestone is required")
    if not project.team:
        raise DataError(f"{where}: at least one team member is required")

    names = [m.name for m in project.milestones]
    if len(set(names)) != len(names):
        raise DataError(f"{where}: milestone names must be unique")
    people = [m.name for m in project.team]
    if len(set(people)) != len(people):
        raise DataError(f"{where}: team member names must be unique")
    for member in project.team:
        if member.weekly_capacity_h <= 0:
            raise DataError(f"{where}: weekly_capacity_h for {member.name} must be greater than zero")


def load_tasks(path: str | Path, project: Project) -> list[Task]:
    """Read tasks.csv and check every row against the project definition."""
    path = Path(path)
    milestone_names = {m.name for m in project.milestones}
    people = {m.name for m in project.team}
    tasks: list[Task] = []
    seen: set[str] = set()

    try:
        handle = path.open(newline="", encoding="utf-8")
    except FileNotFoundError:
        raise DataError(f"File not found: {path}") from None

    with handle:
        reader = csv.DictReader(handle)
        missing = [c for c in TASK_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise DataError(f"{path.name}: missing column(s): {', '.join(missing)}")

        for line_no, row in enumerate(reader, start=2):
            where = f"{path.name} line {line_no}"
            get = lambda key: (row.get(key) or "").strip()  # noqa: E731

            task_id = get("id")
            if not task_id:
                raise DataError(f"{where}: id is required")
            if task_id in seen:
                raise DataError(f"{where}: duplicate task id '{task_id}'")
            seen.add(task_id)

            status = _choice(get("status"), STATUSES, where, "status")
            priority = _choice(get("priority"), PRIORITIES, where, "priority")
            milestone = get("milestone")
            if milestone not in milestone_names:
                raise DataError(f"{where}: unknown milestone '{milestone}'")
            assignee = get("assignee")
            if assignee not in people:
                raise DataError(f"{where}: unknown assignee '{assignee}'")

            due = _parse_date(get("due"), f"{where} due")
            completed = _parse_date(get("completed"), f"{where} completed") if get("completed") else None
            if status == "done" and completed is None:
                raise DataError(f"{where}: task {task_id} is done but has no completion date")
            if status != "done" and completed is not None:
                raise DataError(f"{where}: task {task_id} has a completion date but is not done")

            blocked_on, blocked_reason = get("blocked_on"), get("blocked_reason")
            if status == "blocked":
                _choice(blocked_on, BLOCKERS, where, "blocked_on")
                if not blocked_reason:
                    raise DataError(f"{where}: blocked task {task_id} needs a blocked_reason")

            tasks.append(
                Task(
                    id=task_id,
                    title=get("title"),
                    milestone=milestone,
                    assignee=assignee,
                    status=status,
                    priority=priority,
                    estimate_h=_parse_hours(get("estimate_h"), where, "estimate_h"),
                    spent_h=_parse_hours(get("spent_h"), where, "spent_h"),
                    due=due,
                    completed=completed,
                    blocked_on=blocked_on,
                    blocked_reason=blocked_reason,
                )
            )

    if not tasks:
        raise DataError(f"{path.name}: no tasks found")
    return tasks
