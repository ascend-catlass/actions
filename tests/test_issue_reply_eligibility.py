import unittest
from scripts.issue_reply_eligibility import eligibility


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        # 带正文的反馈类 Issue：作者身份不影响是否分析
        self.issue = {"state": "open", "user": {"login": "contributor", "name": "Maintainer"},
                      "title": "crash when groupList is empty",
                      "body": "Running with an empty groupList crashes the kernel with an "
                              "out of bounds read inside GetKernelInfo."}
        self.roles = {"repository": "cann/catlass", "maintainer_ids": ["Maintainer"],
                      "committer_ids": ["Committer"]}

    def check(self):
        return eligibility(self.issue, self.roles, "cann/catlass")["analyze"]

    def test_non_member_feedback_is_analyzed_using_login_not_display_name(self):
        self.assertTrue(self.check())

    def test_feedback_from_member_is_assigned_not_analyzed(self):
        """成员反馈不跑 AI 回复：直接分配给自己并发闭环提示。"""
        for login in ["Maintainer", "Committer"]:
            with self.subTest(login=login):
                self.issue["user"]["login"] = login
                result = eligibility(self.issue, self.roles, "cann/catlass")
                self.assertFalse(result["analyze"])
                self.assertTrue(result["remind"])
                self.assertTrue(result["assign"])
                self.assertEqual(result["reason"], "author-is-committer-or-maintainer")

    def test_non_feedback_is_reminded_not_analyzed(self):
        """非反馈类不跑分析，发固定提示。"""
        self.issue["title"] = "weekly sync notes"
        self.issue["body"] = "Meeting notes from this week are attached for review."
        result = eligibility(self.issue, self.roles, "cann/catlass")
        self.assertFalse(result["analyze"])
        self.assertTrue(result["remind"])
        self.assertFalse(result["assign"])
        self.assertEqual(result["reason"], "author-is-internal-developer")

    def test_non_feedback_from_member_is_assigned_and_reminded(self):
        self.issue["title"] = "weekly sync notes"
        self.issue["body"] = "Meeting notes from this week are attached for review."
        self.issue["user"]["login"] = "Maintainer"
        result = eligibility(self.issue, self.roles, "cann/catlass")
        self.assertFalse(result["analyze"])
        self.assertTrue(result["remind"])
        self.assertTrue(result["assign"])

    def test_both_roles_are_skipped_case_insensitively(self):
        """非反馈类时，成员身份大小写不敏感地触发分配。"""
        self.issue["title"] = "weekly sync notes"
        self.issue["body"] = "Meeting notes from this week are attached for review."
        for login in ["MAINTAINER", "committer", "CommitTer"]:
            with self.subTest(login=login):
                self.issue["user"]["login"] = login
                self.assertFalse(self.check())
                result = eligibility(self.issue, self.roles, "cann/catlass")
                self.assertTrue(result["assign"])
                self.assertEqual(result["atomgit_id"], login)

    def test_closed_issue_is_skipped(self):
        self.issue["state"] = "closed"
        self.assertFalse(self.check())
        self.assertFalse(eligibility(self.issue, self.roles, "cann/catlass")["assign"])
        self.issue["user"]["login"] = "Maintainer"
        self.assertFalse(eligibility(self.issue, self.roles, "cann/catlass")["assign"])

    def test_missing_identity_and_invalid_roles_fail_closed(self):
        for user in [None, {}, {"name": "contributor"}, {"login": ""}, {"login": "user\nattack"}]:
            with self.subTest(user=user), self.assertRaises(ValueError):
                eligibility({"state": "open", "user": user}, self.roles, "cann/catlass")
        for invalid in [None, "Committer", [None], ["bad\nid"]]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                eligibility(self.issue, {**self.roles, "committer_ids": invalid}, "cann/catlass")

    def test_wrong_repository_is_rejected(self):
        with self.assertRaises(ValueError):
            eligibility(self.issue, self.roles, "cann/other")

    def test_declared_empty_lists_treat_everyone_as_outsider(self):
        """角色名单为空时，任何人都按外部作者处理。"""
        self.roles.update(maintainer_ids=[], committer_ids=[])
        self.assertTrue(self.check())
        self.issue["title"] = "weekly sync notes"
        self.issue["body"] = "Meeting notes from this week are attached for review."
        result = eligibility(self.issue, self.roles, "cann/catlass")
        self.assertTrue(result["remind"])
        self.assertFalse(result["assign"])


if __name__ == "__main__":
    unittest.main()
