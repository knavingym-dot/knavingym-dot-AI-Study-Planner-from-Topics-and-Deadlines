# Edge-case test report

## Test coverage

| Case | Automated test | Expected behavior |
| --- | --- | --- |
| Work must fit within daily availability, including reset breaks | `test_sessions_fit_daily_limit_including_breaks` | Elapsed focus and break time stays within the daily cap. |
| Several topics share a deadline | `test_overlapping_deadlines_warn_when_work_does_not_fit` | Unplaced work is reported with remaining hours instead of scheduled late. |
| Different deadlines and priorities | `test_deadline_then_priority_then_difficulty_define_order` | Earlier deadlines sort first; priority resolves a same-day tie. |
| No estimate supplied to the planner | `test_missing_estimate_uses_disclosed_difficulty_default` | A difficulty-based default is used and disclosed in a warning. |
| Topic is already complete | `test_completed_topics_are_not_scheduled` | Completed work is excluded from the plan. |
| Deadline has passed | `test_past_due_work_is_reported_not_scheduled` | Past-due work is reported and not assigned a future session. |
| Remaining time can fit a quick review | `test_plan_adds_short_review_and_breaks_without_exceeding_budget` | Review and breaks appear without exceeding available time. |
| Daily hours or planning horizon are unreasonable | `test_rejects_unreasonable_daily_hours_and_deadline_horizon` | The planner rejects invalid inputs with a clear error. |

## Execution status

All eight automated planner tests passed with Python 3.12.10. The app was also started locally, the demo account authenticated successfully, five topics were loaded, and the plan API returned a five-day schedule. The sample dataset JSON was validated and the responsive login and signed-in dashboard were inspected in a browser.

Run the planner tests with Python 3.10+:

```powershell
python -m unittest discover -s tests -v
```
