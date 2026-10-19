import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("bmc_power_cycle", Path(__file__).resolve().parents[1] / "scripts/bmc_power_cycle.py")
bmc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bmc)


class PowerTests(unittest.TestCase):
    def client(self):
        return bmc.BMC("192.0.2.1")

    def test_login_form_and_csrf(self):
        client = self.client()
        client.request = Mock(side_effect=[{"encrypt_ctrl": 0, "random": "nonce"}, {"ok": 0, "CSRFToken": "token"}])
        client.login("user", "p#$&+")
        self.assertEqual(client.csrf, "token")
        self.assertEqual(client.request.call_args.args[2]["password"], "p#$&+")
        self.assertTrue(client.request.call_args.kwargs["form"])

    def test_encrypted_login_is_not_downgraded(self):
        client = self.client()
        client.request = Mock(return_value={"encrypt_ctrl": 1, "random": "nonce"})
        with self.assertRaises(RuntimeError):
            client.login("user", "secret")
        self.assertEqual(client.request.call_count, 1)

    def test_failed_login(self):
        client = self.client()
        client.request = Mock(side_effect=[{"encrypt_ctrl": 0, "random": "nonce"}, {"ok": 1}])
        with self.assertRaises(RuntimeError):
            client.login("user", "secret")

    @patch.object(bmc.time, "sleep")
    def test_cycle_sent_once(self, sleep):
        client = self.client()
        client.power_status = Mock(side_effect=[1, 0, 1])
        client.request = Mock(return_value={})
        client.cycle()
        client.request.assert_called_once_with("/itf/actions/power", "POST", {"power_command": 2})

    @patch.object(bmc.time, "sleep")
    def test_already_off_powers_on(self, sleep):
        client = self.client()
        client.power_status = Mock(side_effect=[0, 1])
        client.request = Mock(return_value={})
        client.cycle()
        client.request.assert_called_once_with("/itf/actions/power", "POST", {"power_command": 1})

    def test_uncertain_command_is_not_retried(self):
        client = self.client()
        client.power_status = Mock(return_value=1)
        client.request = Mock(side_effect=OSError("connection lost"))
        with self.assertRaisesRegex(RuntimeError, "uncertain"):
            client.cycle()
        self.assertEqual(client.request.call_count, 1)

    def test_reject_unknown_state(self):
        client = self.client()
        client.request = Mock(return_value={"power_status": "1"})
        with self.assertRaises(RuntimeError):
            client.power_status()

    def test_form_encoding_preserves_special_characters(self):
        client = self.client()
        response = Mock()
        response.read.return_value = b'{"ok":0}'
        client.opener.open = Mock()
        client.opener.open.return_value.__enter__ = Mock(return_value=response)
        client.opener.open.return_value.__exit__ = Mock(return_value=False)
        client.request("/itf/session", "POST", {"password": "p#$&+"}, form=True)
        req = client.opener.open.call_args.args[0]
        self.assertEqual(bmc.urllib.parse.parse_qs(req.data.decode()), {"password": ["p#$&+"]})
        self.assertEqual(req.get_header("Content-type"), "application/x-www-form-urlencoded")

    def test_https_verification_is_explicitly_opt_in_to_disable(self):
        with patch.object(bmc.ssl, "create_default_context") as factory:
            context = factory.return_value
            self.client()
            self.assertFalse(context.check_hostname is False)
            bmc.BMC("192.0.2.1", insecure=True)
            self.assertFalse(context.check_hostname)
            self.assertEqual(context.verify_mode, bmc.ssl.CERT_NONE)


if __name__ == "__main__":
    unittest.main()
