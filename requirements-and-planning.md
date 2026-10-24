# Requirements and planning rules

## Intended audience

Studyflow is a single-student planner prototype for learners who need a manageable, editable way to prepare for several subjects with overlapping deadlines. It is not a school learning-management system, a grade predictor, or a substitute for teacher guidance.

## Assumptions

- The student enters one task or topic at a time and supplies a due date, an estimate, a difficulty rating, and a personal priority.
- Daily availability is a repeating maximum of 0.5–12 study hours; this first version does not model individual calendar events, weekdays off, or time-of-day preferences.
- Plans begin today and include work only on or before each topic's due date.
- A supplied estimate is an estimate, not a promise. Completed topics are left out of planning.
- The browser connects to a local Python server. SQLite stores each account, topic, setting, and server-side session.
- AI is not used for scheduling. The visible rules produce the same schedule for the same inputs.

## Input shape

```json
{
  "dailyHours": 2,
  "topics": [
    {
      "subject": "Biology",
      "title": "Cell structure and transport",
      "estimatedHours": 2,
      "deadline": "2026-10-26",
      "difficulty": 2,
      "priority": 3,
      "completed": false
    }
  ]
}
```

`difficulty` and `priority` each range from 1 (low) to 3 (high). Estimates must be 0.25–100 hours; due dates must be valid and within one year. When the planner is called directly with a missing estimate, it uses 0.5, 1, or 1.5 hours for difficulty 1, 2, or 3, and displays that assumption. The app's topic form asks for an estimate explicitly.

## Transparent baseline scheduling

1. Ignore completed topics.
2. Sort remaining topics by earliest deadline, then higher student priority, then higher difficulty, then stable topic ID.
3. Starting today, fill each day's available time in 45-minute focus sessions, continuing partially completed topics on later eligible days.
4. Insert a 10-minute reset after each pair of focus sessions when time permits. Break time counts toward the daily availability limit.
5. When a topic is finished and there is at least 15 minutes of time left, use up to 15 minutes for a quick review. Revision also counts against daily availability.
6. Never schedule a task after its deadline. Explain past-due work and any remaining workload in warnings rather than hiding it or overrunning the daily limit.
7. Keep the plan editable: change estimates, priority, difficulty, availability, or completion, then refresh the plan.

## Edge cases considered

- Overlapping deadlines and insufficient capacity are surfaced with remaining hours.
- A same-day deadline is eligible today, but work that cannot fit is reported as unscheduled.
- Past-due work is called out, not silently moved to a later date.
- A missing estimate has a disclosed difficulty-based default in the planner.
- Completed topics do not consume time.
- Invalid hours, estimates, ratings, dates, and deadlines outside the planning horizon are rejected with a visible message.
- Breaks and review are included in the daily time budget; the plan never silently exceeds availability.

## Accessibility and wellbeing

The interface supports keyboard-accessible native forms/dialogs, explicit labels, visible focus styles, semantic landmarks, responsive layouts, and live status feedback. Color is supplementary to text. The plan is framed as a suggestion: students should adapt it for rest, accessibility, unexpected events, and support needs.
