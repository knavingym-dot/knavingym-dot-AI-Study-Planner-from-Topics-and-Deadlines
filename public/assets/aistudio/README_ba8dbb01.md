# Studyflow — AI Study Planner

Studyflow turns topics, deadlines, and available study time into a clear, editable day-by-day plan. It is built around one simple idea: a good plan should make studying feel more manageable, not make the student feel behind.

> **Capstone prototype:** scheduling is deterministic and transparent. No AI model is used to make hidden planning decisions. The plan is a suggestion that students can change as their time, needs, or priorities change.

## Features

- Responsive sign-in and account creation with a calm, student-focused interface.
- Private topic list with subject, estimate, due date, difficulty, priority, and completion controls.
- Overview with upcoming deadlines and weekly context.
- Adjustable daily availability and a day-by-day schedule.
- 45-minute focus sessions, 10-minute breaks, and short review sessions.
- Clear warnings for past-due work, missing time estimates, and workload that cannot fit.
- Python standard-library backend and local SQLite persistence.

## Quick start

**Requirements:** Python 3.10 or newer. No third-party Python packages are needed.

```powershell
python server.py
```

Open <http://127.0.0.1:8000>, choose **Create account**, then add a few topics. Stop the local server with `Ctrl+C`.

On Windows, you can also double-click `start-studyflow.bat` to start the local server and open the app in your browser.

Run the planner tests:

```powershell
python -m unittest discover -s tests -v
```

## How the plan is made

1. Completed topics are excluded.
2. Work is ordered by earliest deadline, then higher student priority, then higher difficulty. Topic ID makes ties reproducible.
3. Each day is capped at the student's available hours. Work is split into sessions of up to 45 minutes.
4. A 10-minute reset is included after every two focus sessions when time permits. A short review may use up to 15 minutes left after finishing a topic.
5. Break and review time count toward the daily availability limit. Work that does not fit before its deadline is reported, never silently scheduled late.

For missing estimates passed to the planner, the disclosed defaults are 0.5 / 1 / 1.5 hours for difficulty levels 1 / 2 / 3. The app asks students to enter an estimate when adding a topic.

## Project files

| File | Purpose |
| --- | --- |
| `index.html`, `styles.css`, `app.js` | Accessible login, dashboard, topics, plan, and browser interactions |
| `start-studyflow.bat` | Windows launcher that starts the server and opens the browser |
| `server.py` | Local HTTP server, JSON API, accounts, sessions, topic persistence |
| `planner.py` | Deterministic scheduling rules |
| `tests/test_planner.py` | Automated planner and edge-case tests |
| `sample-input.json` | Example workload with overlapping deadlines and limited hours |
| `requirements-and-planning.md` | Audience, assumptions, input shape, rules, edge cases |
| `user-guide-and-prompt-log.md` | Run instructions, sample walkthrough, AI-use log, privacy notes |
| `edge-case-test-report.md` | Edge-case coverage, expected behavior, and execution status |
| `final-report.md` | Capstone outcome, responsible use, limitations |
| `presentation-outline.md` | Suggested presentation structure |

Project notes: [requirements and planning](requirements-and-planning.md) · [sample input](sample-input.json) · [edge-case report](edge-case-test-report.md) · [user guide and prompt log](user-guide-and-prompt-log.md) · [final report](final-report.md) · [presentation outline](presentation-outline.md).

## Configuration

By default, the server binds to `127.0.0.1:8000` and stores data in `studyflow.db` next to `server.py`. Optional environment variables:

```powershell
$env:STUDYFLOW_HOST = "127.0.0.1"
$env:STUDYFLOW_PORT = "8000"
$env:STUDYFLOW_DB = "C:\path\to\studyflow.db"
python server.py
```

Keep the host on `127.0.0.1` for local development. The prototype is not configured for public deployment.

## API overview

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/register` | Create an account and session |
| `POST` | `/api/auth/login` | Sign in |
| `POST` | `/api/auth/logout` | End the current session |
| `GET` | `/api/me` | Check the current account |
| `GET`, `POST` | `/api/topics` | List or create topics |
| `PATCH`, `DELETE` | `/api/topics/{id}` | Edit or remove a topic |
| `GET`, `PUT` | `/api/settings` | Read or update daily availability |
| `GET` | `/api/plan` | Build a plan from saved topics and settings |

## Privacy and security notes

Passwords are salted PBKDF2-HMAC-SHA256 hashes, not plaintext. Sessions use random tokens stored server-side as hashes and are sent in HttpOnly, SameSite cookies. Data is stored locally in SQLite. This educational prototype does not include account recovery, production rate-limits, HTTPS configuration, or a production privacy policy. Do not expose it to the public internet or use a password you rely on elsewhere.

## GitHub

To publish this folder as a new repository:

```powershell
git init
git add .
git commit -m "Build Studyflow study planner"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/studyflow.git
git push -u origin main
```

Replace the remote URL with your own GitHub repository. Do not commit `studyflow.db` or real student data.
