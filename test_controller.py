import json
import unittest
from unittest.mock import patch

import controller
from flow import Run


SHA = "a" * 40


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.run = Run("run-1", "reviewer")
        self.runs = {self.run.run_id: self.run}

    def test_work_card_events_do_not_dispatch(self):
        with patch.object(controller, "gh") as gh, patch.object(controller, "dispatch") as dispatch:
            controller.handle(self.runs, {"action": "created", "issue": {"number": 99},
                                          "comment": {"user": {"login": "reviewer"}, "body": "/agree v1"}},
                              "issue_comment")
            controller.handle(self.runs, {"action": "closed", "issue": {"number": 99}}, "issues")
            gh.assert_not_called()
            dispatch.assert_not_called()

    def test_early_close_reopens_without_advancing(self):
        self.run.set_issue("A_B", 1)
        event = {"action": "closed", "issue": {"number": 1, "state_reason": "completed"},
                 "sender": {"login": "reviewer"}}
        with patch.object(controller, "gh", return_value="[]") as gh:
            controller.handle(self.runs, event, "issues")
            self.assertTrue(any(call.args[:2] == ("issue", "reopen") for call in gh.call_args_list))
        self.assertEqual(self.run.stage, "A_B")

    def test_latest_passed_sha_and_human_close_advance(self):
        self.run.set_issue("A_B", 1)
        self.run.propose("A_B", "criteria", "A")
        self.run.agree("A_B", "A", 1)
        self.run.agree("A_B", "B", 1)
        self.run.submit("A_B", "A", SHA, 1, "self-check")
        self.run.review_result("A_B", "B", SHA, 1, True, "checked")
        event = {"action": "closed", "issue": {"number": 1, "state_reason": "completed"},
                 "sender": {"login": "reviewer"}}
        comments = json.dumps([{"user": {"login": "reviewer"}, "body": f"/accept {SHA} complete"}])
        with patch.object(controller, "gh", return_value=comments), \
             patch.object(controller, "dispatch") as dispatch, \
             patch.object(controller, "label"):
            controller.handle(self.runs, event, "issues")
            dispatch.assert_called_once()
        self.assertEqual(self.run.stage, "B_C")

    def test_model_failure_before_card_records_block(self):
        event = {"action": "agent-report", "sender": {"type": "Bot"},
                 "client_payload": {"run_id": "run-1", "stage": "A_B", "role": "A",
                                    "repo": "agent-a", "report_id": "r1", "version": 1,
                                    "attempt": 0, "action": "failed", "failed_action": "propose",
                                    "text": "API unavailable"}}
        with patch.object(controller, "gh"):
            controller.handle(self.runs, event, "repository_dispatch")
        self.assertIn("API unavailable", self.run.stopped)
        self.assertEqual(self.run.handoffs["A_B"].blocked_action, "propose")


if __name__ == "__main__":
    unittest.main()
