# Client Status Report Automation

Turn a task export into a ready-to-send weekly client status report, plus an internal team workload view, in one command.

Built as a project-management automation case study: a project manager running several web projects in parallel spends hours each week copying numbers out of a tracker into status emails. This tool removes that step and makes the status rules explicit and consistent.

> **All data in this repository is fictional.** The demo project is a website redesign for an invented coffee roaster, "Bean & Brew".

**Sample output:** [client report](examples/client_status_2026-11-06.md) · [HTML version](examples/client_status_2026-11-06.html) (download and open in a browser) · [internal team view](examples/team_workload_2026-11-06.md)

## The problem

Weekly client reporting is repetitive, and it quietly goes wrong:

- Someone has to collect progress, hours, blockers and risks by hand, for every project, every week.
- "Green / Amber / Red" depends on who writes the report, so two projects in the same state get different labels.
- Internal information (team capacity, internal risks) must not leak into client reports, and that is easy to get wrong when editing by hand.

## What it does

```
tasks.csv  +  project.json   ──►   validate   ──►   calculate   ──►   client report (.md + .html)
(tracker export)                                                      internal team view (.md)
```

| Output | Audience | Contents |
| --- | --- | --- |
| Client report (Markdown and HTML) | Client | Overall RAG status with reasons, progress, budget and forecast, milestones, completed this week, coming up, what is needed from the client, client-visible risks |
| Team workload view (Markdown) | Internal | Utilization per person for the next 7 days, all blockers, overdue tasks, all risks |

## Quick start

Requires Python 3.10 or newer. The tool itself has no dependencies (standard library only); `pytest` is needed only to run the tests.

```bash
# generate reports for a given date (default: today)
python -m status_report --as-of 2026-11-06

# write to a specific folder
python -m status_report --as-of 2026-11-06 --out-dir reports

# only check that the input data is valid
python -m status_report --validate-only

# run the tests
pip install -r requirements-dev.txt
python -m pytest
```

Use your own data by pointing `--data-dir` at a folder that contains `project.json` and `tasks.csv`.

## Input data

**`data/tasks.csv`**, one row per task. Any tracker that can export CSV works after mapping its columns.

| Column | Meaning |
| --- | --- |
| `id`, `title` | Task identifier and name |
| `milestone` | Must match a milestone name in `project.json` |
| `assignee` | Must match a team member in `project.json` |
| `status` | `todo`, `in_progress`, `blocked` or `done` |
| `priority` | `low`, `medium` or `high` |
| `estimate_h`, `spent_h` | Estimated and logged hours |
| `due`, `completed` | ISO dates (`YYYY-MM-DD`); `completed` is required for `done` tasks and forbidden otherwise |
| `blocked_on`, `blocked_reason` | For blocked tasks: `client` or `team`, plus a reason. Client blockers appear under "Needed from you" |

**`data/project.json`**: project name, client, PM, start and end dates, budget in hours, milestones with due dates, team with weekly capacity, and risks marked `client` or `internal` visibility.

Invalid data stops the run with a message that names the file and line, for example `tasks.csv line 14: unknown assignee 'Jon'`, so a broken export never turns into a wrong report.

## How status is decided

The rules are named constants in [`status_report/metrics.py`](status_report/metrics.py), covered by tests.

**Milestone status**

| Status | Rule |
| --- | --- |
| Complete | Every task in the milestone is done |
| Late | Due date has passed and it is not complete |
| At risk | Has an overdue or blocked task, **or** is due within 7 days with less than 80% of effort done |
| On track | Everything else (including a milestone with no tasks) |

**Overall project status**

| Status | Rule |
| --- | --- |
| Red | Any milestone is Late, **or** forecast hours exceed budget by more than 10% |
| Amber | Any milestone is At risk, forecast is over budget by up to 10%, or there are overdue or blocked tasks |
| Green | None of the above |

**Other calculations**

- *Progress* is weighted by estimated hours, so a 20-hour task counts more than a 2-hour task.
- *Forecast at completion* is hours spent plus remaining estimated hours; an overrun never counts as negative remaining work.
- *Utilization* is open hours due within the next 7 days (including overdue) divided by weekly capacity. Over 100% is Overloaded, 85% and above is Near capacity.

## Design decisions

- **Standard library only.** No install step, nothing to break, easy to run in CI or on a colleague's machine.
- **Validation before calculation.** The most common failure in reporting automation is silently wrong input, so inputs are checked strictly.
- **Client and internal views are kept separate.** The client report never renders workload figures, internal risks or team-side blockers, and tests enforce it, so internal information cannot slip into a client email.
- **Deterministic output.** The same input and date always give identical files, so reports can be diffed and reviewed in version control.
- **HTML is escaped.** Task titles from a tracker are treated as untrusted text.
- **Tested.** 50 tests cover validation errors, every status rule and threshold, date windows and the CLI; GitHub Actions runs them on Python 3.10 and 3.12.

## Automation

[`.github/workflows/weekly-report.yml`](.github/workflows/weekly-report.yml) generates the report every Friday (and on demand). The client report is shown on the workflow run summary and the files are saved as a downloadable artifact. The demo data is frozen at 2026-11-06, so the workflow pins that date; on a real project, drop the pinned date and feed it a fresh tracker export.

## Time saved

This is an estimate, not a measurement: assume a manual weekly report takes about 45 minutes per project. For five parallel projects that is almost four hours a week of copying and formatting, replaced by a command that runs in under a second and uses the same rules every time.

## Possible next steps

- Pull tasks directly from the Jira or Asana API instead of a CSV export
- Send the client report by email or post the summary to Slack
- Add a burndown chart and a week-over-week trend
- PDF export for clients who prefer attachments
