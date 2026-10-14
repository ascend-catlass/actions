import unittest
from scripts.issue_reply_eligibility import eligibility


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.issue = {"state": "open", "user": {"login": "contributor", "name": "Maintainer"}}
        self.roles = {"repository": "cann/catlass", "maintainer_ids": ["Maintainer"],
                      "committer_ids": ["Committer"]}

    def check(self):
        return eligibility(self.issue, self.roles, "cann/catlass")["analyze"]

    def test_non_member_is_analyzed_using_login_not_display_name(self):
        self.assertTrue(self.check())

    def test_both_roles_are_skipped_case_insensitively(self):
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

    def test_declared_empty_lists_allow_contributors(self):
        self.roles.update(maintainer_ids=[], committer_ids=[])
        self.assertTrue(self.check())


if __name__ == "__main__":
    unittest.main()
