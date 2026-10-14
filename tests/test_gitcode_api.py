import io
import json
import unittest
from unittest.mock import patch

from scripts.gitcode_api import GitCodeAPI


class ApiTests(unittest.TestCase):
    def test_form_encoding_keeps_text_literal_and_tokens_in_headers(self):
        response = io.BytesIO(b'{"id":42}')
        with patch("urllib.request.urlopen", return_value=response) as open_url:
            result = GitCodeAPI("private-token").request("POST", "/repos/cann/catlass/issues/739/comments",
                                                       {"body": "中文\n$(echo literal)"})
        req = open_url.call_args.args[0]
        self.assertEqual(result, {"id": 42})
        self.assertNotIn("private-token", req.full_url)
        self.assertNotIn(b"private-token", req.data)
        self.assertEqual(req.get_header("Authorization"), "Bearer private-token")
        self.assertIn(b"%24%28echo+literal%29", req.data)

    def test_json_encoding_and_fixed_api_root(self):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b'{}')) as open_url:
            GitCodeAPI("token").request("PATCH", "/repos/cann/catlass/issues/739", {"body": "hello"}, "json")
        req = open_url.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.gitcode.com/api/v5/repos/cann/catlass/issues/739")
        self.assertEqual(json.loads(req.data), {"body": "hello"})

    def test_invalid_requests_do_not_access_network(self):
        with patch("urllib.request.urlopen") as open_url:
            for method, path, body in [("EXEC", "/user", None), ("GET", "https://evil.test", None),
                                       ("GET", "//evil.test", None), ("GET", "/../user", None),
                                       ("POST", "/user", {"access_token": "secret"})]:
                with self.subTest(path=path), self.assertRaises(ValueError):
                    GitCodeAPI("token").request(method, path, body)
            open_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
