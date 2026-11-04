# Bean & Brew — Website Redesign: internal team view

Week of 02 Nov 2026 · as of 06 Nov 2026 · not for client distribution

## Capacity for the next 7 days

Open work due on or before 13 Nov 2026 (including overdue tasks) against weekly capacity.

| Person | Role | Open hours | Weekly capacity | Utilization | Status |
| --- | --- | --- | --- | --- | --- |
| Nastia | Project Manager | 0 | 20 | 0% | 🟢 OK |
| Olena Kovalenko | UX/UI Designer | 0 | 32 | 0% | 🟢 OK |
| Marek Nowak | Frontend Developer | 24 | 36 | 67% | 🟢 OK |
| Iryna Petrenko | Backend Developer | 40 | 32 | 125% | 🔴 Overloaded |
| Kasia Zielinska | SEO & Content Specialist | 7 | 24 | 29% | 🟢 OK |
| Tomasz Lis | QA Engineer | 0 | 30 | 0% | 🟢 OK |

## Blocked tasks

| Task | Owner | Blocked on | Reason | Due |
| --- | --- | --- | --- | --- |
| Payment provider integration (test mode) | Iryna Petrenko | Client | Waiting for the client to create the payment provider account and share test API keys | 05 Nov 2026 |
| Product photo upload & optimization | Marek Nowak | Client | Final product photos promised by the client for 9 Nov | 09 Nov 2026 |

## Overdue tasks

| Task | Owner | Due | Hours left |
| --- | --- | --- | --- |
| Payment provider integration (test mode) | Iryna Petrenko | 05 Nov 2026 | 10 |

## All risks

| ID | Risk | Impact | Owner | Visible to client | Mitigation |
| --- | --- | --- | --- | --- | --- |
| R1 | Client assets (payment provider account, final product photos) arrive late and delay checkout and catalog work. | High | Nastia | Yes | Requested in this report with dates. Fallback: launch with placeholder photos and swap them after go-live. |
| R2 | Ordering API work is concentrated on one backend developer and exceeds her capacity next week. | Medium | Nastia | No | Move rate limiting to post-launch hardening, or shift 8h of integration work to the frontend developer. |
| R3 | Old-site URLs lose search traffic after launch if redirects are incomplete. | Medium | Kasia Zielinska | Yes | 301 redirect map is part of Content & SEO; Search Console monitored for two weeks after launch. |
