from datetime import date

import pytest

from status_report.loader import Milestone, Project, Risk, Task, TeamMember


@pytest.fixture
def project() -> Project:
    return Project(
        name="Test Site",
        client="Acme",
        pm="Pat",
        start=date(2026, 1, 5),
        end=date(2026, 3, 27),
        budget_hours=100.0,
        milestones=(Milestone("Design", date(2026, 2, 6)), Milestone("Build", date(2026, 3, 6))),
        team=(TeamMember("Ann", "Designer", 20.0), TeamMember("Bob", "Developer", 30.0)),
        risks=(
            Risk("R1", "Client delay", "high", "Escalate", "Pat", "client"),
            Risk("R2", "Single developer", "medium", "Rebalance", "Pat", "internal"),
        ),
    )


@pytest.fixture
def make_task():
    counter = {"n": 0}

    def _make(**overrides) -> Task:
        counter["n"] += 1
        values = dict(
            id=f"T-{counter['n']:03d}",
            title="Task",
            milestone="Build",
            assignee="Bob",
            status="todo",
            priority="medium",
            estimate_h=10.0,
            spent_h=0.0,
            due=date(2026, 3, 6),
            completed=None,
            blocked_on="",
            blocked_reason="",
        )
        values.update(overrides)
        return Task(**values)

    return _make
