#!/usr/bin/env python3
"""Log into a BMC and request its native power-off/power-on cycle."""

import argparse
import getpass
import http.cookiejar
import ipaddress
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("BMC redirected the request; refusing to forward credentials")


class BMC:
    def __init__(self, ip, ca_cert=None, insecure=False):
        address = ipaddress.ip_address(ip)
        host = f"[{address}]" if address.version == 6 else str(address)
        self.base = f"https://{host}"
        self.csrf = None
        self.cookies = http.cookiejar.CookieJar()
        context = ssl.create_default_context(cafile=ca_cert)
        if insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=context),
            urllib.request.HTTPCookieProcessor(self.cookies),
            NoRedirect(),
        )

    def request(self, path, method="GET", data=None, form=False):
        headers = {"Accept": "application/json"}
        if self.csrf:
            headers["X-CSRFTOKEN"] = self.csrf
        body = None
        if data is not None:
            headers["Content-Type"] = (
                "application/x-www-form-urlencoded" if form else "application/json"
            )
            body = (urllib.parse.urlencode(data) if form else json.dumps(data)).encode()
        req = urllib.request.Request(self.base + path, body, headers, method=method)
        try:
            with self.opener.open(req, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{method} {path}: HTTP {exc.code}") from None
        result = json.loads(raw) if raw.strip() else {}
        if not isinstance(result, dict):
            raise RuntimeError(f"{path}: expected a JSON object")
        return result

    def login(self, username, password):
        challenge = self.request("/itf/randomtag")
        if challenge.get("encrypt_ctrl") != 0:
            raise RuntimeError("This firmware requires RSA login; plaintext fallback refused")
        if not challenge.get("random"):
            raise RuntimeError("Login challenge is missing")
        result = self.request("/itf/session", "POST", {
            "encrypt_flag": 0, "username": username, "password": password,
            "login_tag": challenge["random"],
        }, form=True)
        self.csrf = result.get("CSRFToken")
        if result.get("ok") != 0 or not self.csrf:
            raise RuntimeError("Login failed or a password change is required")
        print("Login successful", flush=True)

    def power_status(self):
        result = self.request("/itf/chassis-status")
        state = result.get("power_status")
        if type(state) is not int or state not in (0, 1):
            raise RuntimeError("Unexpected power status")
        return state

    def cycle(self, timeout=180, settle=20):
        initial = self.power_status()
        # 2 is the BMC's native force-off-then-on command; do not replay it.
        command = 2 if initial == 1 else 1
        print("Requesting power cycle" if initial else "Host already off; requesting power on", flush=True)
        try:
            result = self.request("/itf/actions/power", "POST", {"power_command": command})
        except (OSError, RuntimeError, ValueError) as exc:
            raise RuntimeError("Power request outcome is uncertain; inspect host state before retrying") from exc
        if "ok" in result and result["ok"] != 0:
            raise RuntimeError("BMC rejected the power request")
        print("Power request accepted; waiting for BMC power-on status", flush=True)
        deadline = time.monotonic() + timeout
        time.sleep(settle)
        while time.monotonic() < deadline:
            if self.power_status() == 1:
                print("Verified: power_status=1 (powered on; OS readiness not checked)", flush=True)
                return
            time.sleep(3)
        raise RuntimeError("Timed out waiting for power on; do not blindly repeat the cycle")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ip", help="BMC IP address")
    parser.add_argument("username")
    parser.add_argument("password", nargs="?", help="Prefer BMC_PASSWORD or an interactive prompt")
    parser.add_argument("--ca-cert", help="Trusted CA/certificate PEM for this BMC")
    parser.add_argument("--insecure", action="store_true", help="Explicitly disable HTTPS certificate verification")
    parser.add_argument("--status-only", action="store_true", help="Test login and query power without changing it")
    args = parser.parse_args()
    password = args.password or os.environ.get("BMC_PASSWORD") or getpass.getpass("BMC password: ")
    client = BMC(args.ip, args.ca_cert, args.insecure)
    try:
        client.login(args.username, password)
        if args.status_only:
            print(f"power_status={client.power_status()}", flush=True)
        else:
            client.cycle()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if client.csrf:
            try:
                client.request("/itf/session", "DELETE")
            except (OSError, RuntimeError, ValueError):
                print("Warning: could not close the BMC session", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
