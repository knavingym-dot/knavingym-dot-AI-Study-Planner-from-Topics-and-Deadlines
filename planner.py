"""Transparent, deterministic study-plan generation."""

from datetime import date, timedelta


DEFAULT_HOURS_BY_DIFFICULTY = {1: 0.5, 2: 1.0, 3: 1.5}
MAX_PLAN_DAYS = 365


class PlanningError(ValueError):
    """Raised when planning inputs cannot be used safely."""


def _parse_date(value, field_name):
    if isinstance(value, date):
        return value
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise PlanningError(f"{field_name} must be a valid date in YYYY-MM-DD format.") from exc
    return parsed


def build_plan(topics, daily_hours, start_date=None):
    """Return a reproducible schedule, transparent warnings, and a concise summary."""
    try:
        daily_hours = float(daily_hours)
    except (TypeError, ValueError) as exc:
        raise PlanningError("Available hours must be a number between 0.5 and 12.") from exc
    if not 0.5 <= daily_hours <= 12:
        raise PlanningError("Available hours must be between 0.5 and 12.")

    start = _parse_date(start_date, "Start date") if start_date else date.today()
    active = []
    warnings = []
    for source in topics:
        if source.get("completed"):
            continue
        topic = dict(source)
        topic["due"] = _parse_date(topic.get("deadline"), "Deadline")
        try:
            difficulty = int(topic.get("difficulty", 2))
            priority = int(topic.get("priority", 2))
        except (TypeError, ValueError) as exc:
            raise PlanningError("Difficulty and priority must be whole numbers from 1 to 3.") from exc
        if difficulty not in (1, 2, 3) or priority not in (1, 2, 3):
            raise PlanningError("Difficulty and priority must be whole numbers from 1 to 3.")
        topic["difficulty"] = difficulty
        topic["priority"] = priority
        estimate = topic.get("estimatedHours")
        if estimate is None or estimate == "":
            estimate = DEFAULT_HOURS_BY_DIFFICULTY[difficulty]
            warnings.append({
                "title": topic.get("title", "Untitled topic"),
                "message": f"No time estimate was provided; using {estimate:g} hour based on difficulty. You can change this estimate."
            })
        try:
            estimate_minutes = round(float(estimate) * 60)
        except (TypeError, ValueError) as exc:
            raise PlanningError("Study estimates must be a number greater than zero.") from exc
        if not 15 <= estimate_minutes <= 6000:
            raise PlanningError("Study estimates must be between 0.25 and 100 hours.")
        topic["remainingMinutes"] = estimate_minutes
        active.append(topic)

    if not active:
        return {
            "days": [],
            "warnings": warnings,
            "summary": {"topics": 0, "scheduledHours": 0, "dailyHours": daily_hours, "unscheduledTopics": 0}
        }

    latest_due = max(topic["due"] for topic in active)
    if (latest_due - start).days > MAX_PLAN_DAYS:
        raise PlanningError("Deadlines must fall within the next 365 days.")

    active.sort(key=lambda topic: (topic["due"], -topic["priority"], -topic["difficulty"], str(topic.get("id", ""))))
    for topic in active:
        if topic["due"] < start:
            warnings.append({
                "title": topic.get("title", "Untitled topic"),
                "message": f"Deadline was {topic['due'].isoformat()}; this past-due work is not placed in the forward-looking plan."
            })

    daily_budget = round(daily_hours * 60)
    day_count = max(0, (latest_due - start).days + 1)
    days = []
    for offset in range(day_count):
        current = start + timedelta(days=offset)
        day_sessions = []
        available_minutes = daily_budget
        study_minutes = 0
        completed_today = []
        eligible = [topic for topic in active if topic["due"] >= current and topic["remainingMinutes"] > 0]

        for topic in eligible:
            session_index = 0
            while topic["remainingMinutes"] > 0 and available_minutes >= 15:
                break_minutes = 10 if day_sessions and len(day_sessions) % 2 == 0 else 0
                if available_minutes - break_minutes < 15:
                    break_minutes = 0
                session_minutes = min(45, topic["remainingMinutes"], available_minutes - break_minutes)
                if session_minutes < 15:
                    if topic["remainingMinutes"] < 15 and available_minutes - break_minutes >= topic["remainingMinutes"]:
                        session_minutes = topic["remainingMinutes"]
                    else:
                        break
                day_sessions.append({
                    "topicId": topic.get("id"),
                    "title": topic.get("title", "Untitled topic"),
                    "subject": topic.get("subject", "Study"),
                    "durationMinutes": session_minutes,
                    "breakBeforeMinutes": break_minutes,
                    "isRevision": False
                })
                available_minutes -= session_minutes + break_minutes
                study_minutes += session_minutes
                topic["remainingMinutes"] -= session_minutes
                session_index += 1
            if topic["remainingMinutes"] == 0 and session_index:
                completed_today.append(topic)

        if day_sessions and available_minutes >= 15 and completed_today:
            review_minutes = min(15, available_minutes)
            review = completed_today[0]
            day_sessions.append({
                "topicId": review.get("id"),
                "title": f"Review: {review.get('title', 'Study topic')}",
                "subject": review.get("subject", "Study"),
                "durationMinutes": review_minutes,
                "breakBeforeMinutes": 0,
                "isRevision": True
            })
            study_minutes += review_minutes
            available_minutes -= review_minutes

        days.append({
            "date": current.isoformat(),
            "sessions": day_sessions,
            "studyHours": round(study_minutes / 60, 2),
            "availableHours": daily_hours
        })

    for topic in active:
        if topic["remainingMinutes"] > 0:
            remaining_hours = round(topic["remainingMinutes"] / 60, 2)
            if topic["due"] < start:
                continue
            warnings.append({
                "title": topic.get("title", "Untitled topic"),
                "message": f"{remaining_hours:g} hour(s) could not be placed before {topic['due'].isoformat()}. Consider adjusting your estimate, availability, or deadline."
            })

    scheduled_minutes = sum(
        session["durationMinutes"]
        for day in days
        for session in day["sessions"]
    )
    unscheduled = sum(
        1 for topic in active
        if topic["due"] >= start and topic["remainingMinutes"] > 0
    )
    return {
        "days": days,
        "warnings": warnings,
        "summary": {
            "topics": len(active),
            "scheduledHours": round(scheduled_minutes / 60, 2),
            "dailyHours": daily_hours,
            "unscheduledTopics": unscheduled
        }
    }
