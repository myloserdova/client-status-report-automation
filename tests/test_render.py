from dataclasses import replace
from datetime import date

from status_report.loader import Milestone
from status_report.metrics import build_summary
from status_report.render import render_client_html, render_client_markdown, render_workload_markdown

AS_OF = date(2026, 2, 13)


def test_markdown_contains_core_sections(project, make_task):
    tasks = [
        make_task(status="done", completed=date(2026, 2, 10), title="Finished thing"),
        make_task(status="blocked", blocked_on="client", blocked_reason="Need the logo", title="Stuck thing", due=date(2026, 2, 17)),
    ]
    text = render_client_markdown(project, build_summary(project, tasks, AS_OF))
    for expected in (
        "# Test Site",
        "## Overall status:",
        "## Milestones",
        "Finished thing",
        "Need the logo",
        "## Risks",
        "Client delay",
    ):
        assert expected in text


def test_client_report_hides_internal_risks_and_workload(project, make_task):
    text = render_client_markdown(project, build_summary(project, [make_task()], AS_OF))
    assert "Single developer" not in text
    assert "Utilization" not in text


def test_internal_report_shows_every_risk_and_workload(project, make_task):
    text = render_workload_markdown(project, build_summary(project, [make_task()], AS_OF))
    assert "Single developer" in text
    assert "Client delay" in text
    assert "Utilization" in text


def test_no_client_blockers_message(project, make_task):
    text = render_client_markdown(project, build_summary(project, [make_task()], AS_OF))
    assert "Nothing is needed from you this week." in text


def test_team_blockers_are_not_shown_as_client_requests(project, make_task):
    task = make_task(status="blocked", blocked_on="team", blocked_reason="Internal review pending")
    text = render_client_markdown(project, build_summary(project, [task], AS_OF))
    assert "Internal review pending" not in text


def test_html_escapes_untrusted_text(project, make_task):
    tasks = [make_task(title="<script>alert(1)</script>", due=date(2026, 2, 16))]
    html = render_client_html(project, build_summary(project, tasks, AS_OF))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_markdown_tables_escape_pipes(project, make_task):
    piped = replace(project, milestones=(Milestone("Design | Build", date(2026, 3, 6)),))
    text = render_client_markdown(piped, build_summary(piped, [make_task(milestone="Design | Build")], AS_OF))
    assert "Design \\| Build" in text


def test_output_is_deterministic(project, make_task):
    summary = build_summary(project, [make_task()], AS_OF)
    assert render_client_markdown(project, summary) == render_client_markdown(project, summary)
    assert render_client_html(project, summary) == render_client_html(project, summary)
