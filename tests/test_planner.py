"""Automated tests for deterministic study planner."""

import unittest
from datetime import date, timedelta
from planner import PlanningError, build_plan


class TestStudyPlanner(unittest.TestCase):
    def test_sessions_fit_daily_limit_including_breaks(self):
        """Work must fit within daily availability, including reset breaks."""
        today = date.today()
        topics = [
            {
                "id": "t1",
                "subject": "Math",
                "title": "Calculus problem set",
                "estimatedHours": 4,
                "deadline": (today + timedelta(days=2)).isoformat(),
                "difficulty": 2,
                "priority": 2,
                "completed": False,
            }
        ]
        daily_hours = 2.0
        plan = build_plan(topics, daily_hours, start_date=today)
        self.assertTrue(len(plan["days"]) > 0)
        daily_limit_minutes = round(daily_hours * 60)
        for day in plan["days"]:
            total_minutes = sum(
                s["durationMinutes"] + s.get("breakBeforeMinutes", 0)
                for s in day["sessions"]
            )
            self.assertLessEqual(
                total_minutes,
                daily_limit_minutes,
                f"Day {day['date']} total minutes ({total_minutes}) exceeds limit ({daily_limit_minutes})",
            )

    def test_overlapping_deadlines_warn_when_work_does_not_fit(self):
        """Several topics share a deadline, but workload exceeds total available time."""
        today = date.today()
        due = (today + timedelta(days=1)).isoformat()
        topics = [
            {
                "id": "t1",
                "subject": "Biology",
                "title": "Genetics chapter",
                "estimatedHours": 5,
                "deadline": due,
                "difficulty": 3,
                "priority": 3,
                "completed": False,
            },
            {
                "id": "t2",
                "subject": "Physics",
                "title": "Mechanics lab",
                "estimatedHours": 5,
                "deadline": due,
                "difficulty": 3,
                "priority": 2,
                "completed": False,
            },
        ]
        # Total work = 10 hrs, available over 2 days (today + tomorrow) at 1.5 hrs/day = 3 hrs
        plan = build_plan(topics, 1.5, start_date=today)
        self.assertGreater(plan["summary"]["unscheduledTopics"], 0)
        self.assertTrue(any("could not be placed before" in w["message"] for w in plan["warnings"]))

    def test_deadline_then_priority_then_difficulty_define_order(self):
        """Different deadlines and priorities: earlier due first, higher priority breaks ties."""
        today = date.today()
        topics = [
            {
                "id": "t_late",
                "subject": "English",
                "title": "Essay draft",
                "estimatedHours": 1,
                "deadline": (today + timedelta(days=3)).isoformat(),
                "difficulty": 3,
                "priority": 3,
            },
            {
                "id": "t_low_prio",
                "subject": "Art",
                "title": "Sketchbook review",
                "estimatedHours": 1,
                "deadline": (today + timedelta(days=1)).isoformat(),
                "difficulty": 2,
                "priority": 1,
            },
            {
                "id": "t_high_prio",
                "subject": "Chemistry",
                "title": "Organic chem",
                "estimatedHours": 1,
                "deadline": (today + timedelta(days=1)).isoformat(),
                "difficulty": 2,
                "priority": 3,
            },
        ]
        plan = build_plan(topics, 2, start_date=today)
        day1_sessions = plan["days"][0]["sessions"]
        self.assertTrue(len(day1_sessions) > 0)
        first_session = day1_sessions[0]
        # Should be Chemistry (earlier deadline + highest priority)
        self.assertEqual(first_session["topicId"], "t_high_prio")

    def test_missing_estimate_uses_disclosed_difficulty_default(self):
        """No estimate supplied to planner: uses disclosed difficulty default."""
        today = date.today()
        topics = [
            {
                "id": "t1",
                "subject": "History",
                "title": "Notes review",
                "deadline": (today + timedelta(days=2)).isoformat(),
                "difficulty": 2,
                "priority": 2,
            }
        ]
        plan = build_plan(topics, 2, start_date=today)
        self.assertTrue(any("No time estimate was provided" in w["message"] for w in plan["warnings"]))
        # Difficulty 2 default is 1.0 hr = 60 minutes
        total_scheduled = sum(
            s["durationMinutes"]
            for d in plan["days"]
            for s in d["sessions"]
            if not s.get("isRevision")
        )
        self.assertEqual(total_scheduled, 60)

    def test_completed_topics_are_not_scheduled(self):
        """Topic is already complete: excluded from schedule."""
        today = date.today()
        topics = [
            {
                "id": "t1",
                "subject": "Math",
                "title": "Finished task",
                "estimatedHours": 2,
                "deadline": (today + timedelta(days=2)).isoformat(),
                "completed": True,
            }
        ]
        plan = build_plan(topics, 2, start_date=today)
        self.assertEqual(len(plan["days"]), 0)
        self.assertEqual(plan["summary"]["topics"], 0)

    def test_past_due_work_is_reported_not_scheduled(self):
        """Deadline has passed: reported in warnings and not scheduled."""
        today = date.today()
        past = (today - timedelta(days=2)).isoformat()
        topics = [
            {
                "id": "t_past",
                "subject": "Civics",
                "title": "Overdue paper",
                "estimatedHours": 1.5,
                "deadline": past,
                "difficulty": 2,
                "priority": 2,
            }
        ]
        plan = build_plan(topics, 2, start_date=today)
        self.assertTrue(any("Deadline was" in w["message"] and "past-due" in w["message"] for w in plan["warnings"]))
        for day in plan["days"]:
            for session in day["sessions"]:
                self.assertNotEqual(session["topicId"], "t_past")

    def test_plan_adds_short_review_and_breaks_without_exceeding_budget(self):
        """Remaining time can fit a quick review: review added without exceeding daily budget."""
        today = date.today()
        topics = [
            {
                "id": "t1",
                "subject": "Language",
                "title": "Vocab list",
                "estimatedHours": 0.5,  # 30 mins
                "deadline": (today + timedelta(days=1)).isoformat(),
                "difficulty": 1,
                "priority": 2,
            }
        ]
        # Daily budget = 1 hr (60 min). 30 min session leaves 30 min, room for 15 min review.
        plan = build_plan(topics, 1.0, start_date=today)
        day1 = plan["days"][0]
        sessions = day1["sessions"]
        has_revision = any(s.get("isRevision") for s in sessions)
        self.assertTrue(has_revision)
        total_time = sum(s["durationMinutes"] + s.get("breakBeforeMinutes", 0) for s in sessions)
        self.assertLessEqual(total_time, 60)

    def test_rejects_unreasonable_daily_hours_and_deadline_horizon(self):
        """Daily hours or planning horizon are unreasonable: rejects with clear PlanningError."""
        today = date.today()
        topics = [
            {
                "id": "t1",
                "subject": "Science",
                "title": "Lab",
                "estimatedHours": 1,
                "deadline": (today + timedelta(days=2)).isoformat(),
            }
        ]
        with self.assertRaises(PlanningError):
            build_plan(topics, 0.1)  # < 0.5 hours
        with self.assertRaises(PlanningError):
            build_plan(topics, 24)   # > 12 hours

        far_future = (today + timedelta(days=400)).isoformat()
        topics_far = [
            {
                "id": "t2",
                "subject": "Science",
                "title": "Far future exam",
                "estimatedHours": 1,
                "deadline": far_future,
            }
        ]
        with self.assertRaises(PlanningError):
            build_plan(topics_far, 2, start_date=today)


if __name__ == "__main__":
    unittest.main()
