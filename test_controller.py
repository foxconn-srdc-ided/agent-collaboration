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

    def test_start_defaults_acceptor_to_token_owner(self):
        with patch.dict(controller.os.environ, {"GITHUB_RUN_ID": "123"}), \
             patch.object(controller, "dispatch"):
            controller.handle(self.runs, {"inputs": {"mode": "start", "human": ""}}, "workflow_dispatch")
        self.assertEqual(self.runs["run-123"].human, "ycliu-dev")

    def test_human_grant_restores_one_a_attempt_on_same_run(self):
        h = self.run.handoffs["A_B"]
        h.issue = 1
        h.status = "阻塞"
        h.attempt = 5
        self.run.fixes["A"] = 3
        self.run.stopped = "A 修正額度耗盡"
        comments = json.dumps([[{"user": {"login": "reviewer"},
                                 "body": "授權在原 run 額外增加 A 一次修正額度"}]])
        event = {"inputs": {"mode": "grant_a_fix", "run_id": "run-1"},
                 "sender": {"login": "reviewer"}}
        with patch.object(controller, "gh", return_value=comments), \
             patch.object(controller, "comment"), patch.object(controller, "label"), \
             patch.object(controller, "dispatch") as dispatch:
            controller.handle(self.runs, event, "workflow_dispatch")
            dispatch.assert_called_once()
            with self.assertRaisesRegex(Exception, "只可對本次"):
                controller.handle(self.runs, event, "workflow_dispatch")
        self.assertEqual(self.run.extra_fixes["A"], 1)
        self.assertEqual(h.attempt, 6)
        self.assertEqual(h.status, "待補件")
        self.assertFalse(self.run.stopped)

    def test_dispatch_payload_has_one_top_level_property(self):
        with patch.object(controller, "gh") as gh:
            controller.dispatch("A", "propose", self.run, "A_B")
        payload = gh.call_args.kwargs["payload"]
        self.assertEqual(list(payload["client_payload"]), ["task"])
        self.assertEqual(payload["client_payload"]["task"]["run_id"], "run-1")

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
        self.run.handoffs["A_B"].passed_at = "2026-10-20T00:00:00+00:00"
        event = {"action": "closed", "issue": {"number": 1, "state_reason": "completed"},
                 "sender": {"login": "reviewer"}}
        comments = json.dumps([[{"user": {"login": "reviewer"}, "body": f"/accept {SHA} complete",
                                 "created_at": "2026-10-20T00:01:00Z"}]])
        with patch.object(controller, "gh", return_value=comments), \
             patch.object(controller, "dispatch") as dispatch, \
             patch.object(controller, "label"):
            controller.handle(self.runs, event, "issues")
            dispatch.assert_called_once()
        self.assertEqual(self.run.stage, "B_C")

    def test_old_accept_comment_does_not_approve_new_check(self):
        self.run.set_issue("A_B", 1)
        self.run.handoffs["A_B"].status = "待人工驗收"
        self.run.handoffs["A_B"].passed_sha = SHA
        self.run.handoffs["A_B"].passed_at = "2026-10-20T00:02:00+00:00"
        comments = json.dumps([[{"user": {"login": "reviewer"}, "body": f"/accept {SHA} old",
                                 "created_at": "2026-10-20T00:01:00Z"}]])
        event = {"action": "closed", "issue": {"number": 1, "state_reason": "completed"},
                 "sender": {"login": "reviewer"}}
        with patch.object(controller, "gh", return_value=comments) as gh:
            controller.handle(self.runs, event, "issues")
            self.assertTrue(any(call.args[:2] == ("issue", "reopen") for call in gh.call_args_list))
        self.assertEqual(self.run.stage, "A_B")

    def test_model_failure_before_card_records_block(self):
        self.run.handoffs["A_B"].pending_role = "A"
        self.run.handoffs["A_B"].pending_action = "propose"
        event = {"action": "agent-report", "sender": {"login": "ycliu-dev"},
                 "client_payload": {"report": {"run_id": "run-1", "stage": "A_B", "role": "A",
                                    "repo": "agent-a", "report_id": "r1", "version": 1,
                                    "attempt": 0, "action": "failed", "failed_action": "propose",
                                    "text": "API unavailable"}}}
        with patch.object(controller, "gh"):
            controller.handle(self.runs, event, "repository_dispatch")
        self.assertIn("API unavailable", self.run.stopped)
        self.assertEqual(self.run.handoffs["A_B"].blocked_action, "propose")

    def test_report_rejects_wrong_sender_or_pending_action(self):
        h = self.run.handoffs["A_B"]
        h.pending_role, h.pending_action = "A", "propose"
        payload = {"run_id": "run-1", "stage": "A_B", "role": "A", "repo": "agent-a",
                   "report_id": "r1", "version": 1, "attempt": 0, "action": "agree", "agree": True}
        with self.assertRaisesRegex(Exception, "授權帳號"):
            controller.handle(self.runs, {"action": "agent-report", "sender": {"login": "intruder"},
                                          "client_payload": {"report": payload}}, "repository_dispatch")
        with self.assertRaisesRegex(Exception, "待處理派工"):
            controller.handle(self.runs, {"action": "agent-report", "sender": {"login": "ycliu-dev"},
                                          "client_payload": {"report": payload}}, "repository_dispatch")
        self.assertEqual(self.run.seen, [])

    def test_complete_three_handoffs_routes_to_done(self):
        issue_no = 0
        approvals = {}

        def fake_gh(*args, **kwargs):
            nonlocal issue_no
            if args[:2] == ("issue", "create"):
                issue_no += 1
                return f"https://github.com/foxconn-srdc-ided/agent-collaboration/issues/{issue_no}"
            if args[:1] == ("api",) and args[1].endswith("/comments"):
                number = int(args[1].split("/")[-2])
                return json.dumps([[{"user": {"login": "reviewer"}, "body": approvals[number],
                                     "created_at": "9999-01-01T00:00:00Z"}]])
            return "{}"

        report_id = 0

        def report(stage, role, action, **fields):
            nonlocal report_id
            report_id += 1
            h = self.run.handoffs[stage]
            h.pending_role, h.pending_action = role, action
            payload = {"run_id": self.run.run_id, "stage": stage, "role": role,
                       "repo": controller.ROLE_REPO[role], "report_id": str(report_id),
                       "version": h.agreement_version, "attempt": h.attempt,
                       "action": action, **fields}
            controller.handle(self.runs, {"action": "agent-report", "sender": {"login": "ycliu-dev"},
                                          "client_payload": {"report": payload}}, "repository_dispatch")

        def close(stage):
            h = self.run.handoffs[stage]
            approvals[h.issue] = f"/accept {h.passed_sha} complete"
            controller.handle(self.runs, {"action": "closed",
                                          "issue": {"number": h.issue, "state_reason": "completed"},
                                          "sender": {"login": "reviewer"}}, "issues")

        with patch.object(controller, "gh", side_effect=fake_gh), \
             patch.object(controller, "dispatch"), patch.object(controller, "label"):
            report("A_B", "A", "propose", text="spec criteria")
            report("A_B", "B", "agree", agree=True, text="yes")
            report("A_B", "A", "agree", agree=True, text="yes")
            report("A_B", "A", "produce", sha=SHA, text="self-check")
            report("A_B", "B", "review", sha=SHA, passed=True, text="checked")
            close("A_B")
            report("B_C", "B", "propose", text="implementation criteria")
            report("B_C", "C", "agree", agree=True, text="yes")
            report("B_C", "B", "agree", agree=True, text="yes")
            report("B_C", "B", "produce", sha=SHA, text="tests passed")
            report("B_C", "C", "review", sha=SHA, passed=True, text="checked")
            close("B_C")
            report("C_HUMAN", "C", "propose", text="test scope")
            controller.handle(self.runs, {"action": "created", "issue": {"number": 3},
                                          "comment": {"user": {"login": "reviewer"},
                                                      "body": "/agree v1"}}, "issue_comment")
            report("C_HUMAN", "C", "agree", agree=True, text="yes")
            report("C_HUMAN", "C", "produce", sha=SHA, text="six cases passed")
            close("C_HUMAN")
        self.assertEqual(self.run.stage, "DONE")
        self.assertEqual(issue_no, 3)


if __name__ == "__main__":
    unittest.main()
