"""Render a Summary as Markdown (GitHub, Slack, email) and HTML (for clients).

The client report shows only what a client needs: progress, milestones,
what was done, what is next, what we need from them, and client-visible risks.
The internal report adds workload, every blocker and every risk.
"""
from __future__ import annotations

from html import escape

from .loader import Project, Task
from .metrics import Summary, remaining_hours

ICON = {
    "Green": "🟢",
    "Amber": "🟠",
    "Red": "🔴",
    "Complete": "✅",
    "On track": "🟢",
    "At risk": "🟠",
    "Late": "🔴",
    "OK": "🟢",
    "Near capacity": "🟠",
    "Overloaded": "🔴",
}


def _d(value) -> str:
    return f"{value:%d %b %Y}"


def _bar(pct: float, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _cell(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _md_table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return lines


def _hours(value: float) -> str:
    return f"{value:g}"


def _client_blockers(summary: Summary) -> list[Task]:
    return [t for t in summary.blocked if t.blocked_on == "client"]


def _risks(project: Project, visibility: str | None):
    return [r for r in project.risks if visibility is None or r.visibility == visibility]


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #

def render_client_markdown(project: Project, s: Summary) -> str:
    key_rows = [
        ["Overall progress", f"`{_bar(s.progress_pct)}` {s.progress_pct:.1f}% (by effort)"],
        ["Tasks completed", f"{s.tasks_done} of {s.tasks_total}"],
        ["Hours used", f"{_hours(s.hours_spent)} of {_hours(s.hours_budget)} budgeted"],
        [
            "Forecast at completion",
            f"{_hours(s.hours_forecast)} h ({s.forecast_variance_pct:+.1f}% vs budget)",
        ],
        ["Days to planned launch", f"{s.days_to_end} ({_d(project.end)})"],
    ]
    milestone_rows = [
        [m.name, _d(m.due), f"{m.progress_pct:.0f}%", f"{ICON[m.status]} {m.status}"] for m in s.milestones
    ]

    out = [
        f"# {project.name}",
        "",
        f"**Weekly status report** · week of {_d(s.week_start)} · as of {_d(s.as_of)}  ",
        f"Prepared by {project.pm} (Project Manager) for {project.client}",
        "",
        f"## Overall status: {ICON[s.rag]} {s.rag}",
        "",
        *[f"- {reason}" for reason in s.rag_reasons],
        "",
        "## Key numbers",
        "",
        *_md_table(["Metric", "Value"], key_rows),
        "",
        "## Milestones",
        "",
        *_md_table(["Milestone", "Due", "Progress", "Status"], milestone_rows),
        "",
        "## Completed this week",
        "",
    ]
    if s.completed_this_week:
        out += [f"- ✅ {t.title} ({t.assignee})" for t in s.completed_this_week]
    else:
        out.append("No tasks were completed this week.")

    out += ["", "## Coming up (next 7 days)", ""]
    if s.coming_up:
        out += [
            f"- {t.title}: due {t.due:%a %d %b} ({t.assignee})" + (" **(blocked)**" if t.status == "blocked" else "")
            for t in s.coming_up
        ]
    else:
        out.append("Nothing is scheduled to finish in the next 7 days.")

    out += ["", "## Needed from you", ""]
    blockers = _client_blockers(s)
    if blockers:
        out += [
            f"- **{t.title}**: {t.blocked_reason} (needed by {t.due:%a %d %b})"
            + (" **[overdue]**" if t in s.overdue else "")
            for t in blockers
        ]
    else:
        out.append("Nothing is needed from you this week.")

    client_risks = _risks(project, "client")
    if client_risks:
        out += [
            "",
            "## Risks",
            "",
            *_md_table(
                ["ID", "Risk", "Impact", "Mitigation"],
                [[r.id, r.description, r.impact.capitalize(), r.mitigation] for r in client_risks],
            ),
        ]

    out += ["", "---", "*Generated automatically from the project tracker export.*", ""]
    return "\n".join(out)


def render_workload_markdown(project: Project, s: Summary) -> str:
    workload_rows = [
        [
            w.name,
            w.role,
            _hours(w.open_hours),
            _hours(w.capacity_h),
            f"{w.utilization_pct:.0f}%",
            f"{ICON[w.status]} {w.status}",
        ]
        for w in s.workload
    ]
    out = [
        f"# {project.name}: internal team view",
        "",
        f"Week of {_d(s.week_start)} · as of {_d(s.as_of)} · not for client distribution",
        "",
        "## Capacity for the next 7 days",
        "",
        f"Open work due on or before {_d(s.horizon)} (including overdue tasks) against weekly capacity.",
        "",
        *_md_table(
            ["Person", "Role", "Open hours", "Weekly capacity", "Utilization", "Status"], workload_rows
        ),
        "",
        "## Blocked tasks",
        "",
    ]
    if s.blocked:
        out += _md_table(
            ["Task", "Owner", "Blocked on", "Reason", "Due"],
            [[t.title, t.assignee, t.blocked_on.capitalize(), t.blocked_reason, _d(t.due)] for t in s.blocked],
        )
    else:
        out.append("No blocked tasks.")

    out += ["", "## Overdue tasks", ""]
    if s.overdue:
        out += _md_table(
            ["Task", "Owner", "Due", "Hours left"],
            [[t.title, t.assignee, _d(t.due), _hours(remaining_hours(t))] for t in s.overdue],
        )
    else:
        out.append("No overdue tasks.")

    out += [
        "",
        "## All risks",
        "",
        *_md_table(
            ["ID", "Risk", "Impact", "Owner", "Visible to client", "Mitigation"],
            [
                [
                    r.id,
                    r.description,
                    r.impact.capitalize(),
                    r.owner,
                    "Yes" if r.visibility == "client" else "No",
                    r.mitigation,
                ]
                for r in _risks(project, None)
            ],
        ),
        "",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# HTML
# --------------------------------------------------------------------------- #

class _Raw(str):
    """A string that is already safe HTML and must not be escaped again."""


def _h(value: object) -> str:
    return value if isinstance(value, _Raw) else escape(str(value))


def _table(headers: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{_h(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _ul(items: list[object]) -> str:
    return "<ul>" + "".join(f"<li>{_h(i)}</li>" for i in items) + "</ul>"


def _badge(label: str) -> _Raw:
    css = label.lower().replace(" ", "-")
    return _Raw(f'<span class="badge {css}">{escape(label)}</span>')


def _progress(pct: float) -> _Raw:
    return _Raw(f'<div class="bar"><div style="width:{pct:.1f}%"></div></div> {pct:.1f}% (by effort)')


_CSS = """
:root { color-scheme: light; }
body { margin: 0; background: #f6f5f2; color: #1f2328; font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 780px; margin: 0 auto; padding: 32px 20px 56px; }
h1 { font-size: 1.7rem; margin: 0 0 4px; }
h2 { font-size: 1.15rem; margin: 32px 0 10px; padding-bottom: 6px; border-bottom: 1px solid #d8d4cc; }
.meta { color: #57606a; margin: 0 0 8px; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #d8d4cc; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #ece9e3; vertical-align: top; }
th { background: #efece6; font-size: .85rem; }
ul { padding-left: 20px; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-weight: 600; font-size: .85rem; }
.green, .on-track { background: #d7f0dc; color: #14532d; }
.amber, .at-risk { background: #fde8c4; color: #7a4100; }
.red, .late { background: #f9d4d1; color: #8a1c14; }
.complete { background: #d6e6fb; color: #0b3d7a; }
.bar { display: inline-block; width: 160px; height: 10px; background: #e2ded6; border-radius: 5px; overflow: hidden; vertical-align: middle; }
.bar > div { height: 100%; background: #2f6f4f; }
.foot { margin-top: 40px; color: #6e7781; font-size: .85rem; }
"""


def render_client_html(project: Project, s: Summary) -> str:
    key_rows = [
        ["Overall progress", _progress(s.progress_pct)],
        ["Tasks completed", f"{s.tasks_done} of {s.tasks_total}"],
        ["Hours used", f"{_hours(s.hours_spent)} of {_hours(s.hours_budget)} budgeted"],
        ["Forecast at completion", f"{_hours(s.hours_forecast)} h ({s.forecast_variance_pct:+.1f}% vs budget)"],
        ["Days to planned launch", f"{s.days_to_end} ({_d(project.end)})"],
    ]
    milestone_rows = [
        [m.name, _d(m.due), f"{m.progress_pct:.0f}%", _badge(m.status)] for m in s.milestones
    ]

    parts = [
        f"<h1>{escape(project.name)}</h1>",
        f'<p class="meta"><strong>Weekly status report</strong> · week of {_d(s.week_start)} · as of {_d(s.as_of)}<br>'
        f"Prepared by {escape(project.pm)} (Project Manager) for {escape(project.client)}</p>",
        f"<h2>Overall status: {_badge(s.rag)}</h2>",
        _ul(list(s.rag_reasons)),
        "<h2>Key numbers</h2>",
        _table(["Metric", "Value"], key_rows),
        "<h2>Milestones</h2>",
        _table(["Milestone", "Due", "Progress", "Status"], milestone_rows),
        "<h2>Completed this week</h2>",
        _ul([f"{t.title} ({t.assignee})" for t in s.completed_this_week])
        if s.completed_this_week
        else "<p>No tasks were completed this week.</p>",
        "<h2>Coming up (next 7 days)</h2>",
        _ul(
            [
                f"{t.title}: due {t.due:%a %d %b} ({t.assignee})" + (" (blocked)" if t.status == "blocked" else "")
                for t in s.coming_up
            ]
        )
        if s.coming_up
        else "<p>Nothing is scheduled to finish in the next 7 days.</p>",
        "<h2>Needed from you</h2>",
    ]

    blockers = _client_blockers(s)
    parts.append(
        _ul(
            [
                f"{t.title}: {t.blocked_reason} (needed by {t.due:%a %d %b})" + (" [overdue]" if t in s.overdue else "")
                for t in blockers
            ]
        )
        if blockers
        else "<p>Nothing is needed from you this week.</p>"
    )

    client_risks = _risks(project, "client")
    if client_risks:
        parts += [
            "<h2>Risks</h2>",
            _table(
                ["ID", "Risk", "Impact", "Mitigation"],
                [[r.id, r.description, r.impact.capitalize(), r.mitigation] for r in client_risks],
            ),
        ]
    parts.append('<p class="foot">Generated automatically from the project tracker export.</p>')

    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(project.name)}: status report</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n<main>\n" + "\n".join(parts) + "\n</main>\n</body>\n</html>\n"
    )
