# Studyflow — project report

## Project question

Can a study-planning tool turn topics, deadlines, and available study time into an adjustable plan?

## Outcome

Studyflow is a browser-based prototype with a sign-in/create-account screen, private topic list, overview dashboard, adjustable daily availability, and a day-by-day planning view. A local Python backend provides account, topic, settings, and plan APIs; SQLite persists data between runs.

## Tools

The prototype uses semantic HTML, CSS, browser JavaScript, Python's standard library, SQLite, and Git/GitHub-ready project documentation. It has no third-party Python runtime dependencies.

## Planning approach

The core scheduler uses deterministic rules rather than generative AI. It prioritises earliest deadlines, then user priority and difficulty, splits work into focused sessions, accounts for breaks and short reviews, and reports work that cannot fit. Students can adjust their estimates and plan at any time.

## Edge-case validation

Automated tests cover daily time limits including breaks, overlapping due dates and insufficient time, tie-breaking order, missing estimate defaults, completed topics, past-due work, review sessions, and unreasonable availability/deadline ranges. Run them with `python -m unittest discover -s tests -v`.

## Responsible use and limitations

The plan is an editable suggestion and is not a measure of ability. It does not know a student's timetable, energy, access needs, or wellbeing. Users should leave room for rest and adapt or seek support when circumstances change. There is no AI model integration. This local prototype is not intended for public deployment without production hardening, HTTPS, account recovery, abuse controls, and a reviewed privacy policy.

## Further work

Potential next steps include a calendar export, per-day availability and rest days, data export/deletion controls, account recovery, stronger deployment controls, and optional AI-generated study explanations that never replace or conceal the scheduling rules.
