# User guide and prompt log

## Run the app

1. Install Python 3.10 or later.
2. Open a terminal in the project folder.
3. Run `python server.py`.
4. Open `http://127.0.0.1:8000` and create an account.
5. Add topics with an estimate, due date, difficulty, and priority.
6. Open **Study plan** to review the draft, change daily hours, and rebuild it when your workload changes.
7. Use **Edit**, **Done**, or **×** on a topic to keep your plan current. Sign out when finished.

The app creates `studyflow.db` locally on first launch. It has no third-party runtime dependencies. Google Fonts are an optional visual enhancement; system fonts remain available if the network is offline.

## Sample input

`sample-input.json` contains five topics across Biology, Mathematics, History, Chemistry, and English. The Biology and Mathematics deadlines overlap, with only two study hours available each day. Import is not currently built into the UI; enter these records by hand to explore the same case.

## Prompt and AI-use log

- **User's project brief (image):** develop “CAPSTONE 23 — AI Study Planner from Topics and Deadlines”; define a student audience and assumptions, input format, transparent prioritisation, deterministic baseline before AI, sample cases, day-by-day schedule with breaks/revision, editable controls, edge-case testing, responsible optional AI use, calendar/table interface, and project documentation.
- **User's implementation request:** create a professional project with login page, careful UI/UX, HTML, backend, and a GitHub README.
- **AI implementation approach:** make a responsive, accessible login and study dashboard; use a small Python/SQLite backend; implement scheduling as a deterministic Python function; provide user-facing warnings and tests; document setup, assumptions, test cases, and responsible-use limits.
- **Generative AI scheduling:** none. No model, external AI API, or hidden AI-generated scheduling logic is connected to the prototype.

## Data and privacy notes

This is a local learning prototype, not a production identity service. Account passwords are stored as salted PBKDF2-HMAC-SHA256 hashes; browser sessions use random, server-validated tokens in HttpOnly cookies. SQLite data stays in the project folder unless `STUDYFLOW_DB` is configured. Do not expose the development server to a public network or reuse a sensitive password.
