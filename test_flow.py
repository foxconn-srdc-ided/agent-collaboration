import unittest

from flow import FlowError, Run


SHA = "a" * 40


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.run = Run("run-1", "reviewer")
        self.run.set_issue("A_B", 1)
        self.run.propose("A_B", "deliverable and criteria", "A")

    def test_requires_both_agreements_and_resets_on_amendment(self):
        self.assertFalse(self.run.agree("A_B", "A", 1))
        self.run.propose("A_B", "updated criteria", "A", amendment=True)
        with self.assertRaises(FlowError):
            self.run.agree("A_B", "B", 1)
        self.assertFalse(self.run.agree("A_B", "B", 2))
        self.assertTrue(self.run.agree("A_B", "A", 2))

    def test_stale_submission_rejected_and_new_sha_rechecked(self):
        self.run.agree("A_B", "A", 1)
        self.run.agree("A_B", "B", 1)
        with self.assertRaises(FlowError):
            self.run.submit("A_B", "A", SHA, 0, "passed")
        self.run.submit("A_B", "A", SHA, 1, "passed")
        self.run.review_result("A_B", "B", SHA, 1, False, "case failed")
        self.run.submit("A_B", "A", "b" * 40, 2, "passed")
        with self.assertRaises(FlowError):
            self.run.review_result("A_B", "B", SHA, 1, True, "old pass")
        self.run.review_result("A_B", "B", "b" * 40, 2, True, "all cases passed")
        with self.assertRaises(FlowError):
            self.run.accept("A_B", "other", "b" * 40, "approve")
        self.assertEqual(self.run.accept("A_B", "reviewer", "b" * 40, "approve"), "B_C")

    def test_fix_limit_shared_and_duplicate_event(self):
        self.assertTrue(self.run.event("event-1"))
        self.assertFalse(self.run.event("event-1"))
        self.run.agree("A_B", "A", 1)
        self.run.agree("A_B", "B", 1)
        for attempt in range(1, 4):
            self.run.submit("A_B", "A", SHA, attempt, "passed")
            self.run.review_result("A_B", "B", SHA, attempt, False, "failure")
        self.assertEqual(self.run.handoffs["A_B"].status, "阻塞")
        self.assertTrue(self.run.stopped)

    def test_round_trip(self):
        self.assertEqual(Run.from_dict(self.run.as_dict()).as_dict(), self.run.as_dict())

    def test_upstream_defect_preserves_acceptance_and_retests_without_c_fix(self):
        self.run.agree("A_B", "A", 1)
        self.run.agree("A_B", "B", 1)
        self.run.submit("A_B", "A", SHA, 1, "self-check")
        self.run.review_result("A_B", "B", SHA, 1, True, "checked")
        self.run.accept("A_B", "reviewer", SHA, "approved")
        self.run.propose("B_C", "implementation criteria", "B")
        self.run.agree("B_C", "B", 1)
        self.run.agree("B_C", "C", 1)
        self.run.submit("B_C", "B", SHA, 1, "self-check")
        self.run.review_result("B_C", "C", SHA, 1, True, "checked")
        self.run.accept("B_C", "reviewer", SHA, "approved")
        self.run.propose("C_HUMAN", "test scope", "C")
        self.run.agree("C_HUMAN", "C", 1)
        self.run.agree("C_HUMAN", "HUMAN", 1)
        correction = self.run.start_correction("independent test failure")
        self.assertEqual(correction, "B_C_FIX_1")
        self.assertEqual(self.run.handoffs["B_C"].status, "已驗收")
        self.assertEqual(self.run.fixes, {"A": 0, "B": 1, "C": 0})
        self.run.propose(correction, "repair original agreement", "B")
        self.run.agree(correction, "B", 1)
        self.run.agree(correction, "C", 1)
        self.run.submit(correction, "B", "b" * 40, 1, "self-check")
        self.run.review_result(correction, "C", "b" * 40, 1, True, "checked")
        self.run.accept(correction, "reviewer", "b" * 40, "approved")
        self.assertEqual(self.run.stage, "C_HUMAN")
        self.assertEqual(self.run.handoffs["C_HUMAN"].attempt, 2)


if __name__ == "__main__":
    unittest.main()
